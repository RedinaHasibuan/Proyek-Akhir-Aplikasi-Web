
"""Query perpustakaan puisi (hanya baca) dan penulisan label tema.

Aturan:
- Hanya puisi dengan in_public_library = 1 yang dapat dibaca melalui API.
- Puisi ID Puisi (0) dan draf pengguna tidak dapat diambil melalui API.
- Klasifikasi utama yang digunakan adalah tema puisi.
- Label emosi lama tetap tersimpan di database sebagai arsip.
"""

from labels import TEMA_LIST


SORTS = {
    "title": "p.title ASC, p.id ASC",
    "poet": "t.name ASC, p.title ASC, p.id ASC",
    "words": "p.n_words DESC, p.id ASC",
    "newest": "p.id DESC",
}


def like_pattern(term):
    """Pola LIKE aman untuk karakter khusus dari pengguna."""
    esc = term.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{esc}%"


def excerpt(body, max_lines=4, max_chars=220):
    lines = [
        ln.strip()
        for ln in body.split("\n")
        if ln.strip() and set(ln.strip()) != {"."}
    ]

    text = "\n".join(lines[:max_lines])

    if len(text) > max_chars or len(lines) > max_lines:
        text = text[:max_chars].rstrip() + "…"

    return text


def _score(value):
    """MySQL mengembalikan Decimal; JSON membutuhkan float."""
    return None if value is None else float(value)


def _labels_for(cur, poem_ids):
    """Mengambil label tema untuk daftar puisi."""
    out = {pid: {"tema": None} for pid in poem_ids}

    if not poem_ids:
        return out

    marks = ",".join(["%s"] * len(poem_ids))

    rows = cur.execute(
        "SELECT poem_id, label, score, source "
        "FROM poem_labels "
        f"WHERE poem_id IN ({marks}) "
        "AND label_type = 'tema'",
        poem_ids,
    ).all()

    for row in rows:
        out[row["poem_id"]]["tema"] = {
            "label": row["label"],
            "source": row["source"],
            "score": _score(row["score"]),
        }

    return out


def _poem_row(row, labels, with_body):
    item = {
        "id": row["id"],
        "title": row["title"],
        "poet": (
            {"id": row["poet_id"], "name": row["poet_name"]}
            if row["poet_id"]
            else None
        ),
        "n_lines": row["n_lines"],
        "n_words": row["n_words"],
        "tema": labels["tema"],
    }

    if with_body:
        item.update(
            body=row["body"],
            n_stanzas=row["n_stanzas"],
            source_url=row["source_url"],
            license=row["license"],
        )
    else:
        item["excerpt"] = excerpt(row["body"])

    return item


def list_poems(
    db,
    *,
    q=None,
    poet_id=None,
    tema=None,
    sort="title",
    page=1,
    per_page=12,
):
    """Daftar puisi publik dengan filter tema dan pagination."""

    if tema is not None and tema not in TEMA_LIST:
        raise ValueError("tema tidak valid")

    order = SORTS[sort]

    where = ["p.in_public_library = 1"]
    params = []

    if q:
        pattern = like_pattern(q)

        where.append(
            "(p.title LIKE %s ESCAPE '!' "
            "OR t.name LIKE %s ESCAPE '!' "
            "OR p.body LIKE %s ESCAPE '!')"
        )

        params += [pattern, pattern, pattern]

    if poet_id is not None:
        where.append("p.poet_id = %s")
        params.append(poet_id)

    if tema:
        where.append(
            "EXISTS ("
            "SELECT 1 FROM poem_labels l "
            "WHERE l.poem_id = p.id "
            "AND l.label_type = 'tema' "
            "AND l.label = %s"
            ")"
        )
        params.append(tema)

    base = (
        "FROM poems p "
        "LEFT JOIN poets t ON t.id = p.poet_id "
        "WHERE " + " AND ".join(where)
    )

    with db.cursor() as cur:
        total = cur.execute(
            f"SELECT COUNT(*) AS n {base}",
            params,
        ).one()["n"]

        rows = cur.execute(
            "SELECT p.id, p.title, p.body, p.n_lines, p.n_words, "
            "p.n_stanzas, p.source_url, p.license, "
            "t.id AS poet_id, t.name AS poet_name "
            f"{base} "
            f"ORDER BY {order} LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page],
        ).all()

        labels = _labels_for(
            cur,
            [row["id"] for row in rows],
        )

    return {
        "items": [
            _poem_row(row, labels[row["id"]], with_body=False)
            for row in rows
        ],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    }


def get_poem(db, poem_id):
    """Mengambil satu puisi publik lengkap."""

    with db.cursor() as cur:
        row = cur.execute(
            "SELECT p.id, p.title, p.body, p.n_lines, p.n_words, "
            "p.n_stanzas, p.source_url, p.license, "
            "t.id AS poet_id, t.name AS poet_name "
            "FROM poems p "
            "LEFT JOIN poets t ON t.id = p.poet_id "
            "WHERE p.id = %s AND p.in_public_library = 1",
            (poem_id,),
        ).one()

        if not row:
            return None

        labels = _labels_for(cur, [poem_id])[poem_id]

    return _poem_row(row, labels, with_body=True)


def list_poets(db, q=None, limit=50):
    """Daftar penyair yang memiliki puisi publik."""

    where = ["p.in_public_library = 1"]
    params = []

    if q:
        where.append("t.name LIKE %s ESCAPE '!'")
        params.append(like_pattern(q))

    with db.cursor() as cur:
        rows = cur.execute(
            "SELECT t.id, t.name, COUNT(*) AS n "
            "FROM poets t "
            "JOIN poems p ON p.poet_id = t.id "
            f"WHERE {' AND '.join(where)} "
            "GROUP BY t.id, t.name "
            "ORDER BY n DESC, t.name ASC "
            "LIMIT %s",
            params + [limit],
        ).all()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "poem_count": row["n"],
        }
        for row in rows
    ]


def filter_counts(db):
    """Jumlah puisi publik berdasarkan tema."""

    out = {}

    with db.cursor() as cur:
        total = cur.execute(
            "SELECT COUNT(*) AS n "
            "FROM poems "
            "WHERE in_public_library = 1"
        ).one()["n"]

        out["total_public"] = total

        rows = cur.execute(
            "SELECT l.label, COUNT(DISTINCT l.poem_id) AS n "
            "FROM poem_labels l "
            "JOIN poems p ON p.id = l.poem_id "
            "WHERE p.in_public_library = 1 "
            "AND l.label_type = 'tema' "
            "GROUP BY l.label"
        ).all()

        counts = {
            row["label"]: row["n"]
            for row in rows
        }

        out["tema"] = [
            {
                "label": label,
                "count": counts.get(label, 0),
            }
            for label in TEMA_LIST
        ]

        labeled = cur.execute(
            "SELECT COUNT(DISTINCT l.poem_id) AS n "
            "FROM poem_labels l "
            "JOIN poems p ON p.id = l.poem_id "
            "WHERE p.in_public_library = 1 "
            "AND l.label_type = 'tema'"
        ).one()["n"]

        out["tema_unlabeled"] = total - labeled

    return out


# ---------------------------------------------------------
# PENULISAN LABEL
# ---------------------------------------------------------

def set_labels(cur, poem_id, label_type, items, source):
    """Mengganti semua label untuk satu puisi dan jenis label.

    items: daftar (label, is_primary, score).

    Fungsi tetap generik agar kompatibel dengan arsip label lama.
    """

    cur.execute(
        "DELETE FROM poem_labels "
        "WHERE poem_id = %s AND label_type = %s",
        (poem_id, label_type),
    )

    for label, is_primary, score in items:
        cur.execute(
            "INSERT INTO poem_labels "
            "(poem_id, label_type, label, is_primary, score, source) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                poem_id,
                label_type,
                label,
                1 if is_primary else 0,
                score,
                source,
            ),
        )
