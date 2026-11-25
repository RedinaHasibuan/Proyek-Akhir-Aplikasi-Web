"""Isi kolom poets.period dari data/periode/penyair_periode.csv (nama,periode,catatan).

Contoh:  python load_periode.py            # tulis ke database
         python load_periode.py --dry-run  # hanya laporan
Periodisasi sastra Indonesia tidak baku (satu penyair bisa masuk dua angkatan menurut sumber berbeda).
CSV bawaan hanya berisi penyair yang umum disepakati; SISANYA KAMU ISI sendiri sesuai buku/dosenmu
dan cantumkan sumbernya di laporan. Penyair publik yang belum punya periode dicetak di akhir (urut jumlah puisi).
Baris dengan periode kosong dilewati. Aman dijalankan berulang.
"""
import argparse
import csv
import os

from db import Database, ensure_schema
from diksi_repo import word_key

DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "periode", "penyair_periode.csv")


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f)]


def apply(db, rows, dry_run=False):
    """Kembalikan {'diperbarui': n, 'tidak_ditemukan': [nama], 'tanpa_periode': [(nama, jumlah_puisi)]}."""
    res = {"diperbarui": 0, "tidak_ditemukan": [], "tanpa_periode": []}
    with db.cursor(commit=not dry_run) as cur:
        poets = {r["name_key"]: r["id"] for r in cur.execute("SELECT id, name_key FROM poets").all()}
        for r in rows:
            nama, periode = (r.get("nama") or "").strip(), (r.get("periode") or "").strip()
            if not nama or not periode:
                continue
            if len(periode) > 60:
                raise SystemExit(f"Periode terlalu panjang (maks 60 karakter): {periode[:30]}...")
            pid = poets.get(word_key(nama))
            if pid is None:
                res["tidak_ditemukan"].append(nama)
                continue
            if not dry_run:
                cur.execute("UPDATE poets SET period = %s WHERE id = %s", (periode, pid))
            res["diperbarui"] += 1
        rows = cur.execute(
            "SELECT t.name AS name, COUNT(*) AS n FROM poets t JOIN poems p ON p.poet_id = t.id "
            "WHERE p.in_public_library = 1 AND (t.period IS NULL OR t.period = '') GROUP BY t.id, t.name ORDER BY n DESC, t.name ASC"
        ).all()
        res["tanpa_periode"] = [(r["name"], r["n"]) for r in rows]
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = Database.mysql()
    ensure_schema(db)
    res = apply(db, read_rows(args.csv), args.dry_run)
    print(f"{'(dry-run) ' if args.dry_run else ''}periode diisi untuk {res['diperbarui']} penyair")
    if res["tidak_ditemukan"]:
        print("Tidak ada di database (ejaan nama harus sama dengan tabel poets): " + ", ".join(res["tidak_ditemukan"]))
    if res["tanpa_periode"]:
        print(f"\nPenyair publik TANPA periode ({len(res['tanpa_periode'])}); isi di CSV lalu jalankan ulang:")
        for name, n in res["tanpa_periode"][:25]:
            print(f"  {n:4d} puisi  {name}")
    if args.dry_run:
        print("\n(dry-run: daftar 'tanpa periode' belum memperhitungkan isian CSV yang akan ditulis)")


if __name__ == "__main__":
    main()
