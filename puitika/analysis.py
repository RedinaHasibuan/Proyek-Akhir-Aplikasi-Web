"""Analisis statistik puisi, saran klasifikasi tema, dan analisis sentimen.

PENTING (untuk laporan/presentasi): ini analisis permukaan (jumlah kata, kata dominan, bunyi akhir baris),
BUKAN pemahaman makna. Fitur "Makna Puisi" yang sebenarnya belum dibuat.
"""
from collections import Counter
from sentiment_analysis import analyze_sentiment
import config
import predict
from preprocess import tokenize

MAX_CHARS = 20000  # batas panjang teks yang dianalisis (puisi normal jauh di bawah ini)
VOWELS = set("aiueo")


def clean_lines(text):
    """Baris tidak kosong, tanpa baris penuh titik (artefak Wikisumber), spasi dirapikan."""
    out = []
    for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        ln = " ".join(ln.split())
        if ln and set(ln) != {"."}:
            out.append(ln)
    return out


def count_stanzas(text):
    """Jumlah bait = blok yang dipisah baris kosong. Bila setiap baris dipisah baris kosong
    (artefak format), seluruh puisi dianggap satu bait."""
    blocks = [b for b in (text or "").replace("\r\n", "\n").split("\n\n") if any(l.strip() for l in b.split("\n"))]
    lines = clean_lines(text)
    if len(blocks) >= len(lines) and len(lines) > 3:
        return 1
    return max(len(blocks), 1) if lines else 0


def line_ending(line):
    """Bunyi akhir baris: dari vokal terakhir sampai akhir kata terakhir (minimal 2 huruf bila ada)."""
    toks = tokenize(line, stopwords=False, min_len=1)
    if not toks:
        return ""
    w = toks[-1].replace("-", "")
    idx = max((i for i, ch in enumerate(w) if ch in VOWELS), default=None)
    if idx is None:
        return w[-2:]
    # ambil dari vokal sebelum vokal terakhir bila kata cukup panjang, agar "-an", "-kan" tidak terlalu longgar
    start = idx - 1 if idx >= 1 and w[idx - 1] not in VOWELS else idx
    return w[start:]


def rhyme_info(lines):
    """Skema rima akhir (a, b, c, ...) dan persentase baris yang bunyi akhirnya dipakai baris lain."""
    endings = [line_ending(l) for l in lines]
    counts = Counter(e for e in endings if e)
    letters, scheme = {}, []
    for e in endings:
        if not e:
            scheme.append("-")
            continue
        if counts[e] > 1:
            letters.setdefault(e, chr(ord("a") + len(letters) % 26))
            scheme.append(letters[e])
        else:
            scheme.append("-")  # bunyi akhir tidak berulang: tidak berima dengan baris lain
    rhymed = sum(1 for s in scheme if s != "-")
    return {
        "skema": "".join(scheme),
        "persen_baris_berima": round(100 * rhymed / len(lines), 1) if lines else 0.0,
        "catatan": "Pendekatan kasar berdasarkan huruf akhir kata; bukan analisis rima yang sebenarnya.",
    }


def stats(text, top_n=10):
    lines = clean_lines(text)
    words_all = tokenize(text, stopwords=False, min_len=1)
    words = tokenize(text, stopwords=True)
    freq = Counter(words)
    n_words = len(words_all)
    return {
        "n_baris": len(lines),
        "n_bait": count_stanzas(text),
        "n_kata": n_words,
        "n_kata_unik": len(set(words_all)),
        "keragaman_kata": round(len(set(words_all)) / n_words, 3) if n_words else 0.0,
        "rata_kata_per_baris": round(n_words / len(lines), 1) if lines else 0.0,
        "kata_dominan": [{"kata": w, "jumlah": c} for w, c in freq.most_common(top_n) if c > 1 or len(freq) <= top_n],
        "rima": rhyme_info(lines),
    }



def model_suggestions(text, model_dir=config.MODEL_DIR):
    """Prediksi tema puisi menggunakan model klasifikasi tema."""
    try:
        result = predict.suggest(text, model_dir=model_dir)

        return {
            "tema": result.get("tema"),
            "error": None
        }

    except Exception as e:
        return {
            "tema": None,
            "error": (
                f"Model tema gagal dimuat ({type(e).__name__}). "
                "Periksa model atau latih ulang dengan train_model.py."
            )
        }


def analyze(text, model_dir=config.MODEL_DIR):
    """Analisis statistik, saran tema, dan sentimen puisi."""

    return {
        "statistik": stats(text),
        "saran_model": model_suggestions(text, model_dir),
        "sentimen": analyze_sentiment(text),
        "catatan": (
            "Hasil analisis sentimen dan prediksi tema merupakan "
            "alat bantu eksplorasi, bukan penentu mutlak makna puisi."
        )
    }
