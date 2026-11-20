"""Gabungkan dan bersihkan data mentah menjadi satu file: data/clean/poems.csv

Sumber:
  - data/raw/wikisumber.jsonl  (hasil crawl_wikisumber.py)  -> boleh tampil di Perpustakaan
  - data/raw/id_puisi.csv      (diunduh otomatis bila belum ada) -> hanya eksperimen internal

Contoh:
  python build_dataset.py
  python build_dataset.py --inspect 5      # tampilkan 5 contoh hasil parsing Wikisumber
  python build_dataset.py --no-idpuisi     # hanya Wikisumber
"""
import argparse
import csv
import json
import os
import random
import statistics
import sys
from collections import Counter

import config
import textclean as tc

IDPUISI_URL = "https://raw.githubusercontent.com/ilhamfp/puisi-pantun-generator/main/data/puisi.csv"
IDPUISI_LICENSE = "MIT (repo dataset); hak cipta tiap puisi tetap pada penulisnya"
FIELDS = [
    "source", "source_key", "title", "author", "body", "source_url", "license",
    "in_public_library", "body_hash", "n_lines", "n_stanzas", "n_words",
]


def read_wikisumber(path, dropped, inspect_n=0):
    if not os.path.exists(path):
        print(f"[!] {path} belum ada. Jalankan crawl_wikisumber.py dulu (atau pakai --no-wikisumber).")
        return []
    rows, samples = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            parsed = tc.parse_wikitext(rec.get("wikitext", ""))
            if parsed["is_redirect"]:
                dropped["wikisumber:redirect"] += 1
                continue
            body = parsed["body"]
            ok, reason = tc.is_probably_poem(body)
            if not ok:
                dropped[f"wikisumber:{reason}"] += 1
                continue
            n_lines, n_stanzas, n_words = tc.text_stats(body)
            row = {
                "source": "wikisumber",
                "source_key": rec["title"],
                "title": tc.display_title(rec["title"]),
                "author": parsed["author"],
                "body": body,
                "source_url": rec.get("url"),
                "license": parsed["license"]
                or "tidak terdeteksi otomatis (Wikisumber hanya memuat domain publik/lisensi bebas)",
                "in_public_library": 1,
                "body_hash": tc.body_hash(body),
                "n_lines": n_lines,
                "n_stanzas": n_stanzas,
                "n_words": n_words,
            }
            rows.append(row)
            samples.append(row)
    if inspect_n:
        print("=" * 70)
        for row in random.sample(samples, min(inspect_n, len(samples))):
            print(f"JUDUL : {row['title']}\nPENYAIR: {row['author']}\nLISENSI: {row['license']}\nURL   : {row['source_url']}")
            print("ISI   :\n" + row["body"][:400])
            print("-" * 70)
    return rows


def download_idpuisi(path):
    import requests

    print(f"Mengunduh ID Puisi dari GitHub -> {path}")
    resp = requests.get(IDPUISI_URL, headers={"User-Agent": config.USER_AGENT}, timeout=60)
    resp.raise_for_status()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(resp.content)


def read_idpuisi(path, dropped):
    if not os.path.exists(path):
        download_idpuisi(path)
    csv.field_size_limit(10**8)
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=",", quoting=csv.QUOTE_ALL)
        next(reader, None)  # lewati header
        for r in reader:
            if len(r) < 4:
                dropped["idpuisi:baris_rusak"] += 1
                continue
            # urutan kolom di dataset asli: puisi, title, author, puisi_with_header
            cleaned = tc.clean_idpuisi_row(r[0], r[1], r[2], r[3])
            if not cleaned["title"]:
                dropped["idpuisi:tanpa_judul"] += 1
                continue
            body = cleaned["body"]
            ok, reason = tc.is_probably_poem(body)
            if not ok:
                dropped[f"idpuisi:{reason}"] += 1
                continue
            h = tc.body_hash(body)
            n_lines, n_stanzas, n_words = tc.text_stats(body)
            rows.append({
                "source": "idpuisi",
                "source_key": "idpuisi:" + h[:16],
                "title": tc.display_title(cleaned["title"]),
                "author": cleaned["author"],
                "body": body,
                "source_url": None,
                "license": IDPUISI_LICENSE,
                "in_public_library": 0,
                "body_hash": h,
                "n_lines": n_lines,
                "n_stanzas": n_stanzas,
                "n_words": n_words,
            })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wikisumber", default=os.path.join(config.RAW_DIR, "wikisumber.jsonl"))
    ap.add_argument("--idpuisi", default=os.path.join(config.RAW_DIR, "id_puisi.csv"))
    ap.add_argument("--out", default=os.path.join(config.CLEAN_DIR, "poems.csv"))
    ap.add_argument("--no-wikisumber", action="store_true")
    ap.add_argument("--no-idpuisi", action="store_true")
    ap.add_argument("--inspect", type=int, default=0, help="tampilkan N contoh hasil parsing Wikisumber")
    args = ap.parse_args()

    dropped = Counter()
    rows = []
    if not args.no_wikisumber:
        rows += read_wikisumber(args.wikisumber, dropped, args.inspect)
    if not args.no_idpuisi:
        rows += read_idpuisi(args.idpuisi, dropped)

    # Deduplikasi berdasarkan isi; Wikisumber diproses lebih dulu jadi menang.
    seen, unique = set(), []
    for r in rows:
        if r["body_hash"] in seen:
            dropped[f"{r['source']}:duplikat"] += 1
            continue
        seen.add(r["body_hash"])
        unique.append(r)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(unique)

    # ---- ringkasan
    print("\n=== RINGKASAN ===")
    by_source = Counter(r["source"] for r in unique)
    for src, n in by_source.items():
        print(f"{src:12s}: {n} puisi")
    print(f"TOTAL       : {len(unique)} puisi -> {args.out}")
    if dropped:
        print("\nDibuang:")
        for k, n in sorted(dropped.items()):
            print(f"  {k}: {n}")
    no_author = sum(1 for r in unique if not r["author"])
    print(f"\nPuisi tanpa penyair: {no_author} ({no_author / max(len(unique), 1):.0%})")
    words = [r["n_words"] for r in unique]
    if len(words) >= 4:
        q = statistics.quantiles(words, n=4)
        print(f"Jumlah kata per puisi: min={min(words)}, Q1={q[0]:.0f}, median={q[1]:.0f}, Q3={q[2]:.0f}, max={max(words)}")
    top = Counter(r["author"] for r in unique if r["author"]).most_common(10)
    if top:
        print("Penyair terbanyak: " + "; ".join(f"{a} ({n})" for a, n in top))


if __name__ == "__main__":
    sys.exit(main())
