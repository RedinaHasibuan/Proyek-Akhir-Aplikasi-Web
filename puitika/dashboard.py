"""Dashboard Sastra: statistik korpus puisi PUBLIK, distribusi tema, frekuensi kata, dan clustering eksploratif.

Clustering = KMeans pada TF-IDF isi puisi. Ini EKSPLORASI tanpa label: klaster belum tentu sama dengan tema.
Kesesuaian klaster dengan tema dihitung (ARI dan NMI) hanya terhadap label buatan manusia (manual/user),
bukan label prediksi model, supaya tidak berputar-putar. Hasil di-cache 10 menit.
"""
import statistics
import time
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score

import corpus
import repo

TTL = 600
MIN_DOCS = 20
K_RANGE = range(3, 9)
BINS = [(0, 50), (51, 100), (101, 200), (201, 400), (401, None)]
_cache = {}


def reset_cache():
    _cache.clear()
    corpus.reset_cache()


def _length_hist(lengths):
    out = []
    for lo, hi in BINS:
        n = sum(1 for x in lengths if x >= lo and (hi is None or x <= hi))
        out.append({"rentang": f"{lo}-{hi}" if hi else f">{lo - 1}", "jumlah": n})
    return out


def _stats(db):
    with db.cursor() as cur:
        rows = cur.execute("SELECT poet_id, n_words, n_lines FROM poems WHERE in_public_library = 1").all()
        src = cur.execute(
            "SELECT l.source AS source, COUNT(DISTINCT l.poem_id) AS n FROM poem_labels l JOIN poems p ON p.id = l.poem_id "
            "WHERE p.in_public_library = 1 AND l.label_type = 'tema' GROUP BY l.source"
        ).all()
    words = [r["n_words"] for r in rows]
    return {
        "n_puisi": len(rows),
        "n_penyair": len({r["poet_id"] for r in rows if r["poet_id"]}),
        "n_tanpa_penyair": sum(1 for r in rows if not r["poet_id"]),
        "total_kata": int(sum(words)),
        "kata_per_puisi": {
            "rata_rata": round(statistics.mean(words), 1) if words else 0,
            "median": statistics.median(words) if words else 0,
            "maks": max(words) if words else 0,
        },
        "sebaran_panjang": _length_hist(words),
        "label_tema_per_sumber": {r["source"]: r["n"] for r in src},
    }


def _cluster(db, k=None):
    with db.cursor() as cur:
        poems = cur.execute("SELECT id, title, body FROM poems WHERE in_public_library = 1 ORDER BY id").all()
        manual = {
            r["poem_id"]: r["label"]
            for r in cur.execute(
                "SELECT poem_id, label FROM poem_labels WHERE label_type = 'tema' AND source <> 'model'"
            ).all()
        }
    if len(poems) < MIN_DOCS:
        return {"tersedia": False, "alasan": f"Korpus publik baru {len(poems)} puisi; clustering butuh minimal {MIN_DOCS}."}
    vec = TfidfVectorizer(tokenizer=corpus.corpus_words, lowercase=False, token_pattern=None, sublinear_tf=True, min_df=2, max_df=0.8)
    try:
        X = vec.fit_transform([p["body"] for p in poems])
    except ValueError:
        return {"tersedia": False, "alasan": "Kosakata terlalu sedikit untuk clustering."}
    terms = vec.get_feature_names_out()

    def fit(kk):
        km = KMeans(n_clusters=kk, n_init=10, random_state=0)
        return km, km.fit_predict(X)

    sil_by_k = {}
    if k is None:
        best = None
        for kk in K_RANGE:
            if kk >= len(poems):
                break
            km, lab = fit(kk)
            if len(set(lab)) < 2:
                continue
            s = float(silhouette_score(X, lab, metric="cosine"))
            sil_by_k[kk] = round(s, 3)
            if best is None or s > best[0]:
                best = (s, kk, km, lab)
        if best is None:
            return {"tersedia": False, "alasan": "Tidak ada pembagian klaster yang valid."}
        _, k, km, lab = best
    else:
        km, lab = fit(k)
        sil_by_k[k] = round(float(silhouette_score(X, lab, metric="cosine")), 3) if len(set(lab)) > 1 else None

    # jarak ke centroid -> contoh judul terdekat
    dist = km.transform(X)
    clusters = []
    for c in range(k):
        idx = np.where(lab == c)[0]
        top = km.cluster_centers_[c].argsort()[::-1][:8]
        nearest = idx[np.argsort(dist[idx, c])[:3]]
        tema_dist = Counter(manual[poems[i]["id"]] for i in idx if poems[i]["id"] in manual)
        clusters.append(
            {
                "klaster": c + 1,
                "ukuran": int(len(idx)),
                "kata_khas": [str(terms[t]) for t in top],
                "contoh_judul": [poems[i]["title"] for i in nearest],
                "tema_berlabel": dict(tema_dist),
            }
        )
    clusters.sort(key=lambda x: -x["ukuran"])

    kesesuaian = None
    ids = [i for i, p in enumerate(poems) if p["id"] in manual]
    if len(ids) >= 20 and len({manual[poems[i]["id"]] for i in ids}) >= 2:
        truth = [manual[poems[i]["id"]] for i in ids]
        pred = [int(lab[i]) for i in ids]
        kesesuaian = {
            "n_berlabel": len(ids),
            "ARI": round(float(adjusted_rand_score(truth, pred)), 3),
            "NMI": round(float(normalized_mutual_info_score(truth, pred)), 3),
            "catatan": "0 = klaster tidak berhubungan dengan tema; 1 = identik. Nilai kecil wajar: klaster dibentuk oleh kosakata, bukan tema.",
        }
    return {
        "tersedia": True,
        "k": int(k),
        "silhouette": sil_by_k.get(k),
        "silhouette_per_k": sil_by_k,
        "klaster": clusters,
        "kesesuaian_dengan_tema": kesesuaian,
        "catatan": "Eksplorasi tanpa label: klaster mengelompokkan puisi berdasarkan kata yang mirip, belum tentu bertema sama.",
    }


def get_dashboard(db, k=None):
    key = (db.kind, db.sqlite_path, k)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    st = corpus.corpus_stats(db)
    counts = repo.filter_counts(db)
    top_words = [
        {"kata": w, "jumlah": c, "jumlah_puisi": st["df"][w]} for w, c in st["tf"].most_common(30)
    ]
    result = {
        "korpus": _stats(db),
        "tema": {"distribusi": counts["tema"], "belum_berlabel": counts["tema_unlabeled"]},
        "periode": {"distribusi": counts["periode"], "tanpa_periode": counts["periode_unmapped"]},
        "penyair_teratas": repo.list_poets(db, limit=10),
        "frekuensi_kata": top_words,
        "clustering": _cluster(db, k),
        "catatan": "Hanya puisi di Perpustakaan (publik). Sebaran tema di sini bukan sebaran asli korpus bila lembar label disampel dengan kuota kata kunci.",
    }
    _cache[key] = (time.time(), result)
    return result
