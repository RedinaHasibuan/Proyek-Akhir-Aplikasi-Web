"""Muat data Ruang Diksi dari CSV ke MySQL (tabel dictionary_entries dan dictionary_relations).

Contoh:
  python load_diksi.py --init --dry-run     # cek CSV saja, tidak menulis apa pun
  python load_diksi.py --init               # buat tabel (bila belum ada) lalu muat data/diksi/diksi_entries.csv
  python load_diksi.py                      # muat ulang setelah CSV diedit

CSV adalah sumber kebenaran data kurasi: kata yang sudah ada diperbarui, kata baru ditambahkan, dan SEMUA relasi
dibangun ulang dari kolom 'terkait'. Kata yang kamu hapus dari CSV TIDAK otomatis dihapus dari database.
Kolom: kata, kelas_kata, makna, nuansa, contoh, kata_kunci, emosi, terkait, terverifikasi, sumber
  kata_kunci : kata/frasa yang dipakai orang untuk mendeskripsikan kata ini (dipakai pencarian deskripsi)
  emosi      : salah satu label emosi Puitika (boleh kosong)
  terkait    : daftar "jenis:kata" dipisah titik koma, jenis = sinonim | antonim | terkait
  terverifikasi : 1 setelah kamu cek maknanya ke KBBI, selain itu 0
"""
import argparse
import csv
import os
from collections import Counter

import config
from db import Database
from diksi_repo import REL_TYPES, word_key
from labels import EMOSI_LIST

DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "diksi", "diksi_entries.csv")
SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diksi_schema.sql")
REQUIRED = ["kata", "makna"]


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED + ["contoh", "kata_kunci", "emosi", "terkait"] if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"Kolom CSV hilang: {', '.join(missing)}")
        return list(reader)


def validate(rows):
    """Kembalikan (entri_valid, relasi, masalah). Masalah = daftar teks; entri bermasalah dilewati."""
    problems, entries, seen = [], [], {}
    for n, r in enumerate(rows, start=2):  # baris 1 = header
        kata = (r.get("kata") or "").strip()
        key = word_key(kata)
        if not kata:
            problems.append(f"baris {n}: kolom 'kata' kosong")
            continue
        if len(kata) > 100:
            problems.append(f"baris {n}: kata terlalu panjang ({kata[:20]}...)")
            continue
        if key in seen:
            problems.append(f"baris {n}: kata '{kata}' duplikat dengan baris {seen[key]}")
            continue
        if not (r.get("makna") or "").strip():
            problems.append(f"baris {n}: '{kata}' tidak punya makna")
            continue
        emosi = (r.get("emosi") or "").strip()
        if emosi and emosi not in EMOSI_LIST:
            problems.append(f"baris {n}: '{kata}' emosi tidak valid: {emosi!r}")
            continue
        ver = (r.get("terverifikasi") or "0").strip() or "0"
        if ver not in ("0", "1"):
            problems.append(f"baris {n}: '{kata}' terverifikasi harus 0 atau 1")
            continue
        seen[key] = n
        entries.append(
            {
                "word": kata,
                "key": key,
                "pos": (r.get("kelas_kata") or "").strip() or None,
                "meaning": r["makna"].strip(),
                "nuance": (r.get("nuansa") or "").strip() or None,
                "example": (r.get("contoh") or "").strip() or None,
                "keywords": (r.get("kata_kunci") or "").strip() or None,
                "emotion": emosi or None,
                "verified": int(ver),
                "source": (r.get("sumber") or "").strip() or None,
                "_rel": (r.get("terkait") or "").strip(),
                "_row": n,
            }
        )

    keys, relations = {e["key"] for e in entries}, set()
    for e in entries:
        for tok in [t.strip() for t in e["_rel"].split(";") if t.strip()]:
            jenis, _, target = tok.partition(":")
            jenis, tkey = jenis.strip(), word_key(target)
            if jenis not in REL_TYPES or not tkey:
                problems.append(f"baris {e['_row']}: '{e['word']}' relasi tidak valid: {tok!r} (pakai jenis:kata, jenis = {'/'.join(REL_TYPES)})")
            elif tkey not in keys:
                problems.append(f"baris {e['_row']}: '{e['word']}' merujuk ke '{target.strip()}' yang tidak ada di CSV")
            elif tkey == e["key"]:
                problems.append(f"baris {e['_row']}: '{e['word']}' berelasi dengan dirinya sendiri")
            else:
                relations.add((e["key"], tkey, jenis))
                relations.add((tkey, e["key"], jenis))  # relasi dua arah
    return entries, sorted(relations), problems


def apply_schema(db):
    with open(SCHEMA, encoding="utf-8") as f:
        sql = f.read()
    stmts = [s.strip() for s in "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--")).split(";") if s.strip()]
    with db.cursor(commit=True) as cur:
        for s in stmts:
            cur.execute(s)


def load(db, entries, relations):
    """Tulis ke database. Mengembalikan Counter(statistik)."""
    stats = Counter()
    with db.cursor(commit=True) as cur:
        ids = {r["word_key"]: r["id"] for r in cur.execute("SELECT id, word_key FROM dictionary_entries").all()}
        for e in entries:
            vals = (e["word"], e["pos"], e["meaning"], e["nuance"], e["example"], e["keywords"], e["emotion"], e["verified"], e["source"])
            if e["key"] in ids:
                cur.execute(
                    "UPDATE dictionary_entries SET word = %s, pos = %s, meaning = %s, nuance = %s, example = %s, "
                    "keywords = %s, emotion = %s, verified = %s, source = %s WHERE id = %s",
                    vals + (ids[e["key"]],),
                )
                stats["diperbarui"] += 1
            else:
                cur.execute(
                    "INSERT INTO dictionary_entries (word, pos, meaning, nuance, example, keywords, emotion, verified, source, word_key) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    vals + (e["key"],),
                )
                stats["baru"] += 1
        ids = {r["word_key"]: r["id"] for r in cur.execute("SELECT id, word_key FROM dictionary_entries").all()}
        cur.execute("DELETE FROM dictionary_relations")
        for a, b, jenis in relations:
            cur.execute(
                "INSERT INTO dictionary_relations (entry_id, related_id, relation_type) VALUES (%s, %s, %s)",
                (ids[a], ids[b], jenis),
            )
            stats["relasi"] += 1
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--init", action="store_true", help="buat tabel diksi bila belum ada")
    ap.add_argument("--dry-run", action="store_true", help="hanya validasi CSV")
    args = ap.parse_args()

    rows = read_rows(args.csv)
    entries, relations, problems = validate(rows)
    emo = Counter(e["emotion"] or "(umum)" for e in entries)
    print(f"CSV: {len(rows)} baris -> {len(entries)} entri valid, {len(relations)} relasi (dua arah)")
    print("Per emosi: " + ", ".join(f"{k}={v}" for k, v in emo.most_common()))
    print(f"Terverifikasi ke KBBI: {sum(e['verified'] for e in entries)} dari {len(entries)}")
    for p in problems:
        print("  !", p)
    if problems:
        print(f"{len(problems)} masalah di atas dilewati. Perbaiki CSV bila perlu.")
    if args.dry_run:
        return
    db = Database.mysql()
    if args.init:
        apply_schema(db)
        print("Tabel diksi siap.")
    stats = load(db, entries, relations)
    print(f"Database {config.DB_NAME}: {stats['baru']} kata baru, {stats['diperbarui']} diperbarui, {stats['relasi']} relasi.")


if __name__ == "__main__":
    main()
