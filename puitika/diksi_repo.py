"""Query Ruang Diksi: daftar kata, detail + relasi, kata mirip, dan pencarian berdasarkan deskripsi makna.

Pencarian deskripsi memakai TF-IDF + cosine similarity di atas teks (kata, kata_kunci, makna, nuansa) tiap entri.
Ini mencocokkan KATA yang sama, bukan makna: deskripsi yang tidak berbagi kata dengan entri tidak akan ketemu.
Karena itu kolom kata_kunci di CSV penting. Hasil di bawah ambang skor dibuang daripada ditebak.
"""
import difflib
import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from labels import EMOSI_LIST
from preprocess import tokenize
from repo import like_pattern

REL_TYPES = ("sinonim", "antonim", "terkait")
MIN_SCORE = 0.08          # di bawah ini dianggap tidak cocok
REL_CUTOFF = 0.4          # dan hasil yang skornya < 40% dari skor teratas ikut dibuang
INDEX_TTL = 60            # detik; data baru dari load_diksi.py muncul paling lambat segini lamanya
_index_cache = {}


def word_key(w):
    return " ".join((w or "").casefold().split())


_PREFIXES = ("meny", "meng", "mem", "men", "ter", "ber", "per", "di", "ke", "se", "me", "pe")
_SUFFIXES = ("kan", "nya", "lah", "kah", "an")


def light_stem(w):
    """Pemotong imbuhan sederhana (BUKAN stemmer lengkap) supaya 'ditakdirkan' bertemu 'takdir'.

    Dipakai sama persis pada kamus dan pada deskripsi pengguna, jadi bentuk yang salah potong tetap konsisten.
    Pada 45 query uji (dua berkas eval_queries*.csv, selisihnya hanya 1-2 query) hasilnya sedikit lebih baik
    daripada tanpa pemotongan; sampel sekecil itu belum cukup untuk menyimpulkan banyak.
    """
    for p in _PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= 4:
            w = w[len(p):]
            break
    for s in _SUFFIXES:
        if w.endswith(s) and len(w) - len(s) >= 4:
            w = w[: -len(s)]
            break
    return w


def _tok(text):
    return [light_stem(t) for t in tokenize(text)]


def _brief(r):
    return {
        "kata": r["word"],
        "kelas_kata": r["pos"],
        "makna": r["meaning"],
        "nuansa": r["nuance"],
        "contoh": r["example"],
        "emosi": r["emotion"],
        "terverifikasi": bool(r["verified"]),
    }


_COLS = "id, word, pos, meaning, nuance, example, keywords, emotion, verified, source"


def all_entries(db):
    with db.cursor() as cur:
        return cur.execute(f"SELECT {_COLS} FROM dictionary_entries ORDER BY word_key ASC").all()


def word_keys(db):
    """Ambil himpunan kata kamus dalam bentuk normalisasi untuk pencocokan token."""
    with db.cursor() as cur:
        rows = cur.execute("SELECT word FROM dictionary_entries").all()
    return {word_key(row["word"]) for row in rows}


def count_entries(db):
    with db.cursor() as cur:
        return cur.execute("SELECT COUNT(*) AS n FROM dictionary_entries").one()["n"]


def list_words(db, q=None, emosi=None, page=1, per_page=30):
    if emosi is not None and emosi not in EMOSI_LIST:
        raise ValueError("emosi tidak valid")
    where, params = ["1 = 1"], []
    if q:
        where.append("word LIKE %s ESCAPE '!'")
        params.append(like_pattern(q))
    if emosi:
        where.append("emotion = %s")
        params.append(emosi)
    clause = " AND ".join(where)
    with db.cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) AS n FROM dictionary_entries WHERE {clause}", params).one()["n"]
        rows = cur.execute(
            f"SELECT {_COLS} FROM dictionary_entries WHERE {clause} ORDER BY word_key ASC LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page],
        ).all()
    return {
        "items": [_brief(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    }


def _relations(cur, entry_id):
    rows = cur.execute(
        "SELECT r.relation_type, e.word, e.nuance, e.meaning FROM dictionary_relations r "
        "JOIN dictionary_entries e ON e.id = r.related_id WHERE r.entry_id = %s ORDER BY e.word_key ASC",
        (entry_id,),
    ).all()
    out = {t: [] for t in REL_TYPES}
    for r in rows:
        out[r["relation_type"]].append({"kata": r["word"], "nuansa": r["nuance"], "makna": r["meaning"]})
    return out


def get_entry(db, kata, with_relations=True):
    """Satu entri (dengan relasi) atau None. Pencocokan tak peka huruf besar dan spasi ganda."""
    key = word_key(kata)
    if not key:
        return None
    with db.cursor() as cur:
        r = cur.execute(f"SELECT {_COLS} FROM dictionary_entries WHERE word_key = %s", (key,)).one()
        if not r:
            return None
        item = _brief(r)
        item["kata_kunci"] = [k for k in (r["keywords"] or "").split() if k]
        item["sumber"] = r["source"]
        if with_relations:
            item["relasi"] = _relations(cur, r["id"])
    return item


def entries_by_emosi(db, emosi, limit=6):
    if emosi not in EMOSI_LIST:
        raise ValueError("emosi tidak valid")
    with db.cursor() as cur:
        rows = cur.execute(
            f"SELECT {_COLS} FROM dictionary_entries WHERE emotion = %s ORDER BY word_key ASC LIMIT %s", (emosi, limit)
        ).all()
    return [_brief(r) for r in rows]


def similar_words(db, kata, n=3):
    """Kata di kamus yang ejaannya mirip (untuk 'Maksudmu ...?')."""
    key = word_key(kata)
    if not key:
        return []
    with db.cursor() as cur:
        words = [r["word"] for r in cur.execute("SELECT word FROM dictionary_entries").all()]
    by_key = {word_key(w): w for w in words}
    return [by_key[k] for k in difflib.get_close_matches(key, list(by_key), n=n, cutoff=0.7)]


# ------------------------------------------------------------------ pencarian deskripsi


def reset_cache():
    _index_cache.clear()


def _doc(r):
    kw = r["keywords"] or ""
    return f"{r['word']} {kw} {kw} {r['meaning']} {r['nuance'] or ''}"


def _build_index(db):
    entries = all_entries(db)
    vec = TfidfVectorizer(tokenizer=_tok, lowercase=False, token_pattern=None, sublinear_tf=True)
    if not entries:
        return {"entries": [], "vec": None, "matrix": None}
    try:
        matrix = vec.fit_transform([_doc(e) for e in entries])
    except ValueError:  # kosakata kosong
        return {"entries": [], "vec": None, "matrix": None}
    return {"entries": entries, "vec": vec, "matrix": matrix}


def _get_index(db):
    key = (db.kind, db.sqlite_path)
    hit = _index_cache.get(key)
    if hit is None or time.time() - hit[0] > INDEX_TTL:
        hit = (time.time(), _build_index(db))
        _index_cache[key] = hit
    return hit[1]


def search_description(db, text, top_k=5, emosi=None, min_score=MIN_SCORE):
    """Kandidat kata untuk sebuah deskripsi: daftar entri + 'skor' (0-1), terurut. Bisa kosong."""
    if emosi is not None and emosi not in EMOSI_LIST:
        raise ValueError("emosi tidak valid")
    idx = _get_index(db)
    if idx["vec"] is None or not _tok(text):
        return []
    q = idx["vec"].transform([text])
    if q.nnz == 0:  # tidak ada satu pun kata deskripsi yang dikenal kamus
        return []
    scores = linear_kernel(q, idx["matrix"])[0]
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], idx["entries"][i]["word"]))
    out = []
    floor = max(min_score, REL_CUTOFF * scores[order[0]])
    for i in order:
        e = idx["entries"][i]
        if scores[i] < floor:
            break
        if emosi and e["emotion"] != emosi:
            continue
        item = _brief(e)
        item["skor"] = round(float(scores[i]), 3)
        out.append(item)
        if len(out) >= top_k:
            break
    return out
