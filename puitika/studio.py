"""Studio Puisi: draf (simpan, ubah, hapus) dan rekomendasi diksi + tema untuk teks yang sedang ditulis.

Rekomendasi diksi punya dua bagian, keduanya dari kamus Ruang Diksi:
  padanan : kata di teksmu yang punya sinonim di kamus, beserta nuansa tiap sinonim (kata apa di baris berapa)
  terkait : kata kamus yang berhubungan dengan isi teksmu (pencarian deskripsi TF-IDF), yang belum kamu pakai
Keduanya HANYA saran: kamus kecil (lihat README), jadi banyak kata wajar tidak punya padanan.
"""
import os

import analysis
import diksi_repo as dr
from db import apply_sql_file
from labels import TEMA_LIST
from preprocess import tokenize
from repo import excerpt

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio_schema.sql")
MAX_TITLE = 200
MAX_BODY = analysis.MAX_CHARS


def ensure_tables(db):
    if db.kind == "mysql":
        apply_sql_file(db, SCHEMA)


def tables_ready(db):
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM drafts").one()
        return True
    except Exception:
        return False


def _item(r, with_body):
    d = {"id": r["id"], "judul": r["title"], "tema": r["tema"], "dibuat": str(r["created_at"]), "diubah": str(r["updated_at"])}
    if with_body:
        d["isi"] = r["body"]
    else:
        d["kutipan"] = excerpt(r["body"])
        d["n_kata"] = len(tokenize(r["body"], stopwords=False, min_len=1))
    return d


_COLS = "id, title, body, tema, created_at, updated_at"


def create_draft(db, title, body, tema):
    with db.cursor(commit=True) as cur:
        cur.execute("INSERT INTO drafts (title, body, tema) VALUES (%s, %s, %s)", (title, body, tema))
        new_id = cur.lastrowid
    return get_draft(db, new_id)


def get_draft(db, draft_id):
    with db.cursor() as cur:
        r = cur.execute(f"SELECT {_COLS} FROM drafts WHERE id = %s", (draft_id,)).one()
    return _item(r, True) if r else None


def list_drafts(db, page=1, per_page=20):
    with db.cursor() as cur:
        total = cur.execute("SELECT COUNT(*) AS n FROM drafts").one()["n"]
        rows = cur.execute(
            f"SELECT {_COLS} FROM drafts ORDER BY updated_at DESC, id DESC LIMIT %s OFFSET %s",
            (per_page, (page - 1) * per_page),
        ).all()
    return {
        "items": [_item(r, False) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    }


def update_draft(db, draft_id, fields):
    """fields: subset dari {'title','body','tema'} (nilai sudah divalidasi). None bila draf tidak ada."""
    cols = {"title": "title", "body": "body", "tema": "tema"}
    sets = [f"{cols[k]} = %s" for k in fields]
    with db.cursor(commit=True) as cur:
        exists = cur.execute("SELECT id FROM drafts WHERE id = %s", (draft_id,)).one()
        if not exists:
            return None
        cur.execute(
            f"UPDATE drafts SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            list(fields.values()) + [draft_id],
        )
    return get_draft(db, draft_id)


def delete_draft(db, draft_id):
    with db.cursor(commit=True) as cur:
        cur.execute("DELETE FROM drafts WHERE id = %s", (draft_id,))
        return cur.rowcount > 0


# ------------------------------------------------------------------ rekomendasi


def diksi_padanan(db, text, max_items=10):
    """Kata dalam teks yang ada di kamus dan punya sinonim. Satu entri per kata (kemunculan pertama)."""
    keys = dr.word_keys(db)
    seen, out = set(), []
    for n, line in enumerate(analysis.clean_lines(text), start=1):
        for tok in tokenize(line, stopwords=False, min_len=2):
            if tok in keys and tok not in seen:
                seen.add(tok)
                e = dr.get_entry(db, tok)
                syn = e["relasi"]["sinonim"] if e else []
                if syn:
                    out.append({"kata": e["kata"], "baris": n, "padanan": [{"kata": s["kata"], "nuansa": s["nuansa"]} for s in syn]})
                    if len(out) >= max_items:
                        return out
    return out


def diksi_terkait(db, text, top_k=6):
    used = set(tokenize(text, stopwords=False, min_len=2))
    hasil = dr.search_description(db, text, top_k=top_k + 10)
    return [h for h in hasil if dr.word_key(h["kata"]) not in used][:top_k]


def recommend(db, text, model_dir):
    """Rekomendasi tema (model) + diksi (kamus). Bagian yang tidak tersedia bernilai None, tidak melempar error."""
    saran = analysis.model_suggestions(text, model_dir)
    try:
        diksi = {"padanan": diksi_padanan(db, text), "terkait": diksi_terkait(db, text)}
    except Exception:  # tabel kamus belum dimuat
        diksi = None
    return {
        "tema": saran["tema"],
        "diksi": diksi,
        "catatan": "Semua ini hanya saran. Penulis yang memutuskan tema dan pilihan kata.",
        **({"galat_model": saran["error"]} if saran.get("error") else {}),
    }
