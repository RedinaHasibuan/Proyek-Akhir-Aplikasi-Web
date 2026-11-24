"""Lapisan akses database yang tipis.

MySQL dipakai untuk aplikasi sungguhan (pengaturan dari config.py / environment variable).
SQLite HANYA untuk uji otomatis (test_backend.py); skema SQLite dibuat di file uji itu.
Semua SQL di proyek ini memakai placeholder %s; untuk SQLite diganti ke ? secara otomatis,
jadi SQL harus tetap portabel (tanpa fitur khusus MySQL) dan tanpa tanda % di dalam teks SQL.
"""
import sqlite3
from contextlib import contextmanager

import config


class _Cursor:
    def __init__(self, cur, kind):
        self._cur, self._kind = cur, kind

    def execute(self, sql, params=()):
        if self._kind == "sqlite":
            sql = sql.replace("%s", "?")
        self._cur.execute(sql, tuple(params))
        return self

    def all(self):
        return [dict(r) for r in self._cur.fetchall()]

    def one(self):
        r = self._cur.fetchone()
        return dict(r) if r else None

    @property
    def rowcount(self):
        return self._cur.rowcount


class Database:
    def __init__(self, kind="mysql", sqlite_path=None):
        if kind not in ("mysql", "sqlite"):
            raise ValueError("kind harus 'mysql' atau 'sqlite'")
        self.kind = kind
        self.sqlite_path = sqlite_path

    @classmethod
    def mysql(cls):
        return cls("mysql")

    @classmethod
    def sqlite(cls, path):
        return cls("sqlite", path)

    def _connect(self):
        if self.kind == "sqlite":
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        import pymysql  # diimpor di sini agar uji SQLite tidak butuh PyMySQL

        return pymysql.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    @contextmanager
    def cursor(self, commit=False):
        """Beri kursor. Dengan commit=True, perubahan disimpan bila blok selesai tanpa error."""
        conn = self._connect()
        try:
            yield _Cursor(conn.cursor(), self.kind)
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def ensure_schema(db):
    """Pastikan kolom poem_labels.is_primary ada (untuk DB yang dibuat dari schema.sql lama).

    Aman dijalankan berulang. Mengembalikan True bila ada perubahan.
    """
    if db.kind != "mysql":
        return False
    with db.cursor(commit=True) as cur:
        t = cur.execute(
            "SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'poem_labels'",
            (config.DB_NAME,),
        ).one()
        if not t["n"]:
            raise RuntimeError("Tabel poem_labels belum ada. Jalankan dulu: python load_to_db.py --init")
        c = cur.execute(
            "SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s "
            "AND TABLE_NAME = 'poem_labels' AND COLUMN_NAME = 'is_primary'",
            (config.DB_NAME,),
        ).one()
        if c["n"]:
            return False
        cur.execute("ALTER TABLE poem_labels ADD COLUMN is_primary TINYINT(1) NOT NULL DEFAULT 1 AFTER label")
        return True
