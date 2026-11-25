"""Lapisan akses database yang tipis.

MySQL dipakai untuk aplikasi sungguhan (pengaturan dari config.py / environment variable).
SQLite HANYA untuk uji otomatis; skema SQLite dibuat di file uji.
Semua SQL di proyek ini memakai placeholder %s; untuk SQLite diganti ke ? secara otomatis.
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
        return [dict(row) for row in self._cur.fetchall()]

    def one(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        """ID baris terakhir yang berhasil ditambahkan."""
        return self._cur.lastrowid


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

        import pymysql  # Diimpor di sini agar tes SQLite tidak membutuhkan PyMySQL.

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
        """Beri kursor. Commit dilakukan hanya bila commit=True dan blok sukses."""
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


# Migrasi tambahan yang aman dijalankan berulang kali.
MIGRATIONS = [
    (
        "poem_labels",
        "is_primary",
        "ALTER TABLE poem_labels ADD COLUMN is_primary TINYINT(1) NOT NULL DEFAULT 1 AFTER label",
    ),
    (
        "poets",
        "period",
        "ALTER TABLE poets ADD COLUMN period VARCHAR(60) NULL",
    ),
]


def ensure_schema(db):
    """Pastikan kolom tambahan yang dibutuhkan proyek tersedia.

    Menambahkan poem_labels.is_primary dan poets.period bila belum ada.
    Aman dipanggil berulang kali. Mengembalikan True bila ada perubahan.
    SQLite tidak dimigrasikan oleh fungsi ini; skema SQLite disiapkan oleh tes.
    """
    if db.kind != "mysql":
        return False

    changed = False
    with db.cursor(commit=True) as cur:
        for table, column, ddl in MIGRATIONS:
            table_exists = cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (config.DB_NAME, table),
            ).one()
            if not table_exists or not table_exists["n"]:
                raise RuntimeError(
                    f"Tabel {table} belum ada. Jalankan dulu: python load_to_db.py --init"
                )

            column_exists = cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                (config.DB_NAME, table, column),
            ).one()
            if not column_exists or not column_exists["n"]:
                cur.execute(ddl)
                changed = True

    return changed


def apply_sql_file(db, path):
    """Jalankan file SQL sederhana; pernyataan dipisahkan dengan titik koma.

    Baris komentar yang diawali -- dilewati. File SQL harus berupa DDL sederhana,
    tanpa titik koma di dalam literal string atau stored procedure.
    """
    with open(path, encoding="utf-8") as file:
        lines = [
            line
            for line in file.read().splitlines()
            if not line.strip().startswith("--")
        ]

    statements = [
        statement.strip()
        for statement in "\n".join(lines).split(";")
        if statement.strip()
    ]

    with db.cursor(commit=True) as cur:
        for statement in statements:
            cur.execute(statement)

    return len(statements)
