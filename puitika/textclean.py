"""Fungsi pembersih teks untuk Puitika.

Dipakai oleh build_dataset.py. Sengaja hanya memakai library standar Python.
Struktur baris dan bait dipertahankan (bait dipisah satu baris kosong) karena
fitur Makna Puisi nanti membutuhkan pemisahan per bait.
"""
import hashlib
import html
import re
import unicodedata

# ---------------------------------------------------------------- umum

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


def normalize_text(s: str) -> str:
    """Rapikan spasi dan baris, pertahankan pemisah bait (satu baris kosong)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.translate(_ZERO_WIDTH)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace(" ", " ").replace("\t", " ")
    lines = []
    for line in s.split("\n"):
        line = re.sub(r" {2,}", " ", line).strip()
        lines.append(line)
    s = "\n".join(lines)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def body_hash(body: str) -> str:
    """Hash untuk mendeteksi puisi duplikat (abaikan huruf besar/kecil dan spasi)."""
    key = re.sub(r"\s+", "", body.casefold())
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def text_stats(body: str):
    """Kembalikan (jumlah_baris, jumlah_bait, jumlah_kata)."""
    lines = [ln for ln in body.split("\n") if ln.strip()]
    stanzas = [b for b in re.split(r"\n\s*\n", body) if b.strip()]
    words = len(re.findall(r"\w+", body, flags=re.UNICODE))
    return len(lines), len(stanzas), words


def is_probably_poem(body: str, min_lines=2, min_words=8, max_words=1500):
    """Saring halaman yang jelas bukan puisi. Kembalikan (ok, alasan)."""
    n_lines, _, n_words = text_stats(body)
    if n_lines < min_lines:
        return False, "terlalu_sedikit_baris"
    if n_words < min_words:
        return False, "terlalu_pendek"
    if n_words > max_words:
        return False, "terlalu_panjang"
    return True, ""


def clean_author(name):
    """'Oleh Mangku Langit Jingga' -> 'Mangku Langit Jingga'. None bila tidak masuk akal."""
    if not name:
        return None
    name = normalize_text(name).replace("\n", " ")
    name = re.sub(r"^(?:pengarang|author|penulis|karya|oleh|by)\b\s*[:\-]?\s*", "", name, flags=re.I)
    name = name.strip(" \t:-–—,.;\"'")
    if not name or len(name) > 80:
        return None
    return name


def author_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.casefold()).strip()


def display_title(title: str) -> str:
    """'Buah Rindu (puisi)' -> 'Buah Rindu'."""
    t = re.sub(r"\s*\((?:puisi|sajak)\)\s*$", "", title or "", flags=re.I)
    return normalize_text(t).replace("\n", " ")[:200]


# ---------------------------------------------------------------- Wikisumber

_RE_REDIRECT = re.compile(r"^\s*#\s*(?:alih|alihkan|redirect)\b", re.I)
_RE_COMMENT = re.compile(r"<!--.*?-->", re.S)
_RE_REF = re.compile(r"<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref>", re.S | re.I)
_RE_CATEGORY = re.compile(r"\[\[\s*(?:Kategori|Category)\s*:[^\]]*\]\]", re.I)
_RE_FILE = re.compile(r"\[\[\s*(?:Berkas|Gambar|File|Image)\s*:[^\]]*\]\]", re.I)
_RE_TEMPLATE_INNER = re.compile(r"\{\{[^{}]*\}\}")
_RE_TABLE = re.compile(r"\{\|.*?\|\}", re.S)
_RE_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_RE_EXTLINK = re.compile(r"\[(?:https?:)?//[^\s\]]+\s*([^\]]*)\]")
_RE_QUOTES = re.compile(r"'{2,5}")
_RE_BR = re.compile(r"<br\s*/?>", re.I)
_RE_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_RE_HEADING = re.compile(r"^\s*=+\s*(.*?)\s*=+\s*$", re.M)
_RE_MAGIC = re.compile(r"__[A-Z]+__")
_RE_POEM = re.compile(r"<poem\b[^>]*>(.*?)</poem>", re.S | re.I)
_RE_HRULE = re.compile(r"^-{4,}\s*$", re.M)
_RE_LICENSE = re.compile(r"\{\{\s*((?:DP|PD)[-\w]*)", re.I)
_RE_AUTHOR_PARAM = re.compile(
    r"\|\s*(?:author|pengarang|penulis|pencipta)\s*=\s*((?:\[\[[^\]]*\]\]|[^\n|{}\[\]])+)",
    re.I,
)
_RE_AUTHOR_LINK = re.compile(r"\[\[\s*(?:Pengarang|Author)\s*:\s*([^\]|]+)", re.I)


def _strip_templates(text: str) -> str:
    """Hapus {{...}} dari yang paling dalam ke luar (templat bersarang)."""
    for _ in range(25):
        new = _RE_TEMPLATE_INNER.sub("", text)
        if new == text:
            break
        text = new
    return text


def _clean_markup(text: str) -> str:
    text = _RE_TABLE.sub("", text)
    text = _strip_templates(text)
    text = _RE_CATEGORY.sub("", text)
    text = _RE_FILE.sub("", text)
    text = _RE_LINK.sub(r"\1", text)
    text = _RE_EXTLINK.sub(r"\1", text)
    text = _RE_QUOTES.sub("", text)
    text = _RE_BR.sub("\n", text)
    text = _RE_TAG.sub("", text)
    text = _RE_HEADING.sub(r"\1", text)
    text = _RE_MAGIC.sub("", text)
    text = _RE_HRULE.sub("", text)
    text = html.unescape(text)
    # indentasi wikitext (":" di awal baris) tidak bermakna untuk analisis
    text = re.sub(r"^[:;]+\s*", "", text, flags=re.M)
    return text


def parse_wikitext(wikitext: str) -> dict:
    """Ambil isi puisi, penyair, dan tag lisensi dari wikitext satu halaman.

    Mengembalikan dict: is_redirect, body, author, license.
    Parser ini defensif karena format halaman Wikisumber bisa bervariasi;
    gunakan `build_dataset.py --inspect N` untuk memeriksa hasilnya.
    """
    wikitext = wikitext or ""
    if _RE_REDIRECT.match(wikitext):
        return {"is_redirect": True, "body": "", "author": None, "license": None}

    licenses = []
    for m in _RE_LICENSE.finditer(wikitext):
        tag = m.group(1)
        if tag not in licenses:
            licenses.append(tag)

    author = None
    m = _RE_AUTHOR_PARAM.search(wikitext)
    if m:
        value = _RE_LINK.sub(r"\1", m.group(1))
        value = re.sub(r"^(?:pengarang|author)\s*:\s*", "", value.strip(), flags=re.I)
        author = clean_author(value)
    if not author:
        m = _RE_AUTHOR_LINK.search(wikitext)
        if m:
            author = clean_author(m.group(1))

    text = _RE_COMMENT.sub("", wikitext)
    text = _RE_REF.sub("", text)

    poems = _RE_POEM.findall(text)
    raw_body = "\n\n".join(poems) if poems else text

    body = normalize_text(_clean_markup(raw_body))
    return {
        "is_redirect": False,
        "body": body,
        "author": author,
        "license": ", ".join(licenses) if licenses else None,
    }


# ---------------------------------------------------------------- ID Puisi


def clean_idpuisi_row(puisi: str, title: str, author: str, puisi_with_header: str) -> dict:
    """Bersihkan satu baris dataset ID Puisi.

    Judul dan penulis di dataset asli diekstrak dengan regex yang tidak
    sempurna, jadi di sini dirapikan dan ada cadangan dari teks mentah.
    """
    raw_lines = [ln.strip() for ln in (puisi_with_header or "").splitlines() if ln.strip()]

    title = normalize_text(title or "").replace("\n", " ")
    if not title or len(title) > 120:
        title = raw_lines[0][:120] if raw_lines else ""

    author = clean_author(author)
    if not author and len(raw_lines) > 1 and re.match(r"^oleh\b", raw_lines[1], re.I):
        author = clean_author(raw_lines[1])

    body = normalize_text(puisi or "")
    if not body and raw_lines:
        body = normalize_text("\n".join((puisi_with_header or "").splitlines()[2:]))

    return {"title": title.strip(), "author": author, "body": body}
