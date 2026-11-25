"""Pengujian API lanjutan Puitika: Makna Puisi, Studio, dan Dashboard.

Jalankan dari folder puitika:
    python test_advanced_api.py

Semua test memakai SQLite sementara, kamus dari CSV lokal, dan model sintetis.
Database MySQL utama tidak digunakan atau diubah.
"""
import os
import shutil
import sqlite3
import tempfile
import unittest

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

import dashboard
import diksi_repo
import load_diksi
from app import create_app
from db import Database
import repo


HERE = os.path.dirname(os.path.abspath(__file__))

SCHEMA = """
CREATE TABLE poets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL UNIQUE,
    period TEXT
);

CREATE TABLE poems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poet_id INTEGER,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_url TEXT,
    license TEXT,
    in_public_library INTEGER NOT NULL DEFAULT 0,
    body_hash TEXT NOT NULL UNIQUE,
    n_lines INTEGER NOT NULL DEFAULT 0,
    n_stanzas INTEGER NOT NULL DEFAULT 0,
    n_words INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source, source_key),
    FOREIGN KEY(poet_id) REFERENCES poets(id)
);

CREATE TABLE poem_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poem_id INTEGER NOT NULL,
    label_type TEXT NOT NULL,
    label TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 1,
    score REAL,
    source TEXT NOT NULL,
    UNIQUE(poem_id, label_type, label, source),
    FOREIGN KEY(poem_id) REFERENCES poems(id)
);

CREATE TABLE dictionary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    word_key TEXT NOT NULL UNIQUE,
    pos TEXT,
    meaning TEXT NOT NULL,
    nuance TEXT,
    example TEXT,
    keywords TEXT,
    emotion TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    source TEXT
);

CREATE TABLE dictionary_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    related_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    UNIQUE(entry_id, related_id, relation_type),
    FOREIGN KEY(entry_id) REFERENCES dictionary_entries(id) ON DELETE CASCADE,
    FOREIGN KEY(related_id) REFERENCES dictionary_entries(id) ON DELETE CASCADE
);

CREATE TABLE drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    tema TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

TRAIN_DATA = {
    "romansa": [
        "cinta kekasih sayang pelukan rindu",
        "hatiku mencintai seseorang yang kusayang",
        "kasih mesra pasangan cinta",
        "aku merindukan kekasih tercinta",
        "pelukan hangat kasih sayang",
        "cinta dan rindu dalam hati",
    ],
    "alam": [
        "hutan gunung hujan pohon sungai",
        "lautan ombak angin dan pantai",
        "daun bunga langit matahari",
        "burung bernyanyi di tengah hutan",
        "gunung hijau diselimuti kabut",
        "hujan turun membasahi pepohonan",
    ],
    "sosial": [
        "rakyat masyarakat keadilan kehidupan",
        "pekerja memperjuangkan hak masyarakat",
        "kemiskinan dan kesenjangan sosial",
        "bangsa bersatu melawan ketidakadilan",
        "rakyat menuntut perubahan dan keadilan",
        "perjuangan masyarakat dan kemanusiaan",
    ],
}

GROUPS = [
    {
        "tema": "romansa",
        "penyair": 1,
        "inti": ["cinta", "kasih", "kekasih", "rindu", "sayang", "pelukan"],
        "variasi": ["senja", "melati", "hati", "kenangan", "temu"],
    },
    {
        "tema": "alam",
        "penyair": 2,
        "inti": ["hutan", "gunung", "hujan", "pohon", "sungai", "rimba"],
        "variasi": ["awan", "daun", "burung", "kabut", "embun"],
    },
    {
        "tema": "sosial",
        "penyair": 3,
        "inti": ["rakyat", "bangsa", "keadilan", "perjuangan", "masyarakat", "hak"],
        "variasi": ["merdeka", "buruh", "suara", "negeri", "setara"],
    },
]


def train_tiny_model(model_dir):
    os.makedirs(model_dir, exist_ok=True)
    texts, labels = [], []
    for tema, examples in TRAIN_DATA.items():
        texts.extend(examples)
        labels.extend([tema] * len(examples))

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=1000)),
    ])
    pipeline.fit(texts, labels)
    bundle = {
        "pipeline": pipeline,
        "meta": {
            "target": "tema",
            "classes": sorted(set(labels)),
            "n_train": len(texts),
            "cv_macro_f1": 0.5,
        },
    }
    joblib.dump(bundle, os.path.join(model_dir, "tema.joblib"))


class AdvancedAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="puitika_advanced_test_")
        cls.db_path = os.path.join(cls.tmp, "advanced.db")
        cls.model_dir = os.path.join(cls.tmp, "models")

        conn = sqlite3.connect(cls.db_path)
        conn.executescript(SCHEMA)
        conn.close()

        cls.db = Database.sqlite(cls.db_path)
        train_tiny_model(cls.model_dir)

        # Muat kamus proyek ke SQLite sementara, bukan ke MySQL utama.
        rows = load_diksi.read_rows(load_diksi.DEFAULT_CSV)
        entries, relations, problems = load_diksi.validate(rows)
        if problems:
            raise AssertionError(f"CSV kamus memiliki masalah: {problems[:5]}")
        load_diksi.load(cls.db, entries, relations)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        dashboard.reset_cache()
        diksi_repo.reset_cache()

        with self.db.cursor(commit=True) as cur:
            for table in ("drafts", "poem_labels", "poems", "poets"):
                cur.execute(f"DELETE FROM {table}")

            poets = [
                (1, "Penyair Romansa", "penyair romansa", "Angkatan 45"),
                (2, "Penyair Alam", "penyair alam", "Pujangga Baru"),
                (3, "Penyair Sosial", "penyair sosial", "Balai Pustaka"),
            ]
            for poet in poets:
                cur.execute(
                    "INSERT INTO poets (id, name, name_key, period) VALUES (%s, %s, %s, %s)",
                    poet,
                )

            self.poem_ids = []
            for i in range(30):
                group = GROUPS[i // 10]
                variation = (i // 3) % len(group["variasi"])
                next_variation = (variation + 1) % len(group["variasi"])
                body = " ".join(
                    group["inti"]
                    + [group["variasi"][variation], group["variasi"][next_variation]]
                )
                cur.execute(
                    """
                    INSERT INTO poems (
                        poet_id, title, body, source, source_key, source_url,
                        license, in_public_library, body_hash, n_lines, n_stanzas, n_words
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        group["penyair"],
                        f"Puisi {i + 1:02d}",
                        body,
                        "wikisumber",
                        f"advanced-{i}",
                        f"https://example.test/poem/{i}",
                        "PD",
                        1,
                        f"advanced-hash-{i}",
                        1,
                        1,
                        len(body.split()),
                    ),
                )
                poem_id = cur.execute(
                    "SELECT id FROM poems WHERE source_key = %s", (f"advanced-{i}",)
                ).one()["id"]
                self.poem_ids.append(poem_id)
                repo.set_labels(
                    cur,
                    poem_id,
                    "tema",
                    [(group["tema"], True, None)],
                    "manual",
                )

            # Satu puisi internal untuk memastikan endpoint publik tidak membocorkannya.
            cur.execute(
                """
                INSERT INTO poems (
                    poet_id, title, body, source, source_key, source_url,
                    license, in_public_library, body_hash, n_lines, n_stanzas, n_words
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (1, "Puisi Internal", "teks rahasia internal", "idpuisi", "internal-1",
                 None, None, 0, "internal-hash", 1, 1, 3),
            )
            self.internal_id = cur.execute(
                "SELECT id FROM poems WHERE source_key = %s", ("internal-1",)
            ).one()["id"]

        self.client = create_app(self.db, self.model_dir).test_client()

    # ------------------------------- MAKNA PUISI
    def test_makna_post_returns_analysis_sections(self):
        response = self.client.post(
            "/api/makna",
            json={"text": "Cinta itu seperti mawar yang mekar di senja."},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        for key in ("ringkasan", "diksi_penting", "baris_kunci", "frasa_kiasan", "sentimen", "tema", "catatan"):
            self.assertIn(key, result)
        self.assertIn("kata_kamus", result["diksi_penting"])
        self.assertIn("kata_menonjol", result["diksi_penting"])
        self.assertIsInstance(result["frasa_kiasan"], list)

    def test_makna_get_public_poem(self):
        response = self.client.get(f"/api/poems/{self.poem_ids[0]}/makna")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["poem_id"], self.poem_ids[0])
        self.assertIn("title", response.get_json())

    def test_makna_rejects_invalid_text(self):
        for payload in ({}, {"text": ""}, {"text": "   "}, {"text": 123}):
            response = self.client.post("/api/makna", json=payload)
            self.assertEqual(response.status_code, 400, (payload, response.get_json()))

    def test_makna_does_not_expose_internal_poem(self):
        response = self.client.get(f"/api/poems/{self.internal_id}/makna")
        self.assertEqual(response.status_code, 404)

    # -------------------------------- STUDIO PUISI
    def test_studio_crud_lifecycle(self):
        created = self.client.post(
            "/api/drafts",
            json={"judul": "Senja", "isi": "Aku menunggu senja dan rindu.", "tema": "romansa"},
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        draft = created.get_json()
        draft_id = draft["id"]
        self.assertEqual(draft["judul"], "Senja")
        self.assertEqual(draft["tema"], "romansa")
        self.assertEqual(draft["isi"], "Aku menunggu senja dan rindu.")

        fetched = self.client.get(f"/api/drafts/{draft_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.get_json()["id"], draft_id)

        updated = self.client.patch(
            f"/api/drafts/{draft_id}", json={"judul": "Senja Baru", "tema": None}
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["judul"], "Senja Baru")
        self.assertIsNone(updated.get_json()["tema"])

        listed = self.client.get("/api/drafts?page=1&per_page=10")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["total"], 1)
        self.assertEqual(listed.get_json()["items"][0]["id"], draft_id)

        deleted = self.client.delete(f"/api/drafts/{draft_id}")
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        self.assertEqual(deleted.get_json()["terhapus"], draft_id)
        self.assertEqual(self.client.get(f"/api/drafts/{draft_id}").status_code, 404)

    def test_studio_validates_create_and_update(self):
        invalid_payloads = (
            {},
            {"judul": "", "isi": "   "},
            {"tema": "tema-tidak-valid"},
            {"judul": 123},
        )
        for payload in invalid_payloads:
            response = self.client.post("/api/drafts", json=payload)
            self.assertEqual(response.status_code, 400, (payload, response.get_json()))

        created = self.client.post("/api/drafts", json={"isi": "Puisi singkat."})
        self.assertEqual(created.status_code, 201)
        draft_id = created.get_json()["id"]
        self.assertEqual(self.client.patch(f"/api/drafts/{draft_id}", json={}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/drafts/{draft_id}", json={"tema": "salah"}).status_code, 400)
        self.assertEqual(self.client.get("/api/drafts/999999").status_code, 404)
        self.assertEqual(self.client.delete("/api/drafts/999999").status_code, 404)

    def test_studio_recommendation_returns_theme_and_dictionary(self):
        response = self.client.post(
            "/api/studio/rekomendasi", json={"text": "Aku merindukan cinta dan kasih."}
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertIn("tema", result)
        self.assertIn("diksi", result)
        self.assertIsNotNone(result["diksi"])
        self.assertIn("padanan", result["diksi"])
        self.assertIn("terkait", result["diksi"])
        self.assertIn("catatan", result)

    def test_studio_recommendation_validates_text(self):
        for payload in ({}, {"text": ""}, {"text": "   "}, {"text": 123}):
            response = self.client.post("/api/studio/rekomendasi", json=payload)
            self.assertEqual(response.status_code, 400, (payload, response.get_json()))

    # -------------------------------- DASHBOARD SASTRA
    def test_dashboard_statistics_and_distributions(self):
        response = self.client.get("/api/dashboard?k=3")
        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual(result["korpus"]["n_puisi"], 30)
        self.assertEqual(result["korpus"]["n_penyair"], 3)
        self.assertGreater(result["korpus"]["total_kata"], 0)
        self.assertEqual(sum(x["count"] for x in result["tema"]["distribusi"]), 30)
        self.assertEqual(sum(x["count"] for x in result["periode"]["distribusi"]), 30)
        self.assertEqual(result["periode"]["tanpa_periode"], 0)
        self.assertTrue(result["frekuensi_kata"])
        self.assertTrue(result["clustering"]["tersedia"])
        self.assertEqual(result["clustering"]["k"], 3)
        self.assertEqual(len(result["clustering"]["klaster"]), 3)

    def test_dashboard_cluster_unavailable_for_small_corpus(self):
        keep_ids = tuple(self.poem_ids[:10])
        placeholders = ", ".join(["%s"] * len(keep_ids))
        with self.db.cursor(commit=True) as cur:
            cur.execute(
                f"DELETE FROM poem_labels WHERE poem_id NOT IN ({placeholders})",
                keep_ids,
            )
            cur.execute(
                f"DELETE FROM poems WHERE in_public_library = 1 AND id NOT IN ({placeholders})",
                keep_ids,
            )
        dashboard.reset_cache()
        result = self.client.get("/api/dashboard?k=3").get_json()
        self.assertEqual(result["korpus"]["n_puisi"], 10)
        self.assertFalse(result["clustering"]["tersedia"])

    def test_dashboard_validates_cluster_count(self):
        self.assertEqual(self.client.get("/api/dashboard?k=2").status_code, 400)
        self.assertEqual(self.client.get("/api/dashboard?k=9").status_code, 400)
        self.assertEqual(self.client.get("/api/dashboard?k=abc").status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
