"""Uji penyajian frontend Puitika pada backend aktif (SQLite sementara).

Jalankan: python test_frontend.py
Test ini tidak membutuhkan MySQL atau model produksi.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from app import FRONTEND_DIR, create_app
from db import Database
from test_backend import SCHEMA

PAGES = ["home", "library", "diksi", "studio", "makna", "dashboard"]


class FrontendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="puitika_frontend_test_")
        db_path = os.path.join(cls.tmp, "frontend.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(SCHEMA)
        conn.close()
        cls.db = Database.sqlite(db_path)
        cls.client = create_app(cls.db, os.path.join(cls.tmp, "models_kosong")).test_client()

    @classmethod
    def tearDownClass(cls):
        cls.client = None
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_index_dan_semua_berkas_frontend(self):
        response = self.client.get("/")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/html", response.content_type)
            html = response.get_data(as_text=True)
            self.assertIn('lang="id"', html)
            self.assertIn("Puitika", html)
            self.assertIn("/app/js/app.js", html)
        finally:
            response.close()

        paths = ["css/style.css", "js/app.js", "js/ui.js", "js/charts.js"]
        paths += [f"js/pages/{page}.js" for page in PAGES]
        for path in paths:
            with self.subTest(path=path):
                asset = self.client.get("/app/" + path)
                try:
                    self.assertEqual(asset.status_code, 200)
                    self.assertGreater(len(asset.get_data()), 0)
                finally:
                    asset.close()

    def test_header_keamanan(self):
        page = self.client.get("/")
        try:
            self.assertIn("default-src 'self'", page.headers.get("Content-Security-Policy", ""))
            self.assertEqual(page.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(page.headers.get("Referrer-Policy"), "no-referrer")
        finally:
            page.close()

        api_error = self.client.get("/api/rute-yang-tidak-ada")
        try:
            self.assertEqual(api_error.status_code, 404)
            self.assertIsInstance(api_error.get_json(), dict)
            self.assertNotIn("Content-Security-Policy", api_error.headers)
        finally:
            api_error.close()


    def test_layout_responsif_dan_beranda_ringkas(self):
        index = os.path.join(FRONTEND_DIR, "index.html")
        css_path = os.path.join(FRONTEND_DIR, "css", "style.css")
        home_path = os.path.join(FRONTEND_DIR, "js", "pages", "home.js")
        with open(index, encoding="utf-8") as source:
            html = source.read()
        with open(css_path, encoding="utf-8") as source:
            css = source.read()
        with open(home_path, encoding="utf-8") as source:
            home = source.read()

        self.assertIn('id="mobile-nav-toggle"', html)
        self.assertIn('id="desktop-nav-toggle"', html)
        self.assertIn('id="rail-backdrop"', html)
        self.assertNotIn('id="status"', html)
        self.assertNotIn('class="rail-note"', html)
        self.assertIn("@media (max-width: 900px)", css)
        self.assertIn("--sage-light: #E3EAD9", css)
        self.assertIn("feature-grid-compact", home)
        self.assertIn('class: "home-note"', home)
        self.assertIn("Kata yang tepat dapat memberi bentuk", home)
        self.assertNotIn("home-bottom-banner", home)

    def test_home_search_results_are_mounted_in_hero(self):
        home_path = os.path.join(FRONTEND_DIR, "js", "pages", "home.js")
        with open(home_path, encoding="utf-8") as source:
            home = source.read()

        self.assertIn('class: "home-search-results"', home)
        self.assertIn('api("/api/diksi/search"', home)
        hero_start = home.index('el("div", { class: "hero-copy" },')
        hero_end = home.index('el("div", { class: "hero-art', hero_start)
        hero_copy = home[hero_start:hero_end]
        self.assertIn("form,\n        out", hero_copy)

    def test_sidebar_diksi_dan_catatan_katalog(self):
        css_path = os.path.join(FRONTEND_DIR, "css", "style.css")
        ui_path = os.path.join(FRONTEND_DIR, "js", "ui.js")
        diksi_path = os.path.join(FRONTEND_DIR, "js", "pages", "diksi.js")
        library_path = os.path.join(FRONTEND_DIR, "js", "pages", "library.js")
        app_path = os.path.join(FRONTEND_DIR, "js", "app.js")
        with open(css_path, encoding="utf-8") as source:
            css = source.read()
        with open(ui_path, encoding="utf-8") as source:
            ui = source.read()
        with open(diksi_path, encoding="utf-8") as source:
            diksi = source.read()
        with open(library_path, encoding="utf-8") as source:
            library = source.read()
        with open(app_path, encoding="utf-8") as source:
            app = source.read()

        self.assertIn(".shell.rail-collapsed", css)
        self.assertIn("--rail-cocoa-top", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn("body.focus-reading .poem-side.catalog-note", css)
        self.assertIn("function setDesktopRail(open)", app)
        self.assertIn('class: "poem-side catalog-note"', library)
        self.assertNotIn('"Lisensi"', library)
        self.assertNotIn('"Ukuran"', library)
        self.assertNotIn("belum diverifikasi", ui + diksi)


    def test_teman_diksi_memiliki_layout_percakapan(self):
        diksi_path = os.path.join(FRONTEND_DIR, "js", "pages", "diksi.js")
        css_path = os.path.join(FRONTEND_DIR, "css", "style.css")
        with open(diksi_path, encoding="utf-8") as source:
            diksi = source.read()
        with open(css_path, encoding="utf-8") as source:
            css = source.read()

        for required in (
            "teman-chat-heading",
            "teman-chat-log",
            "teman-empty-state",
            "teman-message-bot",
            "teman-message-you",
            "teman-typing-bubble",
            "teman-composer-field",
            "Percakapan baru",
        ):
            self.assertIn(required, diksi)
        for required in (
            ".teman-chat {",
            ".teman-message-bot",
            ".teman-message-you",
            ".teman-empty-state",
            ".teman-composer-field",
            "@media (max-width: 700px)",
        ):
            self.assertIn(required, css)
        self.assertIn("/api/diksi/chat", diksi)
        self.assertIn("Berbasis kamus Puitika", diksi)


    def test_tidak_membocorkan_berkas_di_luar_frontend(self):
        paths = ["/app/../app.py", "/app/%2e%2e/config.py", "/app/..%2fconfig.py"]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                try:
                    self.assertEqual(response.status_code, 404)
                finally:
                    response.close()

    def test_tanpa_pola_dom_berbahaya(self):
        forbidden = re.compile(
            r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|"
            r"setAttribute\(\s*['\"]style",
            re.IGNORECASE,
        )
        files = []
        for root, _, names in os.walk(FRONTEND_DIR):
            files.extend(os.path.join(root, name) for name in names if name.endswith((".js", ".html")))
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            with open(path, encoding="utf-8") as source:
                contents = source.read()
            self.assertIsNone(forbidden.search(contents), os.path.relpath(path, FRONTEND_DIR))
        with open(os.path.join(FRONTEND_DIR, "index.html"), encoding="utf-8") as source:
            html = source.read()
        self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)")
        self.assertNotRegex(html, r"\sstyle=")


if __name__ == "__main__":
    unittest.main(verbosity=1)
