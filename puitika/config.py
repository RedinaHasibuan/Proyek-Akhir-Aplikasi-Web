"""Konfigurasi dibaca dari environment variable supaya password tidak masuk kode.

Default cocok untuk XAMPP/Laragon (user root, tanpa password).
Ubah lewat environment variable bila perlu:
  PUITIKA_DB_HOST, PUITIKA_DB_PORT, PUITIKA_DB_USER, PUITIKA_DB_PASSWORD, PUITIKA_DB_NAME
"""
import os

DB_HOST = os.environ.get("PUITIKA_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("PUITIKA_DB_PORT", "3306"))
DB_USER = os.environ.get("PUITIKA_DB_USER", "root")
DB_PASSWORD = os.environ.get("PUITIKA_DB_PASSWORD", "")
DB_NAME = os.environ.get("PUITIKA_DB_NAME", "puitika")

# Wikimedia meminta User-Agent yang jelas + kontak. Isi email/URL kamu.
CONTACT = os.environ.get("PUITIKA_CONTACT", "ISI_EMAIL_KAMU")
USER_AGENT = f"PuitikaStudentProject/0.1 (tugas kuliah; kontak: {CONTACT})"

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
CLEAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "clean")
