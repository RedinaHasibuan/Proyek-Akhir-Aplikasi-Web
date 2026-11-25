"""Endpoint Dashboard Sastra (didaftarkan oleh app.create_app).

  GET /api/dashboard?k=   statistik korpus publik, distribusi tema/periode, penyair teratas, frekuensi kata, clustering.
                          k (3-8, opsional) = jumlah klaster; tanpa k dipilih otomatis lewat silhouette.
Hasil di-cache 10 menit (muat ulang data: tunggu atau restart server).
"""
from flask import jsonify

import dashboard
from apiutil import int_arg


def register(app):
    @app.get("/api/dashboard")
    def dashboard_get():
        k = int_arg("k", None, 3, 8)
        return jsonify(dashboard.get_dashboard(app.config["DB"], k))
