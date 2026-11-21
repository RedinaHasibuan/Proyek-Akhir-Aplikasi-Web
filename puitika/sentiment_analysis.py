"""Sentiment analysis lexicon-based untuk fitur Makna Puisi Puitika.

Metode awal: menghitung kata positif/negatif, memperhatikan negasi dan intensifier sederhana.
Ini adalah alat bantu eksplorasi, bukan penentu makna atau emosi sastra secara mutlak. Score bukan probabilitas/confidence.

CLI:
    python sentiment_analysis.py --text "Aku bersyukur melihat cahaya pagi"
    python sentiment_analysis.py --file puisi.txt

Integrasi Flask:
    from sentiment_analysis import analyze_sentiment
    hasil = analyze_sentiment(teks_puisi)
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from typing import Dict, List

ANALYZER_VERSION = "lexicon-id-puisi-0.1"

# Kamus awal yang transparan dan dapat dikembangkan setelah pemeriksaan contoh puisi.
# Hindari kata yang sangat ambigu (mis. rindu, senja, hujan, pasrah) sebagai polaritas tetap.
POSITIVE_LEXICON = {
    "bahagia": 1.5, "senang": 1.3, "gembira": 1.5, "ceria": 1.3,
    "riang": 1.3, "sukacita": 1.5, "syukur": 1.4, "bersyukur": 1.4,
    "senyum": 1.0, "tersenyum": 1.2, "tawa": 1.0, "tertawa": 1.1,
    "hangat": 0.8, "kasih": 1.0, "cinta": 0.9, "sayang": 0.9,
    "damai": 1.2, "tenteram": 1.2, "indah": 0.8, "harapan": 1.0,
    "harap": 0.8, "optimis": 1.3, "cahaya": 0.5, "fajar": 0.4,
    "pulih": 1.0, "sembuh": 1.0, "merdeka": 0.8, "bebas": 0.7,
    "berkah": 1.0, "rahmat": 0.8, "nikmat": 0.8, "berhasil": 1.0,
    "sukses": 1.1, "kagum": 0.7, "bangga": 1.0, "memeluk": 0.6,
}

NEGATIVE_LEXICON = {
    "sedih": 1.4, "duka": 1.4, "kehilangan": 1.4, "kecewa": 1.3,
    "luka": 1.2, "pedih": 1.3, "tangis": 1.1, "menangis": 1.2,
    "derita": 1.4, "nestapa": 1.4, "muram": 1.1, "sepi": 0.8,
    "sakit": 1.0, "benci": 1.4, "marah": 1.2, "amarah": 1.4,
    "geram": 1.3, "murka": 1.4, "hancur": 1.4, "hilang": 0.8,
    "gelap": 0.7, "pahit": 0.8, "takut": 1.1, "cemas": 1.2,
    "gelisah": 1.1, "sengsara": 1.5, "terpuruk": 1.3, "putusasa": 1.5,
    "menyesal": 1.1, "tersiksa": 1.4, "siksa": 1.3, "runtuh": 1.0,
    "berduka": 1.4, "terluka": 1.2, "kesepian": 1.1, "menderita": 1.4,
}

NEGATIONS = {"tidak", "tak", "bukan", "belum", "tiada", "tanpa"}
INTENSIFIERS = {
    "sangat": 1.5, "amat": 1.5, "begitu": 1.25, "terlalu": 1.35,
    "sungguh": 1.35, "amatlah": 1.5, "benar-benar": 1.35,
}
DAMPENERS = {"agak": 0.75, "sedikit": 0.7, "kurang": 0.7, "hampir": 0.75}
TOKEN_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)?", re.UNICODE)
STANZA_RE = re.compile(r"\n\s*\n+")


def _tokens(text: str) -> List[str]:
    return TOKEN_RE.findall((text or "").casefold())


def _analyze_segment(text: str) -> Dict:
    tokens = _tokens(text)
    positive_score = 0.0
    negative_score = 0.0
    positive_terms = Counter()
    negative_terms = Counter()
    matched = 0

    for i, token in enumerate(tokens):
        if token in POSITIVE_LEXICON:
            value = POSITIVE_LEXICON[token]
            base_polarity = "positif"
        elif token in NEGATIVE_LEXICON:
            value = NEGATIVE_LEXICON[token]
            base_polarity = "negatif"
        else:
            continue

        matched += 1
        previous = tokens[max(0, i - 3):i]
        negated = any(word in NEGATIONS for word in previous)
        multiplier = 1.0
        for word in previous[-2:]:
            if word in INTENSIFIERS:
                multiplier = max(multiplier, INTENSIFIERS[word])
            elif word in DAMPENERS:
                multiplier = min(multiplier, DAMPENERS[word])

        value *= multiplier
        effective = base_polarity
        if negated:
            effective = "negatif" if base_polarity == "positif" else "positif"

        if effective == "positif":
            positive_score += value
            positive_terms[token] += 1
        else:
            negative_score += value
            negative_terms[token] += 1

    total_sentiment = positive_score + negative_score
    score = ((positive_score - negative_score) / total_sentiment) if total_sentiment else 0.0

    if total_sentiment == 0:
        # Tidak ada kata yang dikenali bukan bukti bahwa teks benar-benar netral.
        polarity = "tidak_terdeteksi"
    elif positive_score >= 0.8 and negative_score >= 0.8 and abs(score) <= 0.35:
        polarity = "campuran"
    elif score >= 0.20:
        polarity = "positif"
    elif score <= -0.20:
        polarity = "negatif"
    else:
        polarity = "netral"

    evidence = {
        "positif": [{"kata": word, "jumlah": count} for word, count in positive_terms.most_common()],
        "negatif": [{"kata": word, "jumlah": count} for word, count in negative_terms.most_common()],
    }
    return {
        "polarity": polarity,
        "score": round(score, 4),
        "positive_score": round(positive_score, 4),
        "negative_score": round(negative_score, 4),
        "token_count": len(tokens),
        "matched_token_count": matched,
        "coverage": round(matched / len(tokens), 4) if tokens else 0.0,
        "has_lexicon_evidence": matched > 0,
        "evidence": evidence,
    }


def analyze_sentiment(text: str, analyze_stanzas: bool = True) -> Dict:
    """Analisis polaritas teks/puisi dan, opsional, polaritas per bait.

    Label keluaran: positif, negatif, netral, campuran, atau tidak_terdeteksi.
    tidak_terdeteksi berarti kamus tidak menemukan bukti polaritas; bukan berarti netral.
    Score berada di rentang -1..1. Nilai positif cenderung positif, negatif cenderung negatif.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Teks puisi tidak boleh kosong.")

    result = _analyze_segment(text)
    result["method"] = "lexicon"
    result["analyzer_version"] = ANALYZER_VERSION

    if analyze_stanzas:
        stanzas = [part.strip() for part in STANZA_RE.split(text.strip()) if part.strip()]
        result["stanzas"] = [
            {"stanza": index + 1, **_analyze_segment(stanza)}
            for index, stanza in enumerate(stanzas)
        ]
    else:
        result["stanzas"] = []
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="teks puisi langsung")
    parser.add_argument("--file", help="lokasi file teks puisi")
    parser.add_argument("--no-stanzas", action="store_true", help="lewati analisis per bait")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            text = handle.read()
    elif args.text:
        text = args.text
    else:
        parser.error("Berikan --text atau --file")

    result = analyze_sentiment(text, analyze_stanzas=not args.no_stanzas)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Catatan: hasil lexicon-based adalah indikasi polaritas, bukan tafsir makna atau diagnosis emosi.")


if __name__ == "__main__":
    main()
