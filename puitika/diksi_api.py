"""Endpoint Ruang Diksi (didaftarkan oleh app.create_app).

  GET  /api/diksi/words?q=&emosi=&page=&per_page=   daftar kata (urut abjad)
  GET  /api/diksi/words/<kata>                      detail kata + relasi (sinonim, antonim, terkait)
  POST /api/diksi/search   {"deskripsi": "...", "emosi": "sedih"?, "top_k": 5?}   cari kata dari deskripsi makna
  POST /api/diksi/chat     {"pesan": "..."}                                       Teman Diksi (rule-based)

Bila tabel diksi belum dimuat, semua endpoint ini menjawab 503 dengan petunjuk menjalankan load_diksi.py.
"""
from flask import jsonify, request

import diksi_repo as dr
import teman_diksi
from apiutil import ApiError, choice_arg, int_arg, json_text, q_arg
from labels import EMOSI_LIST

MAX_DESKRIPSI = 300


def register(app):
    def db():
        return app.config["DB"]

    def ready():
        try:
            return dr.count_entries(db())
        except Exception:
            raise ApiError(503, "Data Ruang Diksi belum dimuat. Jalankan: python load_diksi.py --init")

    @app.get("/api/diksi/words")
    def diksi_words():
        ready()
        page = int_arg("page", 1, 1, 100000)
        per_page = int_arg("per_page", 30, 1, 100, clamp=True)
        return jsonify(dr.list_words(db(), q=q_arg(), emosi=choice_arg("emosi", EMOSI_LIST), page=page, per_page=per_page))

    @app.get("/api/diksi/words/<kata>")
    def diksi_word(kata):
        ready()
        if len(kata) > 100:
            raise ApiError(404, "Kata tidak ditemukan.")
        e = dr.get_entry(db(), kata)
        if e is None:
            raise ApiError(404, "Kata tidak ditemukan.")
        return jsonify(e)

    @app.post("/api/diksi/search")
    def diksi_search():
        ready()
        text, payload = json_text("deskripsi", MAX_DESKRIPSI, "Deskripsi")
        emosi = payload.get("emosi")
        if emosi is not None and emosi not in EMOSI_LIST:
            raise ApiError(400, f"Field 'emosi' tidak valid. Pilihan: {', '.join(EMOSI_LIST)}.")
        top_k = payload.get("top_k", 5)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 10:
            raise ApiError(400, "Field 'top_k' harus bilangan bulat 1-10.")
        hasil = dr.search_description(db(), text, top_k=top_k, emosi=emosi)
        return jsonify(
            hasil=hasil,
            catatan="Pencocokan berdasarkan kemiripan kata, bukan pemahaman makna; periksa nuansa tiap kata sebelum memakainya.",
        )

    @app.post("/api/diksi/chat")
    def diksi_chat():
        ready()
        text, _ = json_text("pesan", teman_diksi.MAX_PESAN, "Pesan")
        return jsonify(teman_diksi.respond(db(), text))
