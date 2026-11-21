"""Uji asap seluruh alur hari 3+ dengan DATA TIRUAN (puisi sintetis, bukan data sungguhan).

Tujuannya hanya memastikan skrip berjalan di komputermu. Angka F1 dari uji ini TIDAK bermakna.
Jalankan: python smoke_test.py
"""
import csv
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import textclean as tc  # noqa: E402
from build_dataset import FIELDS  # noqa: E402

TEMA_W = {
    "romansa": "cinta kekasih pelukan sayang hatiku mencintaimu".split(),
    "alam": "hujan laut gunung angin pohon sungai".split(),
    "sosial": "rakyat negeri buruh penguasa merdeka lapar".split(),
    "kehidupan": "waktu hidup rumah ibu makna perjalanan".split(),
    "religius": "tuhan doa surga iman sujud takdir".split(),
}
EMO_W = {
    "sedih": "luka kehilangan pedih sepi tangis kecewa".split(),
    "rindu": "rindu menunggu jauh jarak kenangan pulang".split(),
    "bahagia": "senyum tawa hangat syukur riang ceria".split(),
    "harapan": "esok fajar tekad harap bangkit cahaya".split(),
    "tenang": "teduh damai hening pelan sunyi pasrah".split(),
    "marah": "amarah murka lawan geram benci dendam".split(),
}
FILLER = "yang di dalam bagai seperti ketika masih".split()


def run(*cmd, stdin=None):
    res = subprocess.run([sys.executable, *cmd], cwd=HERE, input=stdin, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit(f"GAGAL: {' '.join(cmd)}")
    return res.stdout


def main():
    rng = random.Random(1)
    with tempfile.TemporaryDirectory() as tmp:
        poems_csv = os.path.join(tmp, "poems.csv")
        truth = {}
        with open(poems_csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            k = 0
            for tema, tw in TEMA_W.items():
                for emo, ew in EMO_W.items():
                    for _ in range(7):
                        lines = []
                        for _ in range(4):
                            words = rng.sample(tw, 2) + rng.sample(ew, 2) + rng.sample(FILLER, 1)
                            rng.shuffle(words)
                            lines.append(" ".join(words))
                        body = "\n".join(lines[:2]) + "\n\n" + "\n".join(lines[2:])
                        src = "wikisumber" if k % 5 == 0 else "idpuisi"
                        key = f"{src}|poem{k}"
                        truth[key] = (tema, emo)
                        n_l, n_s, n_w = tc.text_stats(body)
                        w.writerow({
                            "source": src, "source_key": f"poem{k}", "title": f"Puisi {k}", "author": f"Penyair {k % 9}",
                            "body": body, "source_url": "", "license": "", "in_public_library": int(src == "wikisumber"),
                            "body_hash": tc.body_hash(body), "n_lines": n_l, "n_stanzas": n_s, "n_words": n_w,
                        })
                        k += 1
        rep = os.path.join(tmp, "reports")
        print("1) explore_data"); run("explore_data.py", "--poems", poems_csv, "--report-dir", rep)

        sheet = os.path.join(tmp, "label_sheet.csv")
        print("2) make_label_sheet"); print(run("make_label_sheet.py", "--poems", poems_csv, "--out", sheet, "--n", "150"))

        with open(sheet, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f)); fields = list(rows[0].keys())
        for i, r in enumerate(rows):
            t, e = truth[r["poem_key"]]
            if i < 5:
                r["tema"] = "skip"
            else:
                r["tema"], r["emosi_utama"], r["label_oleh"] = t, e, "manusia"
            if i in (6, 7):
                r["perlu_tinjau"] = "1"
        with open(sheet, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

        models = os.path.join(tmp, "models")
        print("3) train_model")
        out = run("train_model.py", "--sheet", sheet, "--model-dir", models, "--report-dir", rep, "--min-count", "8")
        print(out[-900:])
        assert os.path.exists(os.path.join(models, "tema.joblib"))
        assert not os.path.exists(os.path.join(models, "emosi.joblib"))

        print("4) predict")
        print(run("predict.py", "--model-dir", models, "--text", "tuhan doa iman sujud pedih luka kehilangan tangis"))

        print("5) sentiment_analysis")
        from sentiment_analysis import analyze_sentiment
        assert analyze_sentiment("Aku bahagia dan bersyukur")["polarity"] == "positif"
        assert analyze_sentiment("Aku sedih dan terluka")["polarity"] == "negatif"
        print("   sentiment_analysis OK")

        print("6) label_cli (uji kompatibilitas anotasi lama tema + emosi)")
        cli_sheet = os.path.join(tmp, "cli.csv")
        cols = ["poem_key", "source", "title", "author", "n_words", "body", "tema_ai", "emosi_utama_ai", "emosi_lain_ai",
                "tema", "emosi_utama", "emosi_lain", "perlu_tinjau", "label_oleh", "catatan"]
        with open(cli_sheet, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
            w.writerow({"poem_key": "a", "title": "A", "author": "", "n_words": 5, "body": "satu\ndua",
                        "tema_ai": "alam", "emosi_utama_ai": "tenang", "emosi_lain_ai": "rindu"})
            w.writerow({"poem_key": "b", "title": "B", "author": "", "n_words": 5, "body": "tiga\nempat"})
            w.writerow({"poem_key": "c", "title": "C", "author": "", "n_words": 5, "body": "lima\nenam"})
        run("label_cli.py", "--sheet", cli_sheet, stdin="\n\n\ns\nq\n")
        with open(cli_sheet, encoding="utf-8-sig", newline="") as f:
            got = list(csv.DictReader(f))
        assert (got[0]["tema"], got[0]["emosi_utama"], got[0]["emosi_lain"], got[0]["label_oleh"]) == \
            ("alam", "tenang", "rindu", "manusia_konfirmasi_ai"), got[0]
        assert got[1]["tema"] == "skip" and got[2]["tema"] == "", got[1:]
        print("   label_cli OK")
        print("\nSEMUA UJI ASAP LULUS (angka F1 hanya dari data tiruan; abaikan).")
        print("Model utama: klasifikasi tema saja; sentiment analysis lexicon diuji terpisah.")


if __name__ == "__main__":
    main()
