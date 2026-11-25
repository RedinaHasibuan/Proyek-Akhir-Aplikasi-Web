"""Query perpustakaan puisi (hanya baca) dan penulisan label.

Aturan penting:
  * Hanya puisi dengan in_public_library = 1 yang pernah keluar dari fungsi baca di sini.
    Puisi ID Puisi (0) dan draf pengguna tidak bisa diambil lewat API, apa pun parameternya.
  * Satu puisi punya label tema dari SATU sumber saja: label manual/pengguna menggantikan label model
    (ditegakkan oleh set_labels dan predict_library.py), jadi filter tidak perlu menimbang prioritas sumber.
  * Hanya TEMA yang diklasifikasi (satu label per puisi, is_primary=1). Klasifikasi emosi dibatalkan pada v5.
"""
from labels import TEMA_LIST

SORTS = {
    "title": "p.title ASC, p.id ASC",
    "poet": "t.name ASC, p.title ASC, p.id ASC",
    "words": "p.n_words DESC, p.id ASC",
    "newest": "p.id DESC",
}


def like_pattern(term):
    """Pola LIKE aman: %, _ dan ! dari pengguna dianggap huruf biasa (ESCAPE '!')."""
    esc = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{esc}%"


def excerpt(body, max_lines=4, max_chars=220):
    lines = [ln.strip() for ln in body.split("\n") if ln.strip() and set(ln.strip()) != {"."}]
    text = "\n".join(lines[:max_lines])
    if len(text) > max_chars or len(lines) > max_lines:
        text = text[:max_chars].rstrip() + "…"
    return text


def _score(v):
    return None if v is None else float(v)  # MySQL mengembalikan Decimal; JSON butuh float


def _labels_for(cur, poem_ids):
    out = {pid: {"tema": None} for pid in poem_ids}
    if not poem_ids:
        return out
    marks = ",".join(["%s"] * len(poem_ids))
    rows = cur.execute(
        "SELECT poem_id, label, score, source FROM poem_labels "
        f"WHERE label_type = 'tema' AND poem_id IN ({marks}) ORDER BY label ASC",
        poem_ids,
    ).all()
    for r in rows:
        out[r["poem_id"]]["tema"] = {"label": r["label"], "source": r["source"], "score": _score(r["score"])}
    return out


def _poem_row(r, labels, with_body):
    item = {
        "id": r["id"],
        "title": r["title"],
        "poet": {"id": r["poet_id"], "name": r["poet_name"], "periode": r["poet_period"]} if r["poet_id"] else None,
        "n_lines": r["n_lines"],
        "n_words": r["n_words"],
        "tema": labels["tema"],
    }
    if with_body:
        item.update(body=r["body"], n_stanzas=r["n_stanzas"], source_url=r["source_url"], license=r["license"])
    else:
        item["excerpt"] = excerpt(r["body"])
    return item


def list_poems(db, *, q=None, poet_id=None, tema=None, periode=None, sort="title", page=1, per_page=12):
    """Daftar puisi publik dengan filter dan paginasi. Nilai tema/sort harus sudah divalidasi pemanggil.

    periode: nama periode persis seperti di poets.period (lihat filter_counts()['periode'])."""
    if tema is not None and tema not in TEMA_LIST:
        raise ValueError("tema tidak valid")
    order = SORTS[sort]  # KeyError bila tidak dikenal: daftar putih, bukan teks dari pengguna

    where, params = ["p.in_public_library = 1"], []
    if q:
        pat = like_pattern(q)
        where.append("(p.title LIKE %s ESCAPE '!' OR t.name LIKE %s ESCAPE '!' OR p.body LIKE %s ESCAPE '!')")
        params += [pat, pat, pat]
    if poet_id is not None:
        where.append("p.poet_id = %s")
        params.append(poet_id)
    if periode:
        where.append("t.period = %s")
        params.append(periode)
    if tema:
        where.append("EXISTS (SELECT 1 FROM poem_labels l WHERE l.poem_id = p.id AND l.label_type = 'tema' AND l.label = %s)")
        params.append(tema)
    base = "FROM poems p LEFT JOIN poets t ON t.id = p.poet_id WHERE " + " AND ".join(where)

    with db.cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) AS n {base}", params).one()["n"]
        rows = cur.execute(
            "SELECT p.id, p.title, p.body, p.n_lines, p.n_words, p.n_stanzas, p.source_url, p.license, "
            f"t.id AS poet_id, t.name AS poet_name, t.period AS poet_period {base} ORDER BY {order} LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page],
        ).all()
        labels = _labels_for(cur, [r["id"] for r in rows])
    return {
        "items": [_poem_row(r, labels[r["id"]], with_body=False) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    }


def get_poem(db, poem_id):
    """Satu puisi publik lengkap, atau None bila tidak ada / bukan puisi publik."""
    with db.cursor() as cur:
        r = cur.execute(
            "SELECT p.id, p.title, p.body, p.n_lines, p.n_words, p.n_stanzas, p.source_url, p.license, "
            "t.id AS poet_id, t.name AS poet_name, t.period AS poet_period "
            "FROM poems p LEFT JOIN poets t ON t.id = p.poet_id WHERE p.id = %s AND p.in_public_library = 1",
            (poem_id,),
        ).one()
        if not r:
            return None
        labels = _labels_for(cur, [poem_id])[poem_id]
    return _poem_row(r, labels, with_body=True)


def list_poets(db, q=None, limit=50):
    where, params = ["p.in_public_library = 1"], []
    if q:
        where.append("t.name LIKE %s ESCAPE '!'")
        params.append(like_pattern(q))
    with db.cursor() as cur:
        rows = cur.execute(
            "SELECT t.id, t.name, COUNT(*) AS n FROM poets t JOIN poems p ON p.poet_id = t.id "
            f"WHERE {' AND '.join(where)} GROUP BY t.id, t.name ORDER BY n DESC, t.name ASC LIMIT %s",
            params + [limit],
        ).all()
    return [{"id": r["id"], "name": r["name"], "poem_count": r["n"]} for r in rows]


def filter_counts(db):
    """Jumlah puisi publik per tema, dan berapa yang belum berlabel."""
    out = {}
    with db.cursor() as cur:
        total = cur.execute("SELECT COUNT(*) AS n FROM poems WHERE in_public_library = 1").one()["n"]
        out["total_public"] = total
        for kind, valid in (("tema", TEMA_LIST),):
            rows = cur.execute(
                "SELECT l.label, COUNT(DISTINCT l.poem_id) AS n FROM poem_labels l JOIN poems p ON p.id = l.poem_id "
                "WHERE p.in_public_library = 1 AND l.label_type = %s GROUP BY l.label",
                (kind,),
            ).all()
            counts = {r["label"]: r["n"] for r in rows}
            out[kind] = [{"label": lab, "count": counts.get(lab, 0)} for lab in valid]
            labeled = cur.execute(
                "SELECT COUNT(DISTINCT l.poem_id) AS n FROM poem_labels l JOIN poems p ON p.id = l.poem_id "
                "WHERE p.in_public_library = 1 AND l.label_type = %s",
                (kind,),
            ).one()["n"]
            out[f"{kind}_unlabeled"] = total - labeled
        rows = cur.execute(
            "SELECT t.period AS label, COUNT(*) AS n FROM poems p JOIN poets t ON t.id = p.poet_id "
            "WHERE p.in_public_library = 1 AND t.period IS NOT NULL "
            "AND TRIM(t.period) <> '' "
            "GROUP BY t.period ORDER BY n DESC, t.period ASC"
        ).all()
        out["periode"] = [{"label": r["label"], "count": r["n"]} for r in rows]
        out["periode_unmapped"] = total - sum(r["n"] for r in rows)
    return out


# ---------------------------------------------------------------- penulisan label


def set_labels(cur, poem_id, label_type, items, source):
    """Ganti SEMUA label (dari sumber mana pun) untuk satu puisi dan jenis.

    items: daftar (label, is_primary, score). Dipanggil oleh impor label manual dan prediksi model.
    """
    cur.execute("DELETE FROM poem_labels WHERE poem_id = %s AND label_type = %s", (poem_id, label_type))
    for label, is_primary, score in items:
        cur.execute(
            "INSERT INTO poem_labels (poem_id, label_type, label, is_primary, score, source) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (poem_id, label_type, label, 1 if is_primary else 0, score, source),
        )
