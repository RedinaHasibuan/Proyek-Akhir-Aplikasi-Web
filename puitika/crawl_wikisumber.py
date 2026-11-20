"""Crawler Wikisumber (id.wikisource.org) lewat MediaWiki API.

Menyimpan wikitext MENTAH ke data/raw/wikisumber.jsonl (satu JSON per baris).
Pembersihan dilakukan terpisah di build_dataset.py, jadi kalau parser perlu
diperbaiki kamu tidak perlu crawling ulang.

Contoh:
  python crawl_wikisumber.py --limit 5        # uji coba 5 halaman
  python crawl_wikisumber.py                  # semua halaman Kategori:Puisi
Skrip bisa dilanjutkan: judul yang sudah ada di file output dilewati.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

import config

API = "https://id.wikisource.org/w/api.php"
BATCH = 20  # jumlah judul per permintaan isi halaman


def api_get(session, params, delay, retries=5):
    params = dict(params, format="json", formatversion="2", maxlag="5")
    for attempt in range(retries):
        try:
            resp = session.get(API, params=params, timeout=30)
        except requests.RequestException as exc:
            wait = 2 ** attempt
            print(f"  ! koneksi gagal ({exc}); ulang dalam {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code in (429, 500, 502, 503, 504):
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"  ! HTTP {resp.status_code}; tunggu {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            code = data["error"].get("code")
            if code == "maxlag":
                time.sleep(5)
                continue
            raise RuntimeError(f"API error: {data['error']}")
        time.sleep(delay)
        return data
    raise RuntimeError("API gagal setelah beberapa percobaan")


def list_category(session, category, depth, delay, seen_cats=None):
    """Kembalikan daftar judul halaman (namespace utama) dalam kategori."""
    seen_cats = seen_cats if seen_cats is not None else set()
    if category in seen_cats:
        return []
    seen_cats.add(category)

    titles, subcats = [], []
    cont = {}
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": "page|subcat",
            "cmlimit": "500",
            **cont,
        }
        data = api_get(session, params, delay)
        for m in data.get("query", {}).get("categorymembers", []):
            if m.get("ns") == 14:
                subcats.append(m["title"])
            elif m.get("ns") == 0:
                titles.append(m["title"])
        if "continue" in data:
            cont = data["continue"]
        else:
            break

    if subcats:
        print(f"  subkategori di {category}: {', '.join(subcats)}")
    if depth > 0:
        for sub in subcats:
            titles.extend(list_category(session, sub, depth - 1, delay, seen_cats))
    return list(dict.fromkeys(titles))  # buang duplikat, urutan tetap


def fetch_pages(session, titles, delay):
    params = {
        "action": "query",
        "prop": "revisions|info",
        "rvprop": "content|ids|timestamp",
        "rvslots": "main",
        "inprop": "url",
        "titles": "|".join(titles),
    }
    data = api_get(session, params, delay)
    return data.get("query", {}).get("pages", [])


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["title"])
                except (ValueError, KeyError):
                    continue
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category", default="Kategori:Puisi")
    ap.add_argument("--depth", type=int, default=1, help="kedalaman subkategori (0 = hanya kategori ini)")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah halaman (0 = semua)")
    ap.add_argument("--delay", type=float, default=1.0, help="jeda antar permintaan (detik)")
    ap.add_argument("--out", default=os.path.join(config.RAW_DIR, "wikisumber.jsonl"))
    args = ap.parse_args()

    if "ISI_EMAIL" in config.CONTACT:
        print("Peringatan: set PUITIKA_CONTACT=emailkamu@contoh.com agar User-Agent sesuai aturan Wikimedia.")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT

    print(f"Mendaftar halaman di {args.category} ...")
    titles = list_category(session, args.category, args.depth, args.delay)
    print(f"Ditemukan {len(titles)} halaman.")
    if args.limit:
        titles = titles[: args.limit]

    done = load_done(args.out)
    todo = [t for t in titles if t not in done]
    print(f"Sudah ada {len(titles) - len(todo)}, akan diambil {len(todo)}.")

    saved = 0
    with open(args.out, "a", encoding="utf-8") as out:
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            pages = fetch_pages(session, batch, args.delay)
            for p in pages:
                if p.get("missing") or not p.get("revisions"):
                    continue
                rev = p["revisions"][0]
                rec = {
                    "title": p["title"],
                    "pageid": p.get("pageid"),
                    "url": p.get("canonicalurl") or p.get("fullurl"),
                    "revid": rev.get("revid"),
                    "timestamp": rev.get("timestamp"),
                    "wikitext": rev.get("slots", {}).get("main", {}).get("content", ""),
                    "category": args.category,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                saved += 1
            out.flush()
            print(f"  {min(i + BATCH, len(todo))}/{len(todo)} halaman diproses")

    print(f"Selesai. {saved} halaman baru disimpan di {args.out}")


if __name__ == "__main__":
    main()
