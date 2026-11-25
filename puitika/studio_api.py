"""Endpoint Studio Puisi (didaftarkan oleh app.create_app).

  GET    /api/drafts?page=&per_page=       daftar draf (terbaru diubah dulu)
  POST   /api/drafts                       {"judul"?, "isi"?, "tema"?} -> draf baru (minimal judul atau isi terisi)
  GET    /api/drafts/<id>                  satu draf
  PUT    /api/drafts/<id>                  ubah sebagian: {"judul"?, "isi"?, "tema"?}  (tema null = hapus tema)
  DELETE /api/drafts/<id>                  hapus draf
  POST   /api/studio/rekomendasi           {"text": "..."} -> rekomendasi tema + diksi (padanan, terkait)

Draf bukan puisi publik: tidak pernah muncul di Perpustakaan atau Dashboard. Tanpa akun pengguna.
Bila tabel drafts belum ada: 503 (jalankan python app.py sekali, tabel dibuat otomatis).
"""
from flask import jsonify, request

import studio
from apiutil import ApiError, int_arg, json_text
from labels import TEMA_LIST


def register(app):
    def db():
        return app.config["DB"]

    def ready():
        if not studio.tables_ready(db()):
            raise ApiError(503, "Tabel draf belum ada. Jalankan python app.py (tabel dibuat otomatis).")

    def parse_fields(payload, partial):
        fields = {}
        if "judul" in payload:
            v = payload["judul"]
            if not isinstance(v, str) or len(v.strip()) > studio.MAX_TITLE:
                raise ApiError(400, f"'judul' harus teks maksimal {studio.MAX_TITLE} karakter.")
            fields["title"] = v.strip()
        if "isi" in payload:
            v = payload["isi"]
            if not isinstance(v, str) or len(v) > studio.MAX_BODY:
                raise ApiError(400, f"'isi' harus teks maksimal {studio.MAX_BODY} karakter.")
            fields["body"] = v
        if "tema" in payload:
            v = payload["tema"]
            if v is not None and v not in TEMA_LIST:
                raise ApiError(400, f"'tema' tidak valid. Pilihan: {', '.join(TEMA_LIST)} atau null.")
            fields["tema"] = v
        if partial and not fields:
            raise ApiError(400, "Kirim minimal satu dari: judul, isi, tema.")
        return fields

    def json_body():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ApiError(400, "Kirim JSON objek, misalnya {\"judul\": \"...\", \"isi\": \"...\"}.")
        return payload

    @app.get("/api/drafts")
    def drafts_list():
        ready()
        return jsonify(studio.list_drafts(db(), int_arg("page", 1, 1, 100000), int_arg("per_page", 20, 1, 50, clamp=True)))

    @app.post("/api/drafts")
    def drafts_create():
        ready()
        fields = parse_fields(json_body(), partial=False)
        title, body, tema = fields.get("title", ""), fields.get("body", ""), fields.get("tema")
        if not title and not body.strip():
            raise ApiError(400, "Draf kosong: isi minimal judul atau isi.")
        return jsonify(studio.create_draft(db(), title, body, tema)), 201

    @app.get("/api/drafts/<int:draft_id>")
    def drafts_get(draft_id):
        ready()
        d = studio.get_draft(db(), draft_id)
        if d is None:
            raise ApiError(404, "Draf tidak ditemukan.")
        return jsonify(d)

    @app.route("/api/drafts/<int:draft_id>", methods=["PUT", "PATCH"])
    def drafts_update(draft_id):
        ready()
        fields = parse_fields(json_body(), partial=True)
        d = studio.update_draft(db(), draft_id, fields)
        if d is None:
            raise ApiError(404, "Draf tidak ditemukan.")
        return jsonify(d)

    @app.delete("/api/drafts/<int:draft_id>")
    def drafts_delete(draft_id):
        ready()
        if not studio.delete_draft(db(), draft_id):
            raise ApiError(404, "Draf tidak ditemukan.")
        return jsonify(terhapus=draft_id)

    @app.post("/api/studio/rekomendasi")
    def studio_recommend():
        text, _ = json_text("text", studio.MAX_BODY)
        if not studio.tokenize(text, stopwords=False):
            raise ApiError(400, "Teks tidak mengandung kata yang bisa dianalisis.")
        return jsonify(studio.recommend(db(), text, app.config["MODEL_DIR"]))
