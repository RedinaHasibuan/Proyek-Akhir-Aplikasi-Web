"""Buat lembar pelabelan: sampel puisi beragam dari data/clean/poems.csv.

Contoh:  python make_label_sheet.py --n 250
Hasil: data/labels/label_sheet.csv  (kolom tema/emosi masih kosong)

Sampel diambil dengan kuota kata kunci (romansa, alam, sosial, religius, lain) supaya
setiap tema punya cukup contoh. Akibatnya sebaran di lembar ini BUKAN sebaran asli
korpus, jadi jangan melaporkannya sebagai proporsi tema korpus. Evaluasi memakai F1 per kelas.
"""
import argparse
import csv
import os
import random
from collections import defaultdict

import config
from preprocess import tokenize
from labels import KEYWORDS

QUOTA = {"romansa": 0.25, "alam": 0.20, "sosial": 0.20, "religius": 0.15, "lain": 0.20}
PRIORITY = ["religius", "sosial", "alam", "romansa"]
COLUMNS = [
    "poem_key", "source", "title", "author", "n_words", "body",
    "tema_ai", "emosi_utama_ai", "emosi_lain_ai",
    "tema", "emosi_utama", "emosi_lain", "perlu_tinjau", "label_oleh", "catatan",
]


def bucket_of(body):
    toks = set(tokenize(body, stopwords=False))
    hits = {b: len(toks & words) for b, words in KEYWORDS.items()}
    best = max(hits.values())
    if best == 0:
        return "lain"
    for b in PRIORITY + ["romansa"]:
        if hits[b] == best:
            return b
    return "lain"


def sample_group(rows, n, rng):
    buckets = defaultdict(list)
    for r in rows:
        buckets[bucket_of(r["body"])].append(r)
    for b in buckets.values():
        rng.shuffle(b)
    chosen = []
    for name, frac in QUOTA.items():
        k = min(round(n * frac), len(buckets[name]))
        chosen += buckets[name][:k]
        buckets[name] = buckets[name][k:]
    rest = [r for b in buckets.values() for r in b]
    rng.shuffle(rest)
    chosen += rest[: max(0, n - len(chosen))]
    return chosen[:n]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--poems", default=os.path.join(config.CLEAN_DIR, "poems.csv"))
    ap.add_argument("--out", default=os.path.join(config.LABEL_DIR, "label_sheet.csv"))
    ap.add_argument("--n", type=int, default=250)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-words", type=int, default=15, help="puisi terlalu pendek sulit dilabeli")
    ap.add_argument("--max-words", type=int, default=250, help="puisi terlalu panjang memperlambat pelabelan")
    ap.add_argument("--wikisumber-frac", type=float, default=0.3, help="porsi minimal dari Wikisumber bila tersedia")
    args = ap.parse_args()

    if os.path.exists(args.out):
        raise SystemExit(f"{args.out} sudah ada. Hapus/ganti nama dulu agar label yang sudah dibuat tidak tertimpa.")

    with open(args.poems, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if args.min_words <= int(r["n_words"]) <= args.max_words]
    rng = random.Random(args.seed)

    wiki = [r for r in rows if r["source"] == "wikisumber"]
    other = [r for r in rows if r["source"] != "wikisumber"]
    n_wiki = min(len(wiki), round(args.n * args.wikisumber_frac))
    chosen = sample_group(wiki, n_wiki, rng) + sample_group(other, args.n - n_wiki, rng)
    if len(chosen) < args.n:  # sumber lain kurang -> tambah dari Wikisumber
        used = {r["body_hash"] for r in chosen}
        extra = [r for r in wiki if r["body_hash"] not in used]
        rng.shuffle(extra)
        chosen += extra[: args.n - len(chosen)]
    rng.shuffle(chosen)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in chosen:
            w.writerow({
                "poem_key": f"{r['source']}|{r['source_key']}", "source": r["source"],
                "title": r["title"], "author": r["author"], "n_words": r["n_words"], "body": r["body"],
            })
    by_src = defaultdict(int)
    for r in chosen:
        by_src[r["source"]] += 1
    print(f"{len(chosen)} puisi -> {args.out}  ({dict(by_src)})")
    if len(chosen) < args.n:
        print(f"[!] Hanya {len(chosen)} puisi memenuhi syarat panjang; kurang dari target {args.n}.")


if __name__ == "__main__":
    main()
