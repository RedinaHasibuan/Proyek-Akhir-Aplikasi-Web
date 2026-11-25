"""Ukur kualitas pencarian deskripsi Ruang Diksi dengan daftar query uji (CSV: deskripsi,kata_diharapkan).

Contoh:  python eval_diksi.py                 # data/diksi/eval_queries.csv ke database MySQL
         python eval_diksi.py --csv queriku.csv --show-misses
PENTING untuk laporan: query bawaan ditulis oleh pembuat kamus, jadi hasilnya CENDERUNG TERLALU BAGUS.
Tambahkan 20+ query yang ditulis orang lain (teman/dosen) tanpa melihat isi kamus, lalu laporkan angka dari query itu.
"""
import argparse
import csv
import os

from db import Database
import diksi_repo as dr

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "diksi", "eval_queries.csv")


def evaluate(db, rows, top_k=5):
    res, top1, top3, topk = [], 0, 0, 0
    for r in rows:
        want = dr.word_key(r["kata_diharapkan"])
        got = [dr.word_key(h["kata"]) for h in dr.search_description(db, r["deskripsi"], top_k=top_k)]
        rank = got.index(want) + 1 if want in got else None
        top1 += rank == 1
        top3 += rank is not None and rank <= 3
        topk += rank is not None
        res.append((r["deskripsi"], r["kata_diharapkan"], rank, got[:3]))
    n = len(rows)
    return {"n": n, "top1": top1 / n, "top3": top3 / n, f"top{top_k}": topk / n}, res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT)
    ap.add_argument("--show-misses", action="store_true")
    args = ap.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    summary, res = evaluate(Database.mysql(), rows)
    print(f"{summary['n']} query | top-1 {summary['top1']:.0%} | top-3 {summary['top3']:.0%} | top-5 {summary['top5']:.0%}")
    if args.show_misses:
        for desc, want, rank, got in res:
            if rank != 1:
                print(f"  - '{desc}' -> diharapkan {want}, peringkat {rank}, teratas: {got}")


if __name__ == "__main__":
    main()
