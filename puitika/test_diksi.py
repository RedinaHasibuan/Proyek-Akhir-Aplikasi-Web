"""Uji otomatis Ruang Diksi + Teman Diksi (SQLite sementara). Jalankan: python test_diksi.py

Seperti test_backend.py: jalur MySQL (termasuk diksi_schema.sql) tidak teruji di sini. Data CSV bawaan dipakai
apa adanya, jadi uji ini juga memastikan CSV-mu valid setiap kali kamu mengeditnya.
"""
import csv
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import diksi_repo as dr  # noqa: E402
import eval_diksi  # noqa: E402
import load_diksi as ld  # noqa: E402
import teman_diksi as td  # noqa: E402
from app import create_app  # noqa: E402
from db import Database  # noqa: E402
from labels import EMOSI_LIST  # noqa: E402

SCHEMA = """
CREATE TABLE dictionary_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT NOT NULL, word_key TEXT NOT NULL UNIQUE, pos TEXT,
  meaning TEXT NOT NULL, nuance TEXT, example TEXT, keywords TEXT, emotion TEXT,
  verified INTEGER NOT NULL DEFAULT 0, source TEXT
);
CREATE TABLE dictionary_relations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, entry_id INTEGER NOT NULL, related_id INTEGER NOT NULL,
  relation_type TEXT NOT NULL, UNIQUE (entry_id, related_id, relation_type),
  FOREIGN KEY (entry_id) REFERENCES dictionary_entries(id) ON DELETE CASCADE,
  FOREIGN KEY (related_id) REFERENCES dictionary_entries(id) ON DELETE CASCADE
);
"""


def new_db(tmp, name):
    path = os.path.join(tmp, name)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.close()
    return Database.sqlite(path)


def row(kata, makna="arti", terkait="", **kw):
    base = {"kata": kata, "kelas_kata": "adjektiva", "makna": makna, "nuansa": "", "contoh": f"Contoh {kata}.",
            "kata_kunci": "", "emosi": "", "terkait": terkait, "terverifikasi": "0", "sumber": "uji"}
    base.update(kw)
    return base


class LoaderTest(unittest.TestCase):
    def test_validate_problems(self):
        rows = [
            row("a"),
            row("A"),                                   # duplikat (tak peka huruf besar)
            row("b", makna=""),                         # tanpa makna
            row("c", emosi="gembira"),                  # emosi tidak valid
            row("", makna="x"),                         # kata kosong
            row("d", terkait="sinonim:a;kebalikan:a"),  # jenis salah
            row("e", terkait="sinonim:tidakada"),       # target tak ada
            row("f", terkait="sinonim:f"),              # relasi ke diri sendiri
            row("g", terverifikasi="2"),
            row("h", terkait="terkait:a;antonim:e"),    # e sebenarnya valid, jadi relasi ini sah
        ]
        entries, rels, problems = ld.validate(rows)
        self.assertEqual([e["word"] for e in entries], ["a", "d", "e", "f", "h"])
        self.assertEqual(len(problems), 8, problems)
        self.assertIn(("a", "h", "terkait"), rels)
        self.assertIn(("h", "a", "terkait"), rels)        # dua arah
        self.assertIn(("e", "h", "antonim"), rels)
        self.assertIn(("h", "e", "antonim"), rels)

    def test_valid_relation_kept_when_sibling_token_invalid(self):
        entries, rels, problems = ld.validate([row("a"), row("d", terkait="sinonim:a;kebalikan:a")])
        self.assertIn(("d", "a", "sinonim"), rels)
        self.assertEqual(len(problems), 1)

    def test_load_is_idempotent_and_rebuilds_relations(self):
        tmp = tempfile.mkdtemp()
        try:
            db = new_db(tmp, "l.db")
            e, r, _ = ld.validate([row("a", terkait="sinonim:b"), row("b")])
            s = ld.load(db, e, r)
            self.assertEqual((s["baru"], s["relasi"]), (2, 2))
            # edit: makna a berubah, relasi diganti ke antonim, kata c baru
            e, r, _ = ld.validate([row("a", makna="baru", terkait="antonim:b"), row("b"), row("c")])
            s = ld.load(db, e, r)
            self.assertEqual((s["baru"], s["diperbarui"], s["relasi"]), (1, 2, 2))
            with db.cursor() as cur:
                self.assertEqual(cur.execute("SELECT COUNT(*) AS n FROM dictionary_entries").one()["n"], 3)
                self.assertEqual(cur.execute("SELECT meaning FROM dictionary_entries WHERE word_key = 'a'").one()["meaning"], "baru")
                types = {x["relation_type"] for x in cur.execute("SELECT relation_type FROM dictionary_relations").all()}
            self.assertEqual(types, {"antonim"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_schema_file_statements(self):
        sql = open(ld.SCHEMA, encoding="utf-8").read()
        stmts = [s for s in "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--")).split(";") if s.strip()]
        self.assertEqual(len(stmts), 2)
        self.assertTrue(all(s.strip().startswith("CREATE TABLE IF NOT EXISTS") for s in stmts))

    def test_real_csv_is_valid(self):
        rows = ld.read_rows(ld.DEFAULT_CSV)
        entries, rels, problems = ld.validate(rows)
        self.assertEqual(problems, [])
        self.assertGreaterEqual(len(entries), 100)
        self.assertEqual(len(entries), len(rows))
        for e in entries:
            self.assertTrue(e["example"], e["word"])
            self.assertTrue(e["keywords"], f"kata_kunci kosong: {e['word']}")
            self.assertTrue(e["emotion"] is None or e["emotion"] in EMOSI_LIST)
        # setiap emosi Puitika punya kata
        self.assertEqual({e["emotion"] for e in entries if e["emotion"]}, set(EMOSI_LIST))
        # relasi simetris
        s = set(rels)
        self.assertTrue(all((b, a, t) in s for a, b, t in s))


class DiksiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.db = new_db(cls.tmp, "d.db")
        e, r, p = ld.validate(ld.read_rows(ld.DEFAULT_CSV))
        assert not p
        ld.load(cls.db, e, r)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        dr.reset_cache()
        self.client = create_app(self.db, os.path.join(self.tmp, "nomodel")).test_client()

    # ------------------------------------------------------------------ repo
    def test_get_entry_and_relations(self):
        e = dr.get_entry(self.db, "  LELAH ")
        self.assertEqual(e["kata"], "lelah")
        syn = [x["kata"] for x in e["relasi"]["sinonim"]]
        self.assertIn("letih", syn)
        self.assertTrue(all(x["nuansa"] for x in e["relasi"]["sinonim"]))
        self.assertIsNone(dr.get_entry(self.db, "tidak ada"))
        self.assertIsNone(dr.get_entry(self.db, ""))
        # relasi dua arah
        self.assertIn("lelah", [x["kata"] for x in dr.get_entry(self.db, "letih")["relasi"]["sinonim"]])

    def test_list_words(self):
        r = dr.list_words(self.db, per_page=10)
        self.assertGreaterEqual(r["total"], 100)
        words = [x["kata"] for x in r["items"]]
        self.assertEqual(words, sorted(words))
        self.assertEqual(dr.list_words(self.db, q="%")["total"], 0)          # % dianggap huruf biasa
        self.assertEqual(dr.list_words(self.db, q="LELA")["items"][0]["kata"], "lelah")
        rindu = dr.list_words(self.db, emosi="rindu", per_page=100)
        self.assertTrue(rindu["items"] and all(x["emosi"] == "rindu" for x in rindu["items"]))
        with self.assertRaises(ValueError):
            dr.list_words(self.db, emosi="gembira")

    def test_similar_words(self):
        self.assertEqual(dr.similar_words(self.db, "laraa")[0], "lara")
        self.assertEqual(dr.similar_words(self.db, "zzzzzz"), [])

    def test_light_stem(self):
        self.assertEqual(dr.light_stem("ditakdirkan"), "takdir")
        self.assertEqual(dr.light_stem("menyerah"), "erah")    # salah potong (seharusnya serah), tetapi konsisten di kedua sisi
        self.assertEqual(dr.light_stem("suka"), "suka")        # kata pendek tidak dipotong
        self.assertEqual(dr.light_stem("cinta"), "cinta")

    def test_search_description(self):
        top = dr.search_description(self.db, "perasaan suka dan tidak suka sekaligus")
        self.assertEqual(top[0]["kata"], "ambivalensi")
        self.assertTrue(all(0 < h["skor"] <= 1 for h in top))
        self.assertEqual([h["skor"] for h in top], sorted((h["skor"] for h in top), reverse=True))
        self.assertEqual(dr.search_description(self.db, "xyzq qwerty"), [])      # tak ada kata dikenal -> kosong
        self.assertEqual(dr.search_description(self.db, "   "), [])
        # filter emosi
        marah = dr.search_description(self.db, "sangat marah", emosi="marah", top_k=10)
        self.assertTrue(marah and all(h["emosi"] == "marah" for h in marah))
        self.assertLessEqual(len(dr.search_description(self.db, "sangat marah", top_k=2)), 2)
        # cakupan imbuhan
        self.assertEqual(dr.search_description(self.db, "semuanya sudah ditakdirkan")[0]["kata"], "takdir")

    def test_search_on_empty_db(self):
        empty = new_db(self.tmp, "kosong.db")
        self.assertEqual(dr.search_description(empty, "sedih sekali"), [])

    def test_eval_queries_run(self):
        for name, floor in (("eval_queries.csv", 0.8), ("eval_queries_parafrasa.csv", 0.5)):
            with open(os.path.join(HERE, "data", "diksi", name), encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            summary, _ = eval_diksi.evaluate(self.db, rows)
            self.assertGreaterEqual(summary["top5"], floor, name)  # alarm bila kamus/pencarian rusak, bukan target mutu

    # ------------------------------------------------------------------ chatbot
    def ask(self, text):
        return td.respond(self.db, text)

    def test_chat_intents(self):
        cases = {
            "arti lara": "arti",
            "Apa arti kata nestapa?": "arti",
            "maknanya jengah": "arti",
            "jengah itu artinya apa": "arti",
            "apa itu senja": "arti",
            "tenang": "arti",
            "kata lain untuk lelah": "sinonim",
            "sinonim bahagia": "sinonim",
            "padanan kata sedih": "sinonim",
            "lawan kata gelisah": "antonim",
            "antonim fana": "antonim",
            "contoh kalimat renjana": "contoh",
            "diksi rindu": "emosi",
            "kata-kata untuk suasana marah": "emosi",
            "halo": "sapaan",
            "bantuan": "bantuan",
            "kata yang menggambarkan perasaan suka dan tidak suka sekaligus": "deskripsi",
            "xyzq qwe": "tidak_paham",
            "": "bantuan",
            "?!": "bantuan",
        }
        for msg, niat in cases.items():
            self.assertEqual(self.ask(msg)["niat"], niat, msg)

    def test_chat_contents(self):
        a = self.ask("kata lain untuk lelah")
        self.assertEqual({k["kata"] for k in a["kandidat"]}, {"letih", "penat"})
        self.assertTrue(all("relasi" not in k for k in a["kandidat"]))
        self.assertIn("nuansa", a["balasan"])
        self.assertEqual([k["kata"] for k in self.ask("lawan kata gelisah")["kandidat"]], ["damai", "tenang"])
        a = self.ask("kata lain untuk lara")
        self.assertIn("lara", a["balasan"])
        # kata tanpa sinonim tetapi punya relasi lain: tidak dibohongi
        a = self.ask("lawan kata jarak")
        self.assertEqual(a["niat"], "antonim")
        self.assertIn("Belum ada lawan kata", a["balasan"])
        # salah ketik -> saran
        a = self.ask("arti laraa")
        self.assertEqual(a["niat"], "tidak_paham")
        self.assertIn("lara", a["balasan"])
        self.assertEqual(a["saran"], ["arti lara"])
        # kata tak dikenal sama sekali
        self.assertIn("belum punya", self.ask("arti zzzzzz")["balasan"])
        # kata yang tidak ada di kamus tidak boleh dikarang artinya
        self.assertEqual(self.ask("arti zzzzzz")["kandidat"], [])
        d = self.ask("perasaan ingin bertemu seseorang yang jauh")
        self.assertEqual(d["kandidat"][0]["kata"], "rindu")

    # ------------------------------------------------------------------ API
    def test_api_words(self):
        j = self.client.get("/api/diksi/words?per_page=5&emosi=sedih").get_json()
        self.assertEqual(len(j["items"]), 5)
        self.assertTrue(all(x["emosi"] == "sedih" for x in j["items"]))
        for bad in ("emosi=gembira", "page=0", "page=x", "q=" + "x" * 101):
            self.assertEqual(self.client.get("/api/diksi/words?" + bad).status_code, 400, bad)
        self.assertEqual(self.client.get("/api/diksi/words?per_page=9999").get_json()["per_page"], 100)

    def test_api_word_detail(self):
        j = self.client.get("/api/diksi/words/Lelah").get_json()
        self.assertEqual(j["kata"], "lelah")
        self.assertIn("kata_kunci", j)
        self.assertFalse(j["terverifikasi"])
        self.assertEqual(self.client.get("/api/diksi/words/tidakada").status_code, 404)
        self.assertEqual(self.client.get("/api/diksi/words/" + "x" * 200).status_code, 404)

    def test_api_search(self):
        r = self.client.post("/api/diksi/search", json={"deskripsi": "perasaan suka dan tidak suka sekaligus"})
        j = r.get_json()
        self.assertEqual(j["hasil"][0]["kata"], "ambivalensi")
        self.assertIn("catatan", j)
        r = self.client.post("/api/diksi/search", json={"deskripsi": "sangat marah", "emosi": "marah", "top_k": 2})
        self.assertLessEqual(len(r.get_json()["hasil"]), 2)
        self.assertEqual(self.client.post("/api/diksi/search", json={"deskripsi": "xyzq qwe"}).get_json()["hasil"], [])
        for bad in ({}, {"deskripsi": ""}, {"deskripsi": 5}, {"deskripsi": "a " * 200},
                    {"deskripsi": "sedih", "emosi": "gembira"}, {"deskripsi": "sedih", "top_k": 0},
                    {"deskripsi": "sedih", "top_k": 11}, {"deskripsi": "sedih", "top_k": True},
                    {"deskripsi": "sedih", "top_k": "3"}):
            self.assertEqual(self.client.post("/api/diksi/search", json=bad).status_code, 400, bad)
        self.assertEqual(self.client.post("/api/diksi/search", data="bukan json").status_code, 400)
        self.assertEqual(self.client.get("/api/diksi/search").status_code, 405)

    def test_api_chat(self):
        j = self.client.post("/api/diksi/chat", json={"pesan": "arti lara"}).get_json()
        self.assertEqual((j["niat"], j["kandidat"][0]["kata"]), ("arti", "lara"))
        self.assertEqual(set(j), {"niat", "balasan", "kandidat", "saran"})
        for bad in ({}, {"pesan": ""}, {"pesan": "x" * (td.MAX_PESAN + 1)}, {"pesan": None}):
            self.assertEqual(self.client.post("/api/diksi/chat", json=bad).status_code, 400, bad)

    def test_api_503_when_tables_missing(self):
        path = os.path.join(self.tmp, "polos.db")
        sqlite3.connect(path).close()
        c = create_app(Database.sqlite(path), os.path.join(self.tmp, "nomodel")).test_client()
        for method, url in (("get", "/api/diksi/words"), ("get", "/api/diksi/words/lara")):
            r = getattr(c, method)(url)
            self.assertEqual(r.status_code, 503, url)
            self.assertIn("load_diksi.py", r.get_json()["error"])
        self.assertEqual(c.post("/api/diksi/chat", json={"pesan": "halo"}).status_code, 503)

    def test_health_reports_diksi(self):
        j = self.client.get("/api/health").get_json()
        self.assertTrue(j["diksi"]["tersedia"])
        self.assertGreaterEqual(j["diksi"]["n_entri"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=1)
