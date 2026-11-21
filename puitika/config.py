"""Konfigurasi aplikasi Puitika."""

import os

# Konfigurasi database MySQL
DB_HOST = os.environ.get("PUITIKA_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("PUITIKA_DB_PORT", "3306"))
DB_USER = os.environ.get("PUITIKA_DB_USER", "root")
DB_PASSWORD = os.environ.get("PUITIKA_DB_PASSWORD", "")
DB_NAME = os.environ.get("PUITIKA_DB_NAME", "puitika")

# Identitas crawler Wikimedia
CONTACT = os.environ.get("PUITIKA_CONTACT", "ISI_EMAIL_KAMU")
USER_AGENT = f"PuitikaStudentProject/0.1 (tugas kuliah; kontak: {CONTACT})"

# Lokasi folder proyek
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
CLEAN_DIR = os.path.join(BASE_DIR, "data", "clean")
LABEL_DIR = os.path.join(BASE_DIR, "data", "labels")
MODEL_DIR = os.path.join(BASE_DIR, "models")
REPORT_DIR = os.path.join(BASE_DIR, "reports")