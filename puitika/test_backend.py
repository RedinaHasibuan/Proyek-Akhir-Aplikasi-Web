
"""Pengujian otomatis backend Puitika.

Jalankan:
    python test_backend.py

Pengujian menggunakan SQLite sementara dan Flask test client.
Tidak mengubah database MySQL asli.

Yang diuji:
- Perpustakaan hanya membaca puisi publik.
- Pencarian, filter tema, dan pagination.
- Detail dan analisis puisi.
- Prediksi tema satu dan banyak puisi.
- Prediksi perpustakaan dengan perlindungan label manual/user.
- API Flask dan validasi input.
- Integrasi analisis sentimen.
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

import analysis
import predict
import predict_library
import repo
from app import create_app
from db import Database


# ---------------------------------------------------------
# SKEMA SQLITE UNTUK PENGUJIAN
# ---------------------------------------------------------

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
"""


# ---------------------------------------------------------
# DATA SINTETIS UNTUK MODEL PENGUJIAN
# ---------------------------------------------------------

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


def train_tiny_model(model_dir):
    """Membuat model kecil sementara khusus untuk pengujian."""

    os.makedirs(model_dir, exist_ok=True)

    texts = []
    labels = []

    for tema, examples in TRAIN_DATA.items():
        for example in examples:
            texts.append(example)
            labels.append(tema)

    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
            ),
        ),
        (
            "clf",
            LogisticRegression(max_iter=1000),
        ),
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

    joblib.dump(
        bundle,
        os.path.join(model_dir, "tema.joblib"),
    )


# ---------------------------------------------------------
# TEST BACKEND
# ---------------------------------------------------------

class BackendTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

        cls.db_path = os.path.join(cls.tmp, "test.db")
        cls.model_dir = os.path.join(cls.tmp, "models")

        conn = sqlite3.connect(cls.db_path)
        conn.executescript(SCHEMA)
        conn.close()

        cls.db = Database.sqlite(cls.db_path)

        # Model sintetis hanya digunakan dalam pengujian.
        train_tiny_model(cls.model_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        """Membuat data pengujian baru untuk setiap test."""

        with self.db.cursor(commit=True) as cur:

            for table in ("poem_labels", "poems", "poets"):
                cur.execute(f"DELETE FROM {table}")

            poets = [
                "Penyair A",
                "Penyair B",
                "Penyair C",
            ]

            for i, name in enumerate(poets, 1):
                cur.execute(
                    "INSERT INTO poets (id, name, name_key) "
                    "VALUES (%s, %s, %s)",
                    (i, name, name.lower()),
                )

            bodies = [
                "Cinta kekasih dan sayang dalam hatiku.",
                "Hutan gunung hujan pohon dan sungai.",
                "Rakyat masyarakat menuntut keadilan.",
                "Hujan turun di tengah hutan.",
                "Aku merindukan seseorang yang kucinta.",
                "Perjuangan rakyat demi keadilan.",
                "Puisi internal yang tidak boleh ditampilkan.",
            ]

            self.ids = {}

            for i, body in enumerate(bodies):

                public = i < 6

                title = (
                    "Diskon 100% asli_"
                    if i == 3
                    else f"Puisi {i:02d}"
                )

                source = "wikisumber" if public else "idpuisi"

                cur.execute(
                    """
                    INSERT INTO poems (
                        poet_id, title, body, source, source_key,
                        source_url, license, in_public_library,
                        body_hash, n_lines, n_stanzas, n_words
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        (i % 3) + 1,
                        title,
                        body,
                        source,
                        f"k{i}",
                        f"https://example.test/{i}" if public else None,
                        "PD" if public else None,
                        int(public),
                        f"hash-{i}",
                        1,
                        1,
                        len(body.split()),
                    ),
                )

                self.ids[i] = cur.execute(
                    "SELECT id FROM poems WHERE source_key = %s",
                    (f"k{i}",),
                ).one()["id"]

            # Label manual.
            repo.set_labels(
                cur,
                self.ids[0],
                "tema",
                [("romansa", True, None)],
                "manual",
            )

            # Label model lama.
            repo.set_labels(
                cur,
                self.ids[1],
                "tema",
                [("alam", True, 0.70)],
                "model",
            )

            # Label milik pengguna.
            repo.set_labels(
                cur,
                self.ids[2],
                "tema",
                [("sosial", True, None)],
                "user",
            )

            # Label puisi internal untuk memeriksa pembatasan akses.
            repo.set_labels(
                cur,
                self.ids[6],
                "tema",
                [("religius", True, None)],
                "manual",
            )

        self.client = create_app(
            self.db,
            self.model_dir,
        ).test_client()

    # -----------------------------------------------------
    # REPOSITORY
    # -----------------------------------------------------

    def test_only_public_poems(self):
        result = repo.list_poems(
            self.db,
            per_page=50,
        )

        self.assertEqual(result["total"], 6)

        public_ids = [
            item["id"]
            for item in result["items"]
        ]

        self.assertNotIn(self.ids[6], public_ids)

        self.assertIsNone(
            repo.get_poem(self.db, self.ids[6])
        )

    def test_theme_filter(self):
        result = repo.list_poems(
            self.db,
            tema="romansa",
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(
            result["items"][0]["tema"]["label"],
            "romansa",
        )

        with self.assertRaises(ValueError):
            repo.list_poems(
                self.db,
                tema="emosi",
            )

    def test_search_special_characters(self):
        self.assertEqual(
            repo.list_poems(self.db, q="%")["total"],
            1,
        )

        self.assertEqual(
            repo.list_poems(self.db, q="_")["total"],
            1,
        )

        self.assertEqual(
            repo.list_poems(self.db, q="!")["total"],
            0,
        )

    def test_pagination(self):
        result = repo.list_poems(
            self.db,
            per_page=2,
            page=2,
        )

        self.assertEqual(result["total"], 6)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(len(result["items"]), 2)

    def test_manual_label_replaces_model_label(self):
        with self.db.cursor(commit=True) as cur:
            repo.set_labels(
                cur,
                self.ids[1],
                "tema",
                [("romansa", True, None)],
                "manual",
            )

        poem = repo.get_poem(self.db, self.ids[1])

        self.assertEqual(
            poem["tema"]["source"],
            "manual",
        )

        with self.db.cursor() as cur:
            total = cur.execute(
                "SELECT COUNT(*) AS n FROM poem_labels "
                "WHERE poem_id = %s AND label_type = 'tema'",
                (self.ids[1],),
            ).one()["n"]

        self.assertEqual(total, 1)

    # -----------------------------------------------------
    # PREDIKSI MODEL
    # -----------------------------------------------------

    def test_predict_many(self):
        texts = [
            "hutan gunung hujan dan pohon",
            "cinta kasih sayang dan rindu",
        ]

        results = predict.predict_many(
            texts,
            "tema",
            self.model_dir,
        )

        self.assertEqual(len(results), 2)

        for label, probability in results:
            self.assertIn(label, TRAIN_DATA)
            self.assertIsInstance(probability, float)
            self.assertGreaterEqual(probability, 0)
            self.assertLessEqual(probability, 1)

    def test_predict_library_dry_run(self):
        result = predict_library.predict_library(
            self.db,
            model_dir=self.model_dir,
            min_score=0.0,
            apply=False,
        )

        stats = result["tema"]

        self.assertEqual(stats["total_publik"], 6)
        self.assertEqual(stats["manual_dilewati"], 2)
        self.assertEqual(stats["akan_ditulis"], 4)
        self.assertEqual(stats["ditulis"], 0)

        # Dry-run tidak boleh mengubah database.
        with self.db.cursor() as cur:
            total = cur.execute(
                "SELECT COUNT(*) AS n FROM poem_labels "
                "WHERE label_type = 'tema' AND source = 'model'"
            ).one()["n"]

        self.assertEqual(total, 1)

    def test_predict_library_apply_protects_manual_user(self):
        result = predict_library.predict_library(
            self.db,
            model_dir=self.model_dir,
            min_score=0.0,
            apply=True,
        )

        stats = result["tema"]

        self.assertEqual(stats["ditulis"], 4)

        # Label manual harus tetap ada.
        manual = repo.get_poem(self.db, self.ids[0])
        self.assertEqual(manual["tema"]["source"], "manual")
        self.assertEqual(manual["tema"]["label"], "romansa")

        # Label user juga harus tetap ada.
        user = repo.get_poem(self.db, self.ids[2])
        self.assertEqual(user["tema"]["source"], "user")

        # Prediksi model tidak boleh masuk puisi internal.
        internal = repo.get_poem(self.db, self.ids[6])
        self.assertIsNone(internal)

    # -----------------------------------------------------
    # FLASK API
    # -----------------------------------------------------

    def test_api_health(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertTrue(data["database"])
        self.assertTrue(data["model"]["tema"]["tersedia"])

    def test_api_filters_and_poets(self):
        response = self.client.get("/api/filters")

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertEqual(data["total_public"], 6)
        self.assertIn("tema", data)
        self.assertNotIn("emosi", data)

        poets = self.client.get(
            "/api/poets?limit=10"
        ).get_json()["items"]

        self.assertGreater(len(poets), 0)

    def test_api_poems_and_detail(self):
        response = self.client.get(
            "/api/poems?per_page=5"
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertEqual(data["total"], 6)
        self.assertEqual(len(data["items"]), 5)
        self.assertIn("excerpt", data["items"][0])
        self.assertNotIn("body", data["items"][0])

        detail = self.client.get(
            f"/api/poems/{self.ids[0]}"
        )

        self.assertEqual(detail.status_code, 200)
        self.assertIn("body", detail.get_json())

        # Puisi internal harus ditolak.
        internal = self.client.get(
            f"/api/poems/{self.ids[6]}"
        )

        self.assertEqual(internal.status_code, 404)

    def test_api_poem_analysis(self):
        response = self.client.get(
            f"/api/poems/{self.ids[0]}/analysis"
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertIn("statistik", data)
        self.assertIn("saran_model", data)
        self.assertIn("sentimen", data)
        self.assertIn("tema", data["label_tersimpan"])

    def test_api_analyze(self):
        response = self.client.post(
            "/api/analyze",
            json={
                "text": (
                    "Aku bahagia dan senang, "
                    "tetapi aku sedih dan kecewa."
                )
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()

        self.assertIn("statistik", data)
        self.assertIn("sentimen", data)

        self.assertEqual(
            data["sentimen"]["polarity"],
            "campuran",
        )

        self.assertIn(
            "tema",
            data["saran_model"],
        )

        self.assertNotIn(
            "emosi",
            data["saran_model"],
        )

    def test_api_validation(self):
        invalid_payloads = [
            {},
            {"text": ""},
            {"text": "   "},
            {"text": 123},
            {"text": "123 456 !!!"},
        ]

        for payload in invalid_payloads:
            response = self.client.post(
                "/api/analyze",
                json=payload,
            )

            self.assertEqual(
                response.status_code,
                400,
                msg=str(payload),
            )

        oversized = self.client.post(
            "/api/analyze",
            json={"text": "x" * 21000},
        )

        self.assertEqual(oversized.status_code, 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
