"""Statistik kata atas korpus puisi PUBLIK (in_public_library = 1), dengan cache sementara.

Dipakai Makna Puisi (kata menonjol = sering di puisi ini, jarang di korpus) dan Dashboard (frekuensi kata).
Puisi ID Puisi dan draf pengguna tidak pernah ikut dihitung.
"""
import time
from collections import Counter

from preprocess import tokenize

TTL = 600  # detik
_cache = {}


def reset_cache():
    _cache.clear()


_CLITICS = ("ku", "mu", "nya")
_NOT_CLITIC = {"bangku", "pangku", "rangku", "tangku", "sangku", "lengku"}


def strip_clitic(w):
    """hatiku -> hati, menunggumu -> menunggu. Hanya bila sisanya minimal 4 huruf (tamu, buku, hanya tidak terpotong)."""
    if w in _NOT_CLITIC:
        return w
    for c in _CLITICS:
        if w.endswith(c) and len(w) - len(c) >= 4:
            return w[: -len(c)]
    return w


def corpus_words(text):
    return [strip_clitic(t) for t in tokenize(text, stopwords=True, min_len=3)]


def corpus_stats(db):
    """{'n_docs': int, 'df': Counter(kata -> jumlah puisi), 'tf': Counter(kata -> jumlah kemunculan)}"""
    key = (db.kind, db.sqlite_path)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    df, tf, n = Counter(), Counter(), 0
    with db.cursor() as cur:
        for r in cur.execute("SELECT body FROM poems WHERE in_public_library = 1").all():
            toks = corpus_words(r["body"])
            n += 1
            tf.update(toks)
            df.update(set(toks))
    stats = {"n_docs": n, "df": df, "tf": tf}
    _cache[key] = (time.time(), stats)
    return stats
