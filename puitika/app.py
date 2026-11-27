"""API utama Puitika menggunakan Flask.

Jalankan:
    python app.py

Alamat:
    http://127.0.0.1:5000/api/health

Endpoint utama:
    GET    /api/health
    GET    /api/filters
    GET    /api/poets
    GET    /api/poems
    GET    /api/poems/<id>
    GET    /api/poems/<id>/analysis
    POST   /api/analyze

Ruang Diksi:
    GET    /api/diksi/words
    GET    /api/diksi/words/<kata>
    POST   /api/diksi/search
    POST   /api/diksi/chat

Makna Puisi:
    POST   /api/makna
    GET    /api/poems/<id>/makna

Studio Puisi:
    GET    /api/drafts
    POST   /api/drafts
    GET    /api/drafts/<id>
    PUT    /api/drafts/<id>
    PATCH  /api/drafts/<id>
    DELETE /api/drafts/<id>
    POST   /api/studio/rekomendasi

Dashboard Sastra:
    GET    /api/dashboard?k=

Hanya puisi dengan in_public_library = 1 yang dapat diakses melalui
endpoint Perpustakaan. Draf Studio disimpan terpisah dan tidak menjadi
puisi publik.

Catatan:
    - Tabel drafts dibuat otomatis saat aplikasi dibuat (MySQL).
    - Endpoint draf belum memiliki autentikasi/pemisahan pemilik. Gunakan
      untuk pengembangan lokal atau demonstrasi, bukan deployment publik
      sebelum menambahkan autentikasi dan otorisasi.

Environment variable opsional:
    PUITIKA_CORS_ORIGIN
    PUITIKA_DEBUG=1
"""

import logging
import os

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

import analysis
import config
import dashboard_api
import diksi_api
import diksi_repo
import makna_api
import predict
import repo
import studio
import studio_api

from apiutil import ApiError, choice_arg, int_arg, q_arg
from db import Database
from labels import TEMA, TEMA_LIST


# ---------------------------------------------------------------------
# KONFIGURASI APLIKASI
# ---------------------------------------------------------------------

MAX_PER_PAGE = 50
DEFAULT_PER_PAGE = 12
MAX_TEXT = analysis.MAX_CHARS

log = logging.getLogger("puitika")
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "frontend",
)

CSP = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)


# ---------------------------------------------------------------------
# MEMBUAT APLIKASI FLASK
# ---------------------------------------------------------------------

def create_app(db=None, model_dir=None):
    app = Flask(
    __name__,
    static_folder=FRONTEND_DIR,
    static_url_path="/app",
    )

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    app.config["DB"] = db or Database.mysql()
    app.config["MODEL_DIR"] = model_dir or config.MODEL_DIR

    def _db():
        return app.config["DB"]
    @app.after_request
    def _frontend_security_headers(response):
        response.headers.setdefault(
            "X-Content-Type-Options",
            "nosniff",
        )

        if not request.path.startswith("/api/"):
            response.headers.setdefault(
                "Content-Security-Policy",
                CSP,
            )
            response.headers.setdefault(
                "Referrer-Policy",
                "no-referrer",
            )

        return response

    @app.get("/")
    def index():
        index_path = os.path.join(FRONTEND_DIR, "index.html")

        if not os.path.isfile(index_path):
            return jsonify(
                error="Frontend belum tersedia."
            ), 404

        return send_from_directory(FRONTEND_DIR, "index.html")

    # -----------------------------------------------------------------
    # SIAPKAN TABEL STUDIO PUISI
    # -----------------------------------------------------------------
    # Aman diulang karena studio_schema.sql menggunakan CREATE TABLE IF NOT EXISTS.
    # Untuk SQLite, studio.ensure_tables() tidak melakukan perubahan.
    # Jika MySQL belum tersedia, server tetap dapat dibuat; endpoint yang
    # memerlukan database akan mengembalikan error yang sesuai saat dipanggil.
    try:
        studio.ensure_tables(_db())
    except Exception as e:
        log.warning("Tabel Studio Puisi belum dapat disiapkan: %s", e)

    # -----------------------------------------------------------------
    # CORS UNTUK FRONTEND
    # -----------------------------------------------------------------
    cors = os.environ.get("PUITIKA_CORS_ORIGIN")

    if cors:

        @app.after_request
        def _cors(resp):
            resp.headers["Access-Control-Allow-Origin"] = cors
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            return resp

    # -----------------------------------------------------------------
    # PENANGANAN ERROR
    # -----------------------------------------------------------------
    @app.errorhandler(ApiError)
    def _api_error(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(404)
    def _404(_):
        return jsonify(error="Tidak ditemukan."), 404

    @app.errorhandler(405)
    def _405(_):
        return jsonify(error="Metode tidak diizinkan untuk alamat ini."), 405

    @app.errorhandler(413)
    def _413(_):
        return jsonify(error="Permintaan terlalu besar (maksimal 64 KB)."), 413

    @app.errorhandler(Exception)
    def _500(e):
        if isinstance(e, HTTPException):
            return jsonify(error=e.description), e.code

        log.exception("Kesalahan tak terduga: %s", e)
        return jsonify(error="Terjadi kesalahan di server."), 500

    # =================================================================
    # BAGIAN 1: STATUS APLIKASI
    # =================================================================
    @app.get("/api/health")
    def health():
        model_dir_now = app.config["MODEL_DIR"]
        models = {}

        # Periksa model klasifikasi tema.
        for name in predict.TARGETS:
            try:
                meta = predict.model_meta(name, model_dir_now)
            except Exception as e:
                log.warning("Pemeriksaan model %s gagal: %s", name, e)
                models[name] = {
                    "tersedia": False,
                    "error": "gagal dimuat",
                }
                continue

            if meta is None:
                models[name] = {"tersedia": False}
            else:
                models[name] = {
                    "tersedia": True,
                    "n_train": meta.get("n_train"),
                    "cv_macro_f1": meta.get("cv_macro_f1"),
                }

        # Periksa koneksi database utama.
        try:
            with _db().cursor() as cur:
                cur.execute("SELECT 1 AS ok").one()
            db_ok = True
        except Exception as e:
            log.warning("Cek database gagal: %s", e)
            db_ok = False

        # Periksa ketersediaan kamus diksi.
        # Jika tabel belum tersedia, server utama tetap berjalan.
        diksi = {"tersedia": False}

        if db_ok:
            try:
                diksi = {
                    "tersedia": True,
                    "n_entri": diksi_repo.count_entries(_db()),
                }
            except Exception as e:
                log.info("Data Ruang Diksi belum tersedia: %s", e)

        return jsonify(
            status="ok" if db_ok else "database_error",
            database=db_ok,
            model=models,
            diksi=diksi,
        ), (200 if db_ok else 503)

    # =================================================================
    # BAGIAN 2: PERPUSTAKAAN PUISI
    # =================================================================
    @app.get("/api/filters")
    def filters():
        data = repo.filter_counts(_db())

        # Tambahkan deskripsi tema.
        for item in data["tema"]:
            item["deskripsi"] = TEMA[item["label"]]

        return jsonify(data)

    # -----------------------------------------------------------------
    # DAFTAR PENYAIR
    # -----------------------------------------------------------------
    @app.get("/api/poets")
    def poets():
        limit = int_arg(
            "limit",
            50,
            1,
            200,
            clamp=True,
        )

        return jsonify(
            items=repo.list_poets(
                _db(),
                q=q_arg(),
                limit=limit,
            )
        )

    # -----------------------------------------------------------------
    # DAFTAR PUISI
    # -----------------------------------------------------------------
    @app.get("/api/poems")
    def poems():
        page = int_arg(
            "page",
            1,
            1,
            100000,
        )

        per_page = int_arg(
            "per_page",
            DEFAULT_PER_PAGE,
            1,
            MAX_PER_PAGE,
            clamp=True,
        )

        poet_id = int_arg(
            "poet_id",
            None,
            1,
        )

        tema = choice_arg(
            "tema",
            TEMA_LIST,
        )

        periode = (request.args.get("periode") or "").strip() or None
        if periode and len(periode) > 60:
            raise ApiError(400, "Parameter 'periode' maksimal 60 karakter.")

        sort = choice_arg("sort", list(repo.SORTS)) or "title"

        return jsonify(
            repo.list_poems(
                _db(),
                q=q_arg(),
                poet_id=poet_id,
                tema=tema,
                periode=periode,
                sort=sort,
                page=page,
                per_page=per_page,
            )
        )

    # -----------------------------------------------------------------
    # DETAIL PUISI
    # -----------------------------------------------------------------
    @app.get("/api/poems/<int:poem_id>")
    def poem(poem_id):
        result = repo.get_poem(_db(), poem_id)

        if result is None:
            raise ApiError(404, "Puisi tidak ditemukan.")

        return jsonify(result)

    # -----------------------------------------------------------------
    # ANALISIS PUISI DARI PERPUSTAKAAN (ANALISIS UMUM)
    # -----------------------------------------------------------------
    @app.get("/api/poems/<int:poem_id>/analysis")
    def poem_analysis(poem_id):
        poem_data = repo.get_poem(_db(), poem_id)

        if poem_data is None:
            raise ApiError(404, "Puisi tidak ditemukan.")

        result = analysis.analyze(
            poem_data["body"],
            app.config["MODEL_DIR"],
        )

        result.update(
            poem_id=poem_data["id"],
            title=poem_data["title"],
            label_tersimpan={
                "tema": poem_data["tema"],
            },
        )

        return jsonify(result)

    # -----------------------------------------------------------------
    # ANALISIS TEKS BARU (UNTUK STUDIO / EDITOR)
    # -----------------------------------------------------------------
    @app.post("/api/analyze")
    def analyze():
        payload = request.get_json(silent=True)

        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("text"), str)
        ):
            raise ApiError(
                400,
                'Kirim JSON berbentuk {"text": "..."}.',
            )

        text = payload["text"].strip()

        if not text:
            raise ApiError(400, "Teks puisi kosong.")

        if len(text) > MAX_TEXT:
            raise ApiError(
                400,
                f"Teks terlalu panjang (maksimal {MAX_TEXT} karakter).",
            )

        if not analysis.tokenize(text, stopwords=False):
            raise ApiError(
                400,
                "Teks tidak mengandung kata yang bisa dianalisis.",
            )

        result = analysis.analyze(
            text,
            app.config["MODEL_DIR"],
        )

        # Hasil tema dan sentimen merupakan alat bantu,
        # bukan penentu mutlak makna puisi.
        result["catatan"] = (
            "Prediksi tema dan analisis sentimen merupakan "
            "alat bantu eksplorasi, bukan penentu mutlak "
            "makna puisi."
        )

        return jsonify(result)

    # =================================================================
    # BAGIAN 3: PENDAFTARAN MODUL API
    # =================================================================
    # Ruang Diksi: pencarian kosakata dan chatbot Teman Diksi.
    diksi_api.register(app)

    # Makna Puisi: interpretasi ringan, diksi penting, dan sentimen.
    makna_api.register(app)

    # Studio Puisi: CRUD draf dan rekomendasi tema/diksi.
    studio_api.register(app)

    # Dashboard Sastra: statistik korpus, distribusi tema/periode, dan clustering.
    dashboard_api.register(app)

    return app


# ---------------------------------------------------------------------
# MENJALANKAN SERVER
# ---------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    create_app().run(
        host="127.0.0.1",
        port=5000,
        debug=os.environ.get("PUITIKA_DEBUG") == "1",
    )
