"""Endpoint Makna Puisi (didaftarkan oleh app.create_app).

  POST /api/makna             {"text": "..."} -> analisis makna ringan untuk teks apa pun (juga draf di Studio)
  GET  /api/poems/<id>/makna  analisis yang sama untuk puisi publik di Perpustakaan
"""
from flask import jsonify

import analysis
import makna
import repo
from apiutil import ApiError, json_text


def register(app):
    def db():
        return app.config["DB"]

    @app.post("/api/makna")
    def makna_text():
        text, _ = json_text("text", analysis.MAX_CHARS)
        if not analysis.tokenize(text, stopwords=False):
            raise ApiError(400, "Teks tidak mengandung kata yang bisa dianalisis.")
        return jsonify(makna.analyze_makna(db(), text, app.config["MODEL_DIR"]))

    @app.get("/api/poems/<int:poem_id>/makna")
    def makna_poem(poem_id):
        p = repo.get_poem(db(), poem_id)
        if p is None:
            raise ApiError(404, "Puisi tidak ditemukan.")
        res = makna.analyze_makna(db(), p["body"], app.config["MODEL_DIR"])
        res.update(poem_id=p["id"], title=p["title"])
        return jsonify(res)
