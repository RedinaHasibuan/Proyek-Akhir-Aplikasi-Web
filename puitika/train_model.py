"""Latih dan evaluasi model klasifikasi TEMA Puitika.

Label emosi yang mungkin masih tersimpan pada label_sheet.csv dipertahankan sebagai
arsip anotasi/eksperimen, tetapi TIDAK digunakan untuk melatih model utama.
Sentiment analysis dikerjakan terpisah melalui sentiment_analysis.py (lexicon-based).

Contoh:  python train_model.py
Metode : TF-IDF + Logistic Regression (class_weight=balanced).
Evaluasi: validasi silang BERSARANG (tuning hyperparameter di dalam, penilaian di luar) supaya
          skor tidak terlalu optimis, dibandingkan dengan baseline (kelas terbanyak / tebak acak).
Keluaran: models/tema.joblib, reports/eval_tema.txt,
          reports/confusion_tema.csv, reports/summary.json
Baris yang dipakai: tema bukan kosong/skip, dan perlu_tinjau bukan "1".
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from functools import partial

import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

import config
from labels import SKIP
from preprocess import tokenize

GRID = {
    "tfidf__ngram_range": [(1, 1), (1, 2)],
    "tfidf__min_df": [1, 2],
    "clf__C": [0.5, 2, 8],
}
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]


def make_pipeline(stopwords, stem):
    vec = TfidfVectorizer(
        tokenizer=partial(tokenize, stopwords=stopwords, stem=stem),
        lowercase=False, token_pattern=None, sublinear_tf=True, max_df=0.9,
    )
    clf = LogisticRegression(class_weight="balanced", max_iter=3000)
    return Pipeline([("tfidf", vec), ("clf", clf)])


def load_rows(paths):
    rows, seen = [], set()
    for path in paths:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r["poem_key"] in seen:  # puisi yang sama di dua lembar: pakai yang pertama
                    continue
                seen.add(r["poem_key"])
                rows.append(r)
    usable = [r for r in rows if r["tema"] and r["tema"] != SKIP and r.get("perlu_tinjau", "") != "1"]
    print(f"Lembar label: {len(rows)} baris | dipakai: {len(usable)} | "
          f"skip: {sum(1 for r in rows if r['tema'] == SKIP)} | "
          f"perlu_tinjau: {sum(1 for r in rows if r.get('perlu_tinjau') == '1')} | "
          f"belum dilabeli: {sum(1 for r in rows if not r['tema'])}")
    prov = Counter(r.get("label_oleh") or "(kosong)" for r in usable)
    print("Asal label: " + ", ".join(f"{k}={v}" for k, v in prov.items()))
    return usable


def top_features(pipe, k=8):
    names = pipe.named_steps["tfidf"].get_feature_names_out()
    clf = pipe.named_steps["clf"]
    coef = clf.coef_
    if coef.shape[0] == 1:  # biner
        coef = np.vstack([-coef[0], coef[0]])
    return {cls: [names[j] for j in np.argsort(coef[i])[::-1][:k]] for i, cls in enumerate(clf.classes_)}


def run_target(name, texts, labels, args):
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    say(f"\n{'=' * 60}\nTARGET: {name}\n{'=' * 60}")
    counts = Counter(labels)
    say("Sebaran label: " + ", ".join(f"{k}={v}" for k, v in counts.most_common()))
    small = [k for k, v in counts.items() if v < args.min_count]
    if small:
        say(f"[!] Kelas dengan <{args.min_count} contoh dibuang dari pelatihan: {small}. "
            f"Tambah contoh atau gabungkan kelas ini.")
    keep = [i for i, y in enumerate(labels) if counts[y] >= args.min_count]
    X = [texts[i] for i in keep]
    y = np.array([labels[i] for i in keep])
    classes = [str(c) for c in sorted(set(y))]
    if len(classes) < 2 or len(y) < args.folds * 2:
        say("Data tidak cukup untuk dilatih. Tambah puisi berlabel.")
        return None, "\n".join(lines)
    say(f"Dipakai: {len(y)} puisi, {len(classes)} kelas")

    pipe = make_pipeline(args.stopwords, args.stem)
    inner = GridSearchCV(pipe, GRID, cv=StratifiedKFold(3, shuffle=True, random_state=0),
                         scoring="f1_macro", n_jobs=1)
    outer = StratifiedKFold(args.folds, shuffle=True, random_state=42)

    proba = cross_val_predict(inner, X, y, cv=outer, method="predict_proba")
    pred = np.array(classes)[proba.argmax(axis=1)]
    f1m = f1_score(y, pred, average="macro")
    acc = accuracy_score(y, pred)

    base = {}
    for strat in ("most_frequent", "stratified"):
        bp = cross_val_predict(DummyClassifier(strategy=strat, random_state=0), X, y, cv=outer)
        base[strat] = {"macro_f1": f1_score(y, bp, average="macro"), "acc": accuracy_score(y, bp)}

    say(f"\nHasil validasi silang {args.folds}-lipat (bersarang):")
    say(f"  macro-F1 = {f1m:.3f} | akurasi = {acc:.3f}")
    say(f"  baseline kelas-terbanyak : macro-F1 = {base['most_frequent']['macro_f1']:.3f}, akurasi = {base['most_frequent']['acc']:.3f}")
    say(f"  baseline tebak-acak      : macro-F1 = {base['stratified']['macro_f1']:.3f}, akurasi = {base['stratified']['acc']:.3f}")
    say("\nLaporan per kelas:")
    say(classification_report(y, pred, labels=classes, digits=3, zero_division=0))

    cm = confusion_matrix(y, pred, labels=classes)
    say("Confusion matrix (baris = label sebenarnya, kolom = prediksi):")
    say("            " + " ".join(f"{c[:8]:>8s}" for c in classes))
    for c, row in zip(classes, cm):
        say(f"{c[:10]:10s}  " + " ".join(f"{v:8d}" for v in row))

    maxp = proba.max(axis=1)
    say("\nKeyakinan vs ketepatan (untuk menentukan ambang 'tidak yakin'):")
    for t in THRESHOLDS:
        mask = maxp >= t
        if mask.sum():
            say(f"  prob >= {t:.1f}: mencakup {mask.mean():.0%} puisi, akurasi {accuracy_score(y[mask], pred[mask]):.0%}")

    final = GridSearchCV(make_pipeline(args.stopwords, args.stem), GRID,
                         cv=StratifiedKFold(3, shuffle=True, random_state=0), scoring="f1_macro")
    final.fit(X, y)
    best = final.best_estimator_
    say(f"\nHyperparameter terpilih (data penuh): {final.best_params_}")
    say("Kata paling berpengaruh per kelas:")
    for cls, words in top_features(best).items():
        say(f"  {cls:10s}: {', '.join(words)}")

    os.makedirs(args.model_dir, exist_ok=True)
    os.makedirs(args.report_dir, exist_ok=True)
    meta = {
        "target": name, "classes": classes, "n_train": int(len(y)), "dropped_classes": small,
        "cv_macro_f1": round(f1m, 4), "cv_accuracy": round(acc, 4),
        "baseline_majority_macro_f1": round(base["most_frequent"]["macro_f1"], 4),
        "best_params": {k: str(v) for k, v in final.best_params_.items()},
        "stopwords": args.stopwords, "stem": args.stem,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    joblib.dump({"pipeline": best, "meta": meta}, os.path.join(args.model_dir, f"{name}.joblib"))
    with open(os.path.join(args.report_dir, f"confusion_{name}.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sebenarnya\\prediksi"] + classes)
        for c, row in zip(classes, cm):
            w.writerow([c] + list(map(int, row)))
    return meta, "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", nargs="+", default=[os.path.join(config.LABEL_DIR, "label_sheet.csv")],
                    help="satu atau lebih lembar label (mis. lembar utama + lembar tambahan)")
    ap.add_argument("--model-dir", default=config.MODEL_DIR)
    ap.add_argument("--report-dir", default=config.REPORT_DIR)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--min-count", type=int, default=12, help="kelas dengan contoh lebih sedikit dibuang")
    ap.add_argument("--no-stopwords", dest="stopwords", action="store_false")
    ap.add_argument("--stem", action="store_true", help="pakai stemming Sastrawi (lambat)")
    args = ap.parse_args()

    rows = load_rows(args.sheet)
    pairs = [(r["body"], r["tema"]) for r in rows if r.get("tema") and r["tema"] != SKIP
             and r.get("perlu_tinjau", "") != "1"]
    meta, report_text = run_target("tema", [p[0] for p in pairs], [p[1] for p in pairs], args)

    os.makedirs(args.report_dir, exist_ok=True)
    with open(os.path.join(args.report_dir, "eval_tema.txt"), "w", encoding="utf-8") as f:
        f.write(report_text + "\n")

    # Preserve the previous emotion experiment before summary.json becomes theme-only.
    # Existing emosi.joblib and eval_emosi.txt are deliberately not deleted.
    summary_path = os.path.join(args.report_dir, "summary.json")
    archive_path = os.path.join(args.report_dir, "summary_emosi_eksperimen_lama.json")
    if os.path.exists(summary_path) and not os.path.exists(archive_path):
        try:
            with open(summary_path, encoding="utf-8") as f:
                previous = json.load(f)
            if "emosi" in previous:
                with open(archive_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "catatan": "Hasil eksperimen klasifikasi emosi sebelumnya; bukan model utama Puitika.",
                        "emosi": previous["emosi"],
                    }, f, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError):
            pass

    summary = {"tema": meta} if meta else {}
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== RINGKASAN MODEL UTAMA PUITIKA ===")
    if meta:
        print(f"tema: macro-F1 {meta['cv_macro_f1']:.3f} "
              f"(baseline {meta['baseline_majority_macro_f1']:.3f}), "
              f"akurasi {meta['cv_accuracy']:.3f}, n={meta['n_train']}, kelas={meta['classes']}")
        print("Klasifikasi emosi tidak dilatih sebagai model utama.")
        print("Sentiment analysis tersedia terpisah melalui sentiment_analysis.py.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
