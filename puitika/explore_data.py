"""Eksplorasi korpus: ukuran, kosakata, kata terbanyak, penyair, dan kelayakan label.

Contoh:  python explore_data.py
Hasil dicetak dan disimpan di reports/explore.txt + reports/word_freq.csv
(bahan untuk bab "Eksplorasi Data" di laporan dan slide).
"""
import argparse
import csv
import os
import random
import statistics
from collections import Counter

import config
from labels import KEYWORDS
from preprocess import tokenize


def quantiles(values):
    if len(values) < 4:
        return f"min={min(values)} max={max(values)}"
    q = statistics.quantiles(values, n=4)
    return f"min={min(values)} Q1={q[0]:.0f} median={q[1]:.0f} Q3={q[2]:.0f} max={max(values)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--poems", default=os.path.join(config.CLEAN_DIR, "poems.csv"))
    ap.add_argument("--report-dir", default=config.REPORT_DIR)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    with open(args.poems, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("poems.csv kosong. Jalankan build_dataset.py dulu.")

    out = []

    def say(s=""):
        print(s)
        out.append(s)

    say(f"=== EKSPLORASI DATA ({len(rows)} puisi) ===")
    by_source = {}
    for r in rows:
        by_source.setdefault(r["source"], []).append(r)

    say("\n-- Ukuran per sumber --")
    for src, rs in by_source.items():
        words = [int(r["n_words"]) for r in rs]
        lines = [int(r["n_lines"]) for r in rs]
        stanzas = [int(r["n_stanzas"]) for r in rs]
        no_author = sum(1 for r in rs if not r["author"])
        say(f"{src}: {len(rs)} puisi | tanpa penyair {no_author} ({no_author / len(rs):.0%})")
        say(f"   kata/puisi  : {quantiles(words)}")
        say(f"   baris/puisi : {quantiles(lines)}")
        say(f"   bait/puisi  : {quantiles(stanzas)}")

    say("\n-- Penyair terbanyak --")
    for src, rs in by_source.items():
        top = Counter(r["author"] for r in rs if r["author"]).most_common(10)
        say(f"{src}: " + "; ".join(f"{a} ({n})" for a, n in top))

    # kosakata
    tok_all = Counter()
    doc_freq = Counter()
    tok_src = {src: Counter() for src in by_source}
    doc_tokens = []
    for r in rows:
        toks = tokenize(r["body"])
        doc_tokens.append(toks)
        tok_all.update(toks)
        doc_freq.update(set(toks))
        tok_src[r["source"]].update(toks)

    total_tokens = sum(tok_all.values())
    hapax = sum(1 for c in tok_all.values() if c == 1)
    say("\n-- Kosakata (setelah praproses + stopword) --")
    say(f"total token: {total_tokens} | kosakata unik: {len(tok_all)} | muncul sekali: {hapax} ({hapax / len(tok_all):.0%})")
    say("30 kata terbanyak (semua sumber):")
    say("   " + ", ".join(f"{w}({c})" for w, c in tok_all.most_common(30)))
    for src, cnt in tok_src.items():
        say(f"20 kata terbanyak [{src}]: " + ", ".join(f"{w}({c})" for w, c in cnt.most_common(20)))

    # kelayakan label: berapa puisi memuat kata kunci tiap tema (indikasi kasar)
    say("\n-- Indikasi sebaran tema (puisi yang memuat >=1 kata kunci; BUKAN label, hanya petunjuk) --")
    for bucket, words in KEYWORDS.items():
        n = sum(1 for toks in doc_tokens if words & set(toks))
        say(f"{bucket:10s}: {n} puisi ({n / len(rows):.0%})")
    say("Jika sebuah tema hanya muncul pada <5% puisi, pertimbangkan menggabungkannya atau mengambil sampel tambahan.")

    say("\n-- 3 puisi acak (potongan) --")
    rng = random.Random(args.seed)
    for r in rng.sample(rows, min(3, len(rows))):
        say(f"[{r['source']}] {r['title']} - {r['author'] or '?'}")
        say("   " + r["body"][:200].replace("\n", " / "))

    os.makedirs(args.report_dir, exist_ok=True)
    with open(os.path.join(args.report_dir, "explore.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    with open(os.path.join(args.report_dir, "word_freq.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["token", "count", "doc_freq"])
        for tok, c in tok_all.most_common():
            w.writerow([tok, c, doc_freq[tok]])
    print(f"\nTersimpan: {args.report_dir}/explore.txt dan word_freq.csv")


if __name__ == "__main__":
    main()
