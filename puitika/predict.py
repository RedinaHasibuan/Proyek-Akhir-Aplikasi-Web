"""Prediksi/saran TEMA puisi menggunakan model utama Puitika.

Contoh:
  python predict.py --text "Hujan turun pelan, aku menunggumu di beranda"
  python predict.py --file puisi.txt
Dari kode Flask: from predict import suggest; hasil = suggest(teks)
Hasil hanya berisi kandidat tema. Analisis sentimen berada di sentiment_analysis.py.
"""
import argparse
import os

import joblib
import numpy as np

import config

UNCERTAIN_BELOW = 0.45
_cache = {}


def _load_theme(model_dir):
    key = ("tema", model_dir)
    if key not in _cache:
        path = os.path.join(model_dir, "tema.joblib")
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Model tema tidak ditemukan: {path}. Jalankan python train_model.py terlebih dahulu."
            )
        _cache[key] = joblib.load(path)
    return _cache[key]


def suggest(text, model_dir=config.MODEL_DIR, top_k=3, threshold=UNCERTAIN_BELOW):
    """Kembalikan kandidat tema dan status keyakinannya; tidak memprediksi emosi."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Teks puisi tidak boleh kosong.")
    bundle = _load_theme(model_dir)
    pipe = bundle["pipeline"]
    proba = pipe.predict_proba([text])[0]
    order = np.argsort(proba)[::-1][:max(1, top_k)]
    candidates = [(str(pipe.classes_[i]), float(proba[i])) for i in order]
    return {
        "tema": {
            "kandidat": candidates,
            "yakin": candidates[0][1] >= threshold,
            "cv_macro_f1": bundle.get("meta", {}).get("cv_macro_f1"),
        }
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--model-dir", default=config.MODEL_DIR)
    ap.add_argument("--threshold", type=float, default=UNCERTAIN_BELOW)
    args = ap.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        raise SystemExit("Beri --text atau --file")

    result = suggest(text, model_dir=args.model_dir, threshold=args.threshold)
    theme = result["tema"]
    candidates = ", ".join(f"{label} ({score:.0%})" for label, score in theme["kandidat"])
    flag = " [tidak yakin]" if not theme["yakin"] else ""
    print(f"tema: {candidates}{flag}")
    print("Ini saran tema otomatis; penulis tetap dapat mengubahnya.")


if __name__ == "__main__":
    main()
