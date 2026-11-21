"""Alat pelabelan di terminal. Mode lama menyimpan anotasi tema + emosi.
Gunakan --theme-only untuk anotasi tema saja; anotasi emosi yang sudah ada dipertahankan.

Contoh:  python label_cli.py
Tampilkan puisi satu per satu. Ketik nomor label. Kalau kolom saran AI terisi, tekan
Enter untuk menerima saran. Kunci:  s = lewati (tidak cocok label mana pun)  b = kembali  q = simpan & keluar.
Disimpan ke file setelah SETIAP puisi, jadi aman kalau terputus.
"""
import argparse
import csv
import os
import sys

import config
from labels import EMOSI_LIST, TEMA_LIST, SKIP


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def save(path, rows, fields):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def menu(options):
    return "  ".join(f"{i}={name}" for i, name in enumerate(options, 1))


def ask_choice(prompt, options, default=None):
    """Kembalikan nama label, atau 's' / 'b' / 'q'."""
    while True:
        extra = f" [Enter={default}]" if default else ""
        ans = input(f"{prompt}{extra}> ").strip().lower()
        if ans in ("s", "b", "q"):
            return ans
        if not ans and default:
            return default
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1]
        if ans in options:
            return ans
        print("  ketik nomor yang tersedia, atau s / b / q")


def ask_multi(prompt, options, default=""):
    """Emosi tambahan: nomor dipisah koma/spasi; '-' = kosong; Enter = pakai saran."""
    while True:
        ans = input(f"{prompt}{f' [Enter={default}]' if default else ''}> ").strip().lower()
        if not ans:
            return default
        if ans == "-":
            return ""
        parts = [p for p in ans.replace(",", " ").split() if p]
        if all(p.isdigit() and 1 <= int(p) <= len(options) for p in parts):
            return ";".join(dict.fromkeys(options[int(p) - 1] for p in parts))
        print("  contoh: 2,5   atau '-' untuk tidak ada")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=os.path.join(config.LABEL_DIR, "label_sheet.csv"))
    ap.add_argument(
        "--theme-only", action="store_true",
        help="hanya anotasi tema; kolom emosi lama dipertahankan sebagai arsip dan tidak diminta lagi",
    )
    args = ap.parse_args()

    rows, fields = load(args.sheet)
    total = len(rows)
    history = []  # indeks yang baru dilabeli (untuk 'kembali')
    i = 0
    while i < total:
        r = rows[i]
        if r["tema"]:
            i += 1
            continue
        done = sum(1 for x in rows if x["tema"])
        print("\n" + "=" * 70)
        print(f"[{done}/{total} terlabel]  {r['title']} — {r['author'] or 'penyair tidak diketahui'}  ({r['n_words']} kata)")
        print("-" * 70)
        print(r["body"])
        print("-" * 70)
        ai_t, ai_e, ai_l = r.get("tema_ai", ""), r.get("emosi_utama_ai", ""), r.get("emosi_lain_ai", "")
        if ai_t or ai_e:
            print(f"Saran AI: tema={ai_t or '-'} | emosi={ai_e or '-'}" + (f" (+ {ai_l})" if ai_l else ""))
        print("TEMA   : " + menu(TEMA_LIST) + "   s=lewati b=kembali q=keluar")
        tema = ask_choice("tema", TEMA_LIST, ai_t if ai_t in TEMA_LIST else None)
        if tema == "q":
            break
        if tema == "b":
            if history:
                j = history.pop()
                for col in ("tema", "emosi_utama", "emosi_lain", "label_oleh"):
                    rows[j][col] = ""
                save(args.sheet, rows, fields)
                i = j
            else:
                print("  belum ada yang bisa dikembalikan")
            continue
        if tema == "s":
            r["tema"], r["label_oleh"] = SKIP, "manusia"
            save(args.sheet, rows, fields)
            history.append(i)
            i += 1
            continue

        if args.theme_only:
            accepted_theme_ai = bool(ai_t) and tema == ai_t
            r["tema"] = tema
            r["label_oleh"] = "manusia_konfirmasi_ai" if accepted_theme_ai else "manusia"
            # emosi_utama/emosi_lain yang sudah ada sengaja tidak diubah.
            save(args.sheet, rows, fields)
            history.append(i)
            i += 1
            continue

        print("EMOSI  : " + menu(EMOSI_LIST))
        emo = ask_choice("emosi utama", EMOSI_LIST, ai_e if ai_e in EMOSI_LIST else None)
        if emo in ("q", "b", "s"):
            print("  dibatalkan untuk puisi ini")
            continue
        other = ask_multi("emosi lain (opsional)", EMOSI_LIST, ai_l)
        other = ";".join(e for e in other.split(";") if e and e != emo)

        accepted_all = bool(ai_t) and tema == ai_t and emo == ai_e and other == ai_l
        r["tema"], r["emosi_utama"], r["emosi_lain"] = tema, emo, other
        r["label_oleh"] = "manusia_konfirmasi_ai" if accepted_all else "manusia"
        save(args.sheet, rows, fields)
        history.append(i)
        i += 1

    done = sum(1 for x in rows if x["tema"])
    print(f"\nSelesai sesi. {done}/{total} puisi sudah terlabel. File: {args.sheet}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nKeluar. Label yang sudah diisi tetap tersimpan.", file=sys.stderr)
