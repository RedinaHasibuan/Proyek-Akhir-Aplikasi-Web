
"""API Puitika menggunakan Flask.

Jalankan:
    python app.py

Alamat:
    http://127.0.0.1:5000/api/health
"""

import logging
import os

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

import analysis
import config
import predict
import repo
from db import Database
from labels import TEMA, TEMA_LIST

MAX_Q = 100
MAX_PER_PAGE = 50
DEFAULT_PER_PAGE = 12
MAX_TEXT = analysis.MAX_CHARS

log = logging.getLogger("puitika")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _int_arg(name, default, lo, hi=None, clamp=False):
    raw = request.args.get(name)

    if raw is None or raw == "":
        return default

    try:
        value = int(raw)
    except ValueError:
        raise ApiError(
            400,
            f"Parameter '{name}' harus bilangan bulat."
        )

    if value < lo:
        raise ApiError(400, f"Parameter '{name}' minimal {lo}.")

    if hi is not None and value > hi:
        if clamp:
            return hi
        raise ApiError(400, f"Parameter '{name}' maksimal {hi}.")

    return value


def _choice_arg(name, valid):
    value = request.args.get(name)

    if value is None or value == "":
        return None

    if value not in valid:
        raise ApiError(
            400,
            f"Parameter '{name}' tidak valid. "
            f"Pilihan: {', '.join(valid)}."
        )

    return value


def _q_arg():
    q = (request.args.get("q") or "").strip()

    if len(q) > MAX_Q:
        raise ApiError(
            400,
            f"Parameter 'q' maksimal {MAX_Q} karakter."
        )

    return q or None


def create_app(db=None, model_dir=None):
    app = Flask(__name__)

    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    app.config["DB"] = db or Database.mysql()
    app.config["MODEL_DIR"] = model_dir or config.MODEL_DIR

    def _db():
        return app.config["DB"]

    cors = os.environ.get("PUITIKA_CORS_ORIGIN")

    if cors:

        @app.after_request
        def _cors(resp):
            resp.headers["Access-Control-Allow-Origin"] = cors
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            return resp

    # --------------------------------------------------
    # PENANGANAN ERROR
    # --------------------------------------------------

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
    @app.get("/api/health")
    def health():
        model_dir = app.config["MODEL_DIR"]

        # Periksa ketersediaan model tema
        model_path = os.path.join(model_dir, "tema.joblib")

        if os.path.isfile(model_path):
            model = {"tersedia": True}
        else:
            model = {
                "tersedia": False,
                "error": "Model tema belum tersedia. Jalankan train_model.py."
            }

        # Periksa koneksi database
        try:
            with _db().cursor() as cur:
                cur.execute("SELECT 1 AS ok").one()

            db_ok = True

        except Exception as e:
            log.warning("Cek database gagal: %s", e)
            db_ok = False

        return jsonify(
            status="ok" if db_ok else "database_error",
            database=db_ok,
            model={"tema": model},
        ), (200 if db_ok else 503)


    # --------------------------------------------------
    # FILTER TEMA
    # --------------------------------------------------

    @app.get("/api/filters")
    def filters():
        data = repo.filter_counts(_db())

        for item in data["tema"]:
            item["deskripsi"] = TEMA[item["label"]]

        return jsonify(data)

    # --------------------------------------------------
    # DAFTAR PENYAIR
    # --------------------------------------------------

    @app.get("/api/poets")
    def poets():
        limit = _int_arg("limit", 50, 1, 200, clamp=True)

        return jsonify(
            items=repo.list_poets(
                _db(),
                q=_q_arg(),
                limit=limit,
            )
        )

    # --------------------------------------------------
    # DAFTAR PUISI
    # --------------------------------------------------

    @app.get("/api/poems")
    def poems():
        page = _int_arg("page", 1, 1, 100000)

        per_page = _int_arg(
            "per_page",
            DEFAULT_PER_PAGE,
            1,
            MAX_PER_PAGE,
            clamp=True,
        )

        poet_id = _int_arg("poet_id", None, 1)
        tema = _choice_arg("tema", TEMA_LIST)
        sort = _choice_arg("sort", list(repo.SORTS)) or "title"

        return jsonify(
            repo.list_poems(
                _db(),
                q=_q_arg(),
                poet_id=poet_id,
                tema=tema,
                sort=sort,
                page=page,
                per_page=per_page,
            )
        )

    # --------------------------------------------------
    # DETAIL PUISI
    # --------------------------------------------------

    @app.get("/api/poems/<int:poem_id>")
    def poem(poem_id):
        result = repo.get_poem(_db(), poem_id)

        if result is None:
            raise ApiError(404, "Puisi tidak ditemukan.")

        return jsonify(result)

    # --------------------------------------------------
    # ANALISIS PUISI DARI PERPUSTAKAAN
    # --------------------------------------------------

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

    # --------------------------------------------------
    # ANALISIS TEKS DARI STUDIO PUISI
    # --------------------------------------------------

    @app.post("/api/analyze")
    def analyze():
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict) or not isinstance(
            payload.get("text"), str
        ):
            raise ApiError(
                400,
                'Kirim JSON berbentuk {"text": "..."} .'
            )

        text = payload["text"].strip()

        if not text:
            raise ApiError(400, "Teks puisi kosong.")

        if len(text) > MAX_TEXT:
            raise ApiError(
                400,
                f"Teks terlalu panjang (maksimal {MAX_TEXT} karakter)."
            )

        if not analysis.tokenize(text, stopwords=False):
            raise ApiError(
                400,
                "Teks tidak mengandung kata yang bisa dianalisis."
            )

        result = analysis.analyze(
            text,
            app.config["MODEL_DIR"],
        )

        return jsonify(result)

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    create_app().run(
        host="127.0.0.1",
        port=5000,
        debug=os.environ.get("PUITIKA_DEBUG") == "1",
    )
