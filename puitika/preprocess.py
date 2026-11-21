"""Praproses teks puisi untuk model dan eksplorasi.

Langkah: case folding -> rapikan huruf berulang -> tokenisasi -> (opsional) stopword -> (opsional) stemming.
Kata ganti seperti aku/kau/kamu/-mu/-ku SENGAJA tidak dibuang dari stopword, dan kata
negasi (tak, tidak, bukan, belum) dipertahankan, karena keduanya membawa sinyal emosi di puisi.
Stemming butuh Sastrawi (pip install Sastrawi) dan lambat; default mati, bandingkan lewat train_model.py.
"""
import re
import warnings

STOPWORDS = frozenset(
    """
    yang dan di ke dari pada untuk dengan ini itu adalah akan atau juga ada dalam oleh karena
    sebagai bahwa saja lagi telah sudah masih agar supaya serta namun tetapi tapi jika bila
    ketika saat sampai hingga sebuah suatu para setiap hanya pun lah kah nya yg dgn utk dlm sdh
    """.split()
)

_TOKEN = re.compile(r"[a-zà-ÿ]+(?:-[a-zà-ÿ]+)?")
_REPEAT = re.compile(r"(.)\1{2,}")
_stemmer = None
_stemmer_failed = False


def _get_stemmer():
    global _stemmer, _stemmer_failed
    if _stemmer is None and not _stemmer_failed:
        try:
            from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

            _stemmer = StemmerFactory().create_stemmer()
        except ImportError:
            _stemmer_failed = True
            warnings.warn("Sastrawi belum terpasang; stemming dilewati (pip install Sastrawi).")
    return _stemmer


def tokenize(text, stopwords=True, stem=False, min_len=2):
    """Kembalikan daftar token. Fungsi tingkat modul agar model bisa di-pickle."""
    text = _REPEAT.sub(r"\1\1", (text or "").casefold())
    tokens = _TOKEN.findall(text)
    if stem:
        stemmer = _get_stemmer()
        if stemmer is not None:
            tokens = [stemmer.stem(t) for t in tokens]
    return [t for t in tokens if len(t) >= min_len and not (stopwords and t in STOPWORDS)]
