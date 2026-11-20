"""Muat data/clean/poems.csv ke MySQL.

Contoh:
  python load_to_db.py --init     # buat database + tabel (schema.sql), lalu muat data
  python load_to_db.py            # muat saja (aman dijalankan ulang; data yang sudah ada dilewati)
"""
import argparse
import csv
import os

import pymysql

import config
import textclean as tc


def connect(with_db=True):
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME if with_db else None,
        charset="utf8mb4",
        autocommit=False,
    )


def run_schema(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if not ln.strip().startswith("--")]
    statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
    conn = connect(with_db=False)
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    print(f"Skema dijalankan ({len(statements)} pernyataan).")


def load_poems(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"Membaca {len(rows)} puisi dari {csv_path}")

    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT source, source_key, body_hash FROM poems")
            existing_keys, existing_hashes = set(), set()
            for src, key, h in cur.fetchall():
                existing_keys.add((src, key))
                existing_hashes.add(h)

            # penyair
            poets = {}
            for r in rows:
                if r["author"]:
                    poets.setdefault(tc.author_key(r["author"]), r["author"])
            if poets:
                cur.executemany(
                    "INSERT IGNORE INTO poets (name, name_key) VALUES (%s, %s)",
                    [(name, key) for key, name in poets.items()],
                )
            cur.execute("SELECT id, name_key FROM poets")
            poet_id = {key: pid for pid, key in cur.fetchall()}

            to_insert, skipped = [], 0
            for r in rows:
                if (r["source"], r["source_key"]) in existing_keys or r["body_hash"] in existing_hashes:
                    skipped += 1
                    continue
                pid = poet_id.get(tc.author_key(r["author"])) if r["author"] else None
                to_insert.append((
                    pid, r["title"][:200], r["body"], r["source"], r["source_key"][:255],
                    (r["source_url"] or None), (r["license"] or None)[:255] if r["license"] else None,
                    int(r["in_public_library"]), r["body_hash"],
                    int(r["n_lines"]), int(r["n_stanzas"]), int(r["n_words"]),
                ))
                existing_hashes.add(r["body_hash"])
            if to_insert:
                cur.executemany(
                    "INSERT INTO poems (poet_id, title, body, source, source_key, source_url, license,"
                    " in_public_library, body_hash, n_lines, n_stanzas, n_words)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    to_insert,
                )
        conn.commit()
        print(f"Dimasukkan: {len(to_insert)} puisi baru; dilewati (sudah ada): {skipped}")

        with conn.cursor() as cur:
            cur.execute("SELECT source, in_public_library, COUNT(*) FROM poems GROUP BY source, in_public_library")
            print("\nIsi tabel poems sekarang:")
            for src, pub, n in cur.fetchall():
                print(f"  {src:11s} publik={pub}: {n}")
            cur.execute("SELECT COUNT(*) FROM poets")
            print(f"  penyair unik: {cur.fetchone()[0]}")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", action="store_true", help="jalankan schema.sql dulu")
    ap.add_argument("--csv", default=os.path.join(config.CLEAN_DIR, "poems.csv"))
    ap.add_argument("--schema", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql"))
    args = ap.parse_args()

    if args.init:
        run_schema(args.schema)
    load_poems(args.csv)


if __name__ == "__main__":
    main()
