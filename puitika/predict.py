
"""Prediksi tema puisi menggunakan model utama Puitika.

Fungsi:
- suggest()       : rekomendasi tema untuk teks puisi.
- suggest_one()   : prediksi satu target tema.
- predict_many()  : prediksi banyak puisi sekaligus.
- model_available(): memeriksa ketersediaan model.
- model_meta()    : membaca metadata model.

Model utama hanya mengklasifikasikan tema, bukan emosi.

Contoh:
    python predict.py --text "Hujan turun pelan, aku menunggumu"
    python predict.py --file puisi.txt
"""

import argparse
import os

import joblib
import numpy as np

import config


# ---------------------------------------------------------
# KONFIGURASI MODEL
# ---------------------------------------------------------

UNCERTAIN_BELOW = 0.45

# Hanya satu model utama: klasifikasi tema.
TARGETS = ("tema",)

# Cache model agar tidak perlu dimuat berulang kali.
_cache = {}


# ---------------------------------------------------------
# PEMUATAN MODEL
# ---------------------------------------------------------

def _path(name, model_dir):
    """Membuat alamat file model."""

    if name not in TARGETS:
        raise ValueError(f"Target model tidak dikenal: {name}")

    return os.path.join(os.fspath(model_dir), f"{name}.joblib")


def model_available(name, model_dir=config.MODEL_DIR):
    """Memeriksa apakah file model tersedia."""

    path = _path(name, model_dir)
    return os.path.isfile(path)


def _load(name, model_dir):
    """Memuat model dan menyimpannya dalam cache."""

    path = _path(name, model_dir)

    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Model {name} tidak ditemukan: {path}. "
            "Jalankan python train_model.py terlebih dahulu."
        )

    # Periksa perubahan file agar model bisa dimuat ulang
    # setelah training ulang tanpa harus restart server.
    file_stat = os.stat(path)
    fingerprint = (file_stat.st_mtime_ns, file_stat.st_size)

    cached = _cache.get(path)

    if cached is None or cached["fingerprint"] != fingerprint:
        bundle = joblib.load(path)

        if not isinstance(bundle, dict) or "pipeline" not in bundle:
            raise ValueError(
                f"Format file model {name}.joblib tidak valid."
            )

        _cache[path] = {
            "fingerprint": fingerprint,
            "bundle": bundle,
        }

    return _cache[path]["bundle"]


def model_meta(name, model_dir=config.MODEL_DIR):
    """Mengambil metadata model.

    Mengembalikan metadata atau None jika model belum tersedia.
    """

    if not model_available(name, model_dir):
        return None

    bundle = _load(name, model_dir)
    return bundle.get("meta") or {}


# ---------------------------------------------------------
# PREDIKSI SATU PUISI
# ---------------------------------------------------------

def suggest_one(
    text,
    name,
    model_dir=config.MODEL_DIR,
    top_k=3,
    threshold=UNCERTAIN_BELOW,
):
    """Menghasilkan kandidat prediksi untuk satu puisi.

    Hasil:
    {
        "kandidat": [
            ("romansa", 0.75),
            ("alam", 0.15)
        ],
        "yakin": True,
        "cv_macro_f1": 0.418
    }

    Mengembalikan None apabila model belum tersedia.
    """

    if name not in TARGETS:
        raise ValueError(f"Target model tidak dikenal: {name}")

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Teks puisi tidak boleh kosong.")

    if top_k < 1:
        raise ValueError("top_k minimal 1.")

    if not 0 <= threshold <= 1:
        raise ValueError("threshold harus berada antara 0 dan 1.")

    if not model_available(name, model_dir):
        return None

    bundle = _load(name, model_dir)
    pipeline = bundle["pipeline"]

    probabilities = pipeline.predict_proba([text])[0]

    # Urutkan kandidat dari probabilitas tertinggi.
    order = np.argsort(probabilities)[::-1][:top_k]

    candidates = [
        (
            str(pipeline.classes_[index]),
            float(probabilities[index]),
        )
        for index in order
    ]

    meta = bundle.get("meta") or {}

    return {
        "kandidat": candidates,
        "yakin": candidates[0][1] >= threshold,
        "cv_macro_f1": meta.get("cv_macro_f1"),
    }


# ---------------------------------------------------------
# PREDIKSI UTAMA
# ---------------------------------------------------------

def suggest(
    text,
    model_dir=config.MODEL_DIR,
    top_k=3,
    threshold=UNCERTAIN_BELOW,
):
    """Memberikan saran klasifikasi tema puisi.

    Hasil hanya berisi target tema, bukan klasifikasi emosi.
    """

    return {
        name: suggest_one(
            text,
            name,
            model_dir=model_dir,
            top_k=top_k,
            threshold=threshold,
        )
        for name in TARGETS
    }


# ---------------------------------------------------------
# PREDIKSI BANYAK PUISI
# ---------------------------------------------------------

def predict_many(texts, name, model_dir=config.MODEL_DIR):
    """Memprediksi tema untuk banyak puisi sekaligus.

    Menghasilkan daftar:
        [
            ("romansa", 0.75),
            ("alam", 0.82)
        ]

    Probabilitas yang dikembalikan adalah probabilitas
    kelas dengan nilai tertinggi untuk setiap puisi.
    """

    if name not in TARGETS:
        raise ValueError(f"Target model tidak dikenal: {name}")

    texts = list(texts)

    if not texts:
        return []

    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Semua teks puisi harus berupa teks yang tidak kosong.")

    bundle = _load(name, model_dir)
    pipeline = bundle["pipeline"]

    probabilities = np.asarray(
        pipeline.predict_proba(texts)
    )

    # Bentuk data: jumlah puisi x jumlah kelas tema.
    if probabilities.ndim != 2:
        raise ValueError("Format probabilitas prediksi tidak valid.")

    results = []

    for row in probabilities:
        # Ambil indeks kelas dengan probabilitas tertinggi.
        best_index = int(np.argmax(row))

        # Ambil label dan probabilitas kelas tersebut.
        best_label = str(pipeline.classes_[best_index])
        best_probability = float(row[best_index])

        results.append(
            (best_label, best_probability)
        )

    return results


# ---------------------------------------------------------
# PROGRAM COMMAND LINE
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--text", help="Teks puisi yang akan dianalisis.")
    parser.add_argument("--file", help="File teks puisi.")
    parser.add_argument(
        "--model-dir",
        default=config.MODEL_DIR,
        help="Lokasi folder model.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Jumlah kandidat tema yang ditampilkan.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=UNCERTAIN_BELOW,
        help="Ambang keyakinan model.",
    )

    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as file:
            text = file.read()

    elif args.text:
        text = args.text

    else:
        raise SystemExit("Berikan --text atau --file.")

    if not text.strip():
        raise SystemExit("Teks puisi tidak boleh kosong.")

    result = suggest(
        text,
        model_dir=args.model_dir,
        top_k=args.top_k,
        threshold=args.threshold,
    )

    if not any(result.values()):
        raise SystemExit(
            "Model tema belum tersedia. "
            "Jalankan python train_model.py terlebih dahulu."
        )

    for name, prediction in result.items():

        if prediction is None:
            print(f"{name}: model belum tersedia.")
            continue

        candidates = ", ".join(
            f"{label} ({probability:.0%})"
            for label, probability in prediction["kandidat"]
        )

        flag = "" if prediction["yakin"] else " [tidak yakin]"

        print(f"{name}: {candidates}{flag}")

        if prediction["cv_macro_f1"] is not None:
            print(
                f"Macro-F1 evaluasi model: "
                f"{prediction['cv_macro_f1']:.3f}"
            )

    print(
        "\nIni adalah saran otomatis. "
        "Penulis tetap dapat menentukan tema puisinya."
    )


if __name__ == "__main__":
    main()
