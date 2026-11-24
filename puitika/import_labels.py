
"""Impor label tema hasil anotasi ke database MySQL.

Contoh:
    python import_labels.py
    python import_labels.py --apply
    python import_labels.py --apply --replace

Default hanya melakukan pemeriksaan (dry-run).
Label emosi lama tidak diubah.
"""

import argparse
import csv
from collections import Counter
from pathlib import Path

import config
from db import Database
from labels import TEMA_LIST


def load_label_rows(csv_path):
    """Membaca dan memvalidasi CSV anotasi."""

    path = Path(csv_path)

    if not path.is_file():
        raise FileNotFoundError(f"File label tidak ditemukan: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required = {
            "poem_key",
            "source",
            "tema",
            "label_oleh",
        }

        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Kolom CSV tidak lengkap: {', '.join(sorted(missing))}"
            )

        rows = list(reader)

    records = []
    skipped = 0
    seen = set()
    provenance_counts = Counter()

    for row in rows:
        key = (row.get("poem_key") or "").strip()
        source = (row.get("source") or "").strip()
        label = (row.get("tema") or "").strip()
        label_source = (row.get("label_oleh") or "").strip()

        if not key or not source:
            raise ValueError("Ditemukan poem_key atau source kosong.")

        parts = key.split("|", 1)

        if len(parts) != 2 or parts[0] != source:
            raise ValueError(f"Format poem_key tidak sesuai: {key}")

        source_key = parts[1].strip()

        if not source_key:
            raise ValueError(f"source_key kosong: {key}")

        if key in seen:
            raise ValueError(f"poem_key duplikat: {key}")

        seen.add(key)

        if label == "skip":
            skipped += 1
            continue

        if label not in TEMA_LIST:
            raise ValueError(f"Label tema tidak valid: {key} -> {label}")

        if not label_source:
            raise ValueError(f"Asal anotasi kosong: {key}")

        records.append({
            "poem_key": key,
            "source": source,
            "source_key": source_key,
            "label": label,
            "label_source": label_source,
        })

        provenance_counts[label_source] += 1

    return records, skipped, provenance_counts


def import_labels(csv_path, apply=False, replace=False):
    records, skipped, provenance_counts = load_label_rows(csv_path)

    db = Database.mysql()

    matched = []
    unmatched = []

    with db.cursor(commit=apply) as cur:

        # Cocokkan setiap anotasi menggunakan source dan source_key.
        for record in records:
            rows = cur.execute(
                "SELECT id FROM poems "
                "WHERE source = %s AND source_key = %s",
                (record["source"], record["source_key"]),
            ).all()

            if len(rows) != 1:
                unmatched.append(record["poem_key"])
                continue

            matched.append({
                **record,
                "poem_id": rows[0]["id"],
            })

        if unmatched:
            raise RuntimeError(
                f"{len(unmatched)} puisi tidak ditemukan "
                "atau memiliki kecocokan ambigu. Impor dibatalkan."
            )

        poem_ids = [record["poem_id"] for record in matched]

        # Periksa apakah label tema sudah pernah tersimpan.
        marks = ",".join(["%s"] * len(poem_ids))

        existing = cur.execute(
            "SELECT COUNT(*) AS n FROM poem_labels "
            f"WHERE label_type = 'tema' AND poem_id IN ({marks})",
            poem_ids,
        ).one()["n"]

        if existing > 0 and not replace:
            raise RuntimeError(
                f"Ditemukan {existing} label tema yang sudah ada. "
                "Gunakan --replace jika memang ingin menggantinya."
            )

        print("=== HASIL PEMERIKSAAN IMPOR ===")
        print("Total baris anotasi :", len(records) + skipped)
        print("Label tema valid    :", len(matched))
        print("Puisi skip          :", skipped)
        print("Label sudah ada     :", existing)

        print("\nDistribusi tema:")
        for label in TEMA_LIST:
            jumlah = sum(
                1 for record in matched
                if record["label"] == label
            )
            print(f"- {label}: {jumlah}")

        print("\nAsal anotasi:")
        for source, jumlah in provenance_counts.items():
            print(f"- {source}: {jumlah}")

        if not apply:
            print("\nDRY-RUN: belum ada perubahan pada database.")
            return

        # Hapus label tema sebelumnya hanya jika replace diminta.
        if replace:
            cur.execute(
                "DELETE FROM poem_labels "
                f"WHERE label_type = 'tema' AND poem_id IN ({marks})",
                poem_ids,
            )

        # Simpan satu label tema utama untuk setiap puisi.
        for record in matched:
            cur.execute(
                "INSERT INTO poem_labels "
                "(poem_id, label_type, label, is_primary, score, source) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    record["poem_id"],
                    "tema",
                    record["label"],
                    1,
                    None,
                    "manual",
                ),
            )

    if apply:
        print("\nIMPOR BERHASIL!")
        print(f"{len(matched)} label tema berhasil disimpan ke MySQL.")


def main():
    parser = argparse.ArgumentParser(
        description="Impor label tema Puitika ke MySQL."
    )

    parser.add_argument(
        "--csv",
        default=str(Path(config.LABEL_DIR) / "label_sheet.csv"),
        help="Lokasi file CSV anotasi.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Simpan label ke database. Tanpa opsi ini hanya dry-run.",
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="Ganti label tema yang sudah ada. Hanya berlaku bersama --apply.",
    )

    args = parser.parse_args()

    if args.replace and not args.apply:
        parser.error("--replace harus digunakan bersama --apply.")

    import_labels(
        args.csv,
        apply=args.apply,
        replace=args.replace,
    )


if __name__ == "__main__":
    main()
