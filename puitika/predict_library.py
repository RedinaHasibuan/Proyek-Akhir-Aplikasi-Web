
"""Prediksi tema untuk puisi Perpustakaan Puitika.

Penggunaan:
    python predict_library.py
    python predict_library.py --apply
    python predict_library.py --min-score 0.50

Default hanya melakukan dry-run.
Label manual dan user tidak akan ditimpa.
Hanya puisi publik yang diproses.
"""

import argparse

import config
import predict
from db import Database, ensure_schema
from repo import set_labels


def predict_library(
    db,
    model_dir=config.MODEL_DIR,
    min_score=predict.UNCERTAIN_BELOW,
    batch=256,
    apply=False,
):
    """Memprediksi tema puisi publik tanpa menimpa label manual/user."""

    if not 0 <= min_score <= 1:
        raise ValueError("min_score harus berada antara 0 dan 1.")

    if batch < 1:
        raise ValueError("batch minimal 1.")

    if not predict.model_available("tema", model_dir):
        return {"tema": None}

    stats = {
        "total_publik": 0,
        "manual_dilewati": 0,
        "akan_ditulis": 0,
        "ditulis": 0,
        "di_bawah_ambang": 0,
        "akan_dihapus": 0,
        "dihapus": 0,
        "model_diperbarui": 0,
    }

    with db.cursor(commit=apply) as cur:

        # Hanya ambil puisi yang boleh tampil di Perpustakaan.
        poems = cur.execute(
            "SELECT id, body FROM poems "
            "WHERE in_public_library = 1 "
            "ORDER BY id"
        ).all()

        stats["total_publik"] = len(poems)
        public_ids = {poem["id"] for poem in poems}

        # Lindungi label manual dan user.
        protected_ids = {
            row["poem_id"]
            for row in cur.execute(
                "SELECT DISTINCT poem_id FROM poem_labels "
                "WHERE label_type = 'tema' "
                "AND source <> 'model'"
            ).all()
            if row["poem_id"] in public_ids
        }

        # Identifikasi prediksi model yang sudah tersimpan.
        existing_model_ids = {
            row["poem_id"]
            for row in cur.execute(
                "SELECT DISTINCT poem_id FROM poem_labels "
                "WHERE label_type = 'tema' AND source = 'model'"
            ).all()
            if row["poem_id"] in public_ids
        }

        eligible = [
            poem for poem in poems
            if poem["id"] not in protected_ids
        ]

        stats["manual_dilewati"] = len(protected_ids)

        # Prediksi bertahap agar penggunaan memori tetap terkendali.
        for start in range(0, len(eligible), batch):
            chunk = eligible[start:start + batch]

            predictions = predict.predict_many(
                [poem["body"] for poem in chunk],
                "tema",
                model_dir,
            )

            for poem, (label, probability) in zip(chunk, predictions):

                poem_id = poem["id"]
                probability = float(probability)

                if probability >= min_score:

                    stats["akan_ditulis"] += 1

                    if poem_id in existing_model_ids:
                        stats["model_diperbarui"] += 1

                    if apply:
                        set_labels(
                            cur,
                            poem_id,
                            "tema",
                            [(label, True, round(probability, 4))],
                            "model",
                        )
                        stats["ditulis"] += 1

                else:
                    stats["di_bawah_ambang"] += 1

                    # Prediksi model lama yang sudah tidak memenuhi
                    # ambang dihapus agar tidak menjadi label lemah.
                    if poem_id in existing_model_ids:
                        stats["akan_dihapus"] += 1

                        if apply:
                            cur.execute(
                                "DELETE FROM poem_labels "
                                "WHERE poem_id = %s "
                                "AND label_type = 'tema' "
                                "AND source = 'model'",
                                (poem_id,),
                            )
                            stats["dihapus"] += cur.rowcount

    return {"tema": stats}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--model-dir",
        default=config.MODEL_DIR,
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=predict.UNCERTAIN_BELOW,
    )

    parser.add_argument(
        "--batch",
        type=int,
        default=256,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Simpan hasil prediksi ke database.",
    )

    args = parser.parse_args()

    if not 0 <= args.min_score <= 1:
        parser.error("--min-score harus berada antara 0 dan 1.")

    if args.batch < 1:
        parser.error("--batch minimal 1.")

    db = Database.mysql()

    # Migrasi hanya dijalankan ketika benar-benar akan menyimpan.
    if args.apply:
        ensure_schema(db)

    result = predict_library(
        db,
        model_dir=args.model_dir,
        min_score=args.min_score,
        batch=args.batch,
        apply=args.apply,
    )

    stats = result["tema"]

    if stats is None:
        raise SystemExit(
            "Model tema belum tersedia. "
            "Jalankan python train_model.py terlebih dahulu."
        )

    print("=== PREDIKSI TEMA PERPUSTAKAAN ===")
    print("Mode:", "APPLY" if args.apply else "DRY-RUN")
    print("Total puisi publik:", stats["total_publik"])
    print("Label manual/user dilindungi:", stats["manual_dilewati"])
    print("Prediksi memenuhi ambang:", stats["akan_ditulis"])
    print("Prediksi di bawah ambang:", stats["di_bawah_ambang"])
    print("Label model yang akan diperbarui:", stats["model_diperbarui"])
    print("Label model yang akan dihapus:", stats["akan_dihapus"])

    if args.apply:
        print("\nLabel tema disimpan:", stats["ditulis"])
        print("Label model dihapus:", stats["dihapus"])
        print("PROSES SELESAI.")
    else:
        print("\nDRY-RUN: database tidak diubah.")
        print("Gunakan --apply untuk menyimpan hasil prediksi.")


if __name__ == "__main__":
    main()
