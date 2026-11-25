"""Makna Puisi (versi ringan): bantuan membaca sebuah puisi dengan ATURAN dan LEKSIKON, bukan pemahaman makna.

Isi hasil:
  ringkasan    kalimat templat tentang bentuk puisi + kata menonjol + suasana (BUKAN ringkasan abstraktif)
  diksi_penting  (a) kata di puisi yang ada di kamus Ruang Diksi, dengan makna dan nuansanya
                 (b) kata menonjol: sering di puisi ini tetapi jarang di korpus (tf x idf)
  baris_kunci  baris dengan bobot kata menonjol tertinggi
  frasa_kiasan KANDIDAT: perumpamaan (seperti/bagai/...), pola "A adalah B", dan personifikasi (benda/alam + kata kerja manusia)
  sentimen     hasil sentiment_analysis.py (satu-satunya mesin sentimen), bukti kata, dan pergerakannya per bait

Batas (sebutkan di laporan): leksikon kecil dan disusun sendiri, belum divalidasi terhadap penilaian manusia;
deteksi kiasan hanya pola permukaan dan akan salah pada kiasan tanpa penanda dan pada kalimat harfiah.
"""
import math
from collections import Counter

import analysis
import corpus
import diksi_repo as dr
import sentiment_analysis
from preprocess import tokenize

# ------------------------------------------------------------------ sentimen
# Gunakan satu sumber analisis sentimen untuk seluruh aplikasi Puitika:
# sentiment_analysis.py. Adapter di bawah menjaga nama field yang dipakai
# Makna Puisi v6 agar output/API dan pengujian fitur tetap kompatibel.

def _label_sentimen(polarity):
    return {
        "positif": "cenderung positif",
        "negatif": "cenderung negatif",
        "netral": "netral",
        "campuran": "campuran",
        "tidak_terdeteksi": "tidak cukup sinyal",
    }.get(polarity, "tidak cukup sinyal")


def _jumlah_bukti(items):
    return sum(int(item.get("jumlah", 0)) for item in items)


def sentimen(text, db=None):
    """Adapter ke sentiment_analysis.analyze_sentiment (tanpa leksikon duplikat).

    Field polarity/score/evidence/method tetap disediakan oleh analyzer utama.
    Alias label/skor/kata_positif/kata_negatif/per_bait menjaga kompatibilitas
    dengan struktur Makna Puisi v6.
    """
    raw = sentiment_analysis.analyze_sentiment(text, analyze_stanzas=True)
    evidence = raw.get("evidence", {})
    positive = evidence.get("positif", [])
    negative = evidence.get("negatif", [])
    has_evidence = bool(raw.get("has_lexicon_evidence"))

    per_bait = []
    for stanza in raw.get("stanzas", []):
        stanza_evidence = stanza.get("evidence", {})
        stanza_positive = stanza_evidence.get("positif", [])
        stanza_negative = stanza_evidence.get("negatif", [])
        stanza_has_evidence = bool(stanza.get("has_lexicon_evidence"))
        per_bait.append({
            "bait": stanza.get("stanza"),
            "positif": _jumlah_bukti(stanza_positive),
            "negatif": _jumlah_bukti(stanza_negative),
            "skor": stanza.get("score") if stanza_has_evidence else None,
            "label": _label_sentimen(stanza.get("polarity")),
        })

    return {
        **raw,
        "label": _label_sentimen(raw.get("polarity")),
        "skor": raw.get("score") if has_evidence else None,
        "kata_positif": _jumlah_bukti(positive),
        "kata_negatif": _jumlah_bukti(negative),
        "bukti_positif": [item.get("kata") for item in positive],
        "bukti_negatif": [item.get("kata") for item in negative],
        "per_bait": per_bait,
    }

SIMILE = {"seperti", "bagai", "bagaikan", "laksana", "ibarat", "bak", "umpama"}
SIMILE_LITERAL_NEXT = {"ini", "itu", "biasa", "yang", "sebelumnya", "dahulu", "dulu", "kemarin", "apa", "dia", "kamu", "kau"}
COPULA = {"adalah", "ialah", "merupakan"}
NATURE_NOUNS = set(
    """hujan angin bulan matahari malam senja laut ombak langit awan bintang pohon daun bunga sungai gunung fajar embun kabut
    waktu sepi sunyi harapan kenangan takdir musim pagi dingin api tanah bumi batu jalan rumah kota""".split()
)
HUMAN_VERBS = set(
    """menangis berbisik bisik tersenyum tersenyum tertawa menari berteriak memeluk mencium bernyanyi menyanyi berdoa merindu
    bercerita bercerita mengintip menunggu mengetuk memanggil menyapa mengantar menjemput berjalan pulang tidur tertidur terjaga
    menggenggam mendekap membisikkan menyimpan menertawakan merajuk marah berduka bersedih menjerit mengeluh berkeluh membaca
    menulis memanggil mengingat melupakan memaafkan merangkul menatap bernapas berbicara berkata mendengar mengerti bersembunyi
    mengembara mengusap memeluk-meluk""".split()
)




# ------------------------------------------------------------------ bagian-bagian analisis
def _tokens(line):
    return [corpus.strip_clitic(t) for t in tokenize(line, stopwords=False, min_len=1)]


def frasa_kiasan(text):
    lines = analysis.clean_lines(text)
    out = []
    for n, line in enumerate(lines, start=1):
        toks = _tokens(line)
        for i, t in enumerate(toks):
            if t in SIMILE:
                nxt = toks[i + 1] if i + 1 < len(toks) else ""
                if not nxt or nxt in SIMILE_LITERAL_NEXT:
                    continue
                out.append({"jenis": "perumpamaan", "baris": n, "frasa": " ".join(toks[max(0, i - 2): i + 5]), "penanda": t, "keyakinan": "sedang"})
                break
        for i, t in enumerate(toks):
            if t in COPULA and 0 < i < len(toks) - 1:
                out.append({"jenis": "kemungkinan metafora", "baris": n, "frasa": " ".join(toks[max(0, i - 2): i + 3]), "penanda": t,
                            "keyakinan": "rendah"})
                break
        hit = False
        for i, t in enumerate(toks):
            if t in NATURE_NOUNS and not hit:
                for v in toks[i + 1: i + 4]:
                    if v in HUMAN_VERBS:
                        out.append({"jenis": "kemungkinan personifikasi", "baris": n, "frasa": f"{t} ... {v}", "penanda": v, "keyakinan": "rendah"})
                        hit = True
                        break
    return out



def diksi_penting(db, text, top_n=8):
    """(kata_kamus, kata_menonjol, skor_per_kata)"""
    toks = corpus.corpus_words(text)
    tf = Counter(toks)
    st = corpus.corpus_stats(db)
    n_docs, df = st["n_docs"], st["df"]
    sal = {w: c * (math.log((n_docs + 1) / (df.get(w, 0) + 1)) + 1.0 if n_docs else c) for w, c in tf.items()}
    menonjol = [{"kata": w, "jumlah": tf[w], "bobot": round(s, 2)} for w, s in sorted(sal.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]]

    kamus = []
    try:
        keys = dr.word_keys(db)
        seen = set()
        for t in _tokens(text):
            if t in keys and t not in seen:
                seen.add(t)
                e = dr.get_entry(db, t, with_relations=False)
                kamus.append({"kata": e["kata"], "makna": e["makna"], "nuansa": e["nuansa"]})
        kamus = kamus[:10]
    except Exception:
        kamus = None  # kamus belum dimuat
    return kamus, menonjol, sal


def baris_kunci(text, sal):
    best, best_score = None, 0.0
    for n, line in enumerate(analysis.clean_lines(text), start=1):
        toks = corpus.corpus_words(line)
        if not toks:
            continue
        sc = sum(sal.get(t, 0.0) for t in toks) / math.sqrt(len(toks))
        if sc > best_score:
            best, best_score = {"baris": n, "teks": line}, sc
    return best


def _normalisasi_tema(tema):
    """Samakan bentuk kandidat tema dari berbagai versi analysis/predict.

    Sebagian versi mengembalikan kandidat sebagai tuple (label, probabilitas),
    sedangkan versi lain sudah mengubahnya menjadi dictionary {label, prob}.
    API Makna Puisi selalu mengeluarkan bentuk dictionary yang konsisten.
    """
    if not tema:
        return tema

    hasil = dict(tema)
    kandidat_baru = []
    for kandidat in tema.get("kandidat", []) or []:
        if isinstance(kandidat, dict):
            label = kandidat.get("label")
            probabilitas = kandidat.get("prob", kandidat.get("probabilitas"))
        elif isinstance(kandidat, (tuple, list)) and len(kandidat) >= 2:
            label, probabilitas = kandidat[0], kandidat[1]
        else:
            # Abaikan kandidat dengan bentuk tidak dikenal agar respons API
            # tidak gagal hanya karena ada format hasil prediksi yang berbeda.
            continue

        if label is None:
            continue
        item = {"label": str(label)}
        if probabilitas is not None:
            try:
                item["prob"] = round(float(probabilitas), 3)
            except (TypeError, ValueError):
                item["prob"] = None
        kandidat_baru.append(item)

    hasil["kandidat"] = kandidat_baru
    hasil["yakin"] = bool(tema.get("yakin", False))
    return hasil


def _ringkasan(st, menonjol, sen, tema):
    parts = [f"Puisi ini terdiri atas {st['n_bait']} bait dan {st['n_baris']} baris."]
    if menonjol:
        parts.append("Kata yang menonjol: " + ", ".join(m["kata"] for m in menonjol[:4]) + ".")
    if sen["label"] != "tidak cukup sinyal":
        parts.append(f"Berdasarkan daftar kata, suasananya {sen['label']}.")
    if tema and tema.get("kandidat"):
        k = tema["kandidat"][0]
        label = k.get("label") if isinstance(k, dict) else (k[0] if isinstance(k, (tuple, list)) and k else str(k))
        if label:
            parts.append(f"Model menyarankan tema {label}" + ("." if tema.get("yakin") else " (tidak yakin)."))
    return " ".join(parts)


def analyze_makna(db, text, model_dir):
    st = analysis.stats(text)
    kamus, menonjol, sal = diksi_penting(db, text)
    sen = sentimen(text)
    tema = _normalisasi_tema(analysis.model_suggestions(text, model_dir).get("tema"))
    return {
        "ringkasan": _ringkasan(st, menonjol, sen, tema),
        "diksi_penting": {"kata_kamus": kamus, "kata_menonjol": menonjol},
        "baris_kunci": baris_kunci(text, sal),
        "frasa_kiasan": frasa_kiasan(text),
        "sentimen": sen,
        "tema": tema,
        "catatan": "Analisis berbasis aturan dan daftar kata, bukan pemahaman makna. Tafsir akhir tetap di tangan pembaca.",
    }
