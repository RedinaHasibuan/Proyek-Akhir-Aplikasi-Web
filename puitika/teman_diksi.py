"""Teman Diksi: chatbot rule-based untuk Ruang Diksi (tanpa model bahasa, tanpa riwayat percakapan).

Alur: normalisasi pesan -> cocokkan aturan (urut dari yang paling spesifik) -> ambil data dari database ->
susun jawaban. Jawaban berupa dict: niat, balasan (teks pendek), kandidat (daftar kata lengkap untuk
ditampilkan sebagai kartu), saran (contoh pesan lanjutan).

Niat: sapaan, bantuan, arti, sinonim, antonim, contoh, emosi, deskripsi, tidak_paham.
"""
import re

import diksi_repo as dr
from labels import EMOSI_LIST

MAX_PESAN = 300
FILLER_END = {"itu", "ya", "dong", "sih", "deh", "nih", "kak", "tolong", "apa", "yaa", "gitu", "gimana"}
EMOSI_RE = "|".join(EMOSI_LIST)

_P = {
    "sapaan": re.compile(r"^(halo|hai|hi|hey|hallo|selamat (pagi|siang|sore|malam)|assalamualaikum|permisi)\b"),
    "bantuan": re.compile(r"\b(bantuan|bantu aku|help|bisa apa|apa yang bisa|cara (pakai|pakainya|menggunakan))\b"),
    "contoh": re.compile(r"^(?:minta |beri(?:kan)? |kasih )?contoh(?: kalimat| penggunaan| pemakaian)?(?: dari| untuk| kata| dengan)*\s+(.+)$"),
    "antonim": re.compile(r"^(?:apa )?(?:lawan kata|antonim|kebalikan|lawan)(?: kata)?(?: dari| untuk)?\s+(?:kata\s+)?(.+)$"),
    "sinonim": re.compile(
        r"^(?:apa )?(?:(?:ada )?kata lain (?:untuk|dari|buat)|sinonim|padanan|persamaan kata|persamaan|pengganti|ganti(?:an)? kata)"
        r"(?: kata)?(?: dari| untuk| buat)?\s+(?:kata\s+)?(.+)$"
    ),
    "arti_a": re.compile(r"^(?:apa\s+)?(?:arti|makna|maksud|pengertian|definisi)(?:nya)?(?: dari| kata| dari kata)*\s+(.+)$"),
    "arti_b": re.compile(r"^(?:apa itu|apa sih|apa)\s+(.+)$"),
    "arti_c": re.compile(r"^(.+?)\s+(?:itu\s+)?(?:artinya|berarti|maksudnya|maknanya)(?:\s+apa)?$"),
    "emosi": re.compile(rf"^(?:(?:ada |minta |beri(?:kan)? )?(?:diksi|kata-kata|kata|kosakata))\s+(?:untuk\s+)?(?:suasana\s+|rasa\s+|perasaan\s+|nuansa\s+)?({EMOSI_RE})$"),
}

SARAN_AWAL = [
    "arti lara",
    "kata lain untuk sedih",
    "lawan kata gelisah",
    "contoh kalimat renjana",
    "diksi rindu",
    "kata yang menggambarkan perasaan suka dan tidak suka sekaligus",
]


def normalisasi(pesan):
    t = (pesan or "").casefold().strip()
    t = re.sub(r"[\"'“”‘’`]", "", t)
    t = re.sub(r"[?!.,;:]+", " ", t)
    return " ".join(t.split())


def _bersih_kata(s):
    toks = s.split()
    while toks and toks[-1] in FILLER_END:
        toks.pop()
    if toks and toks[0] == "kata":
        toks = toks[1:]
    return " ".join(toks)


def _jawab(niat, balasan, kandidat=None, saran=None):
    return {"niat": niat, "balasan": balasan, "kandidat": kandidat or [], "saran": saran or []}


def _tidak_ketemu(db, kata):
    mirip = dr.similar_words(db, kata)
    if mirip:
        return _jawab(
            "tidak_paham",
            f"Aku belum punya kata '{kata}' di kamus Puitika. Maksudmu: {', '.join(mirip)}?",
            saran=[f"arti {m}" for m in mirip],
        )
    return _jawab(
        "tidak_paham",
        f"Aku belum punya kata '{kata}' di kamus Puitika. Kamus ini masih kecil dan dikurasi satu per satu. "
        "Coba deskripsikan maknanya, misalnya: \"kata yang menggambarkan ...\".",
        saran=SARAN_AWAL[:3],
    )


def _kartu(entry):
    e = dict(entry)
    e.pop("relasi", None)
    return e


def respond(db, pesan):
    """Jawab satu pesan. Panggil hanya setelah tabel diksi ada."""
    t = normalisasi(pesan)
    if not t:
        return _jawab("bantuan", "Tulis sesuatu dulu ya.", saran=SARAN_AWAL)

    if _P["sapaan"].match(t) and len(t.split()) <= 4:
        return _jawab(
            "sapaan",
            "Halo! Aku Teman Diksi. Aku bisa membantu mencari arti kata, kata lain, lawan kata, contoh kalimat, "
            "atau kata dari deskripsi yang kamu bayangkan.",
            saran=SARAN_AWAL,
        )

    m = _P["emosi"].match(t)
    if m:
        emosi = m.group(1)
        kand = dr.entries_by_emosi(db, emosi, limit=8)
        if not kand:
            return _jawab("emosi", f"Belum ada kata bernuansa {emosi} di kamus.", saran=SARAN_AWAL[:3])
        return _jawab(
            "emosi",
            f"Beberapa kata yang bernuansa {emosi}. Pilih yang paling cocok dengan konteks puisimu; nuansanya bisa berbeda tipis.",
            [_kartu(e) for e in kand],
        )

    for niat in ("contoh", "antonim", "sinonim"):
        m = _P[niat].match(t)
        if m:
            kata = _bersih_kata(m.group(1))
            e = dr.get_entry(db, kata)
            if e is None:
                return _tidak_ketemu(db, kata)
            if niat == "contoh":
                if not e["contoh"]:
                    return _jawab("contoh", f"Belum ada contoh kalimat untuk '{e['kata']}'.", [_kartu(e)])
                return _jawab("contoh", f"Contoh penggunaan '{e['kata']}':", [_kartu(e)], [f"arti {e['kata']}"])
            rel = e["relasi"]["sinonim" if niat == "sinonim" else "antonim"]
            label = "kata lain" if niat == "sinonim" else "lawan kata"
            if not rel:
                lain = e["relasi"]["terkait"]
                if lain:
                    kand = [dr.get_entry(db, r["kata"], with_relations=False) for r in lain]
                    return _jawab(
                        niat,
                        f"Belum ada {label} yang tercatat untuk '{e['kata']}', tetapi ada kata yang berkaitan.",
                        [_kartu(k) for k in kand if k],
                    )
                return _jawab(niat, f"Belum ada {label} yang tercatat untuk '{e['kata']}'.", [_kartu(e)])
            kand = [dr.get_entry(db, r["kata"], with_relations=False) for r in rel]
            tambahan = (
                " Kata-kata ini jarang tepat sama; baca nuansanya sebelum memilih."
                if niat == "sinonim"
                else ""
            )
            return _jawab(niat, f"{label.capitalize()} untuk '{e['kata']}':{tambahan}", [_kartu(k) for k in kand if k])

    for key in ("arti_a", "arti_c", "arti_b"):
        m = _P[key].match(t)
        if m:
            kata = _bersih_kata(m.group(1))
            # "apa X" yang panjang bukan pertanyaan arti kata; biarkan jatuh ke pencarian deskripsi
            if key == "arti_b" and (len(kata.split()) > 2 or dr.get_entry(db, kata) is None):
                continue
            e = dr.get_entry(db, kata)
            if e is None:
                return _tidak_ketemu(db, kata)
            return _jawab("arti", f"Ini yang kutemukan tentang '{e['kata']}'.", [_kartu(e)], _saran_kata(e))

    # satu kata/frasa pendek yang persis ada di kamus -> anggap bertanya arti
    if len(t.split()) <= 3:
        e = dr.get_entry(db, t)
        if e is not None:
            return _jawab("arti", f"Ini yang kutemukan tentang '{e['kata']}'.", [_kartu(e)], _saran_kata(e))

    if _P["bantuan"].search(t):
        return _jawab(
            "bantuan",
            "Coba salah satu: tanya arti kata, minta kata lain atau lawan kata, minta contoh kalimat, minta diksi "
            "untuk suatu emosi (sedih, rindu, bahagia, harapan, tenang, marah), atau deskripsikan makna yang kamu cari.",
            saran=SARAN_AWAL,
        )

    if len(t.split()) <= 2:  # kata tunggal yang tidak ada: mungkin salah ketik
        mirip = dr.similar_words(db, t)
        if mirip:
            return _tidak_ketemu(db, t)

    # fallback: anggap deskripsi makna
    hasil = dr.search_description(db, t, top_k=4)
    if hasil:
        return _jawab(
            "deskripsi",
            "Dari deskripsimu, ada beberapa kata yang bisa kamu pertimbangkan. Pilih sesuai konteks puisimu; "
            "pencocokan ini berdasarkan kemiripan kata, jadi belum tentu paling tepat.",
            hasil,
        )
    return _jawab(
        "tidak_paham",
        "Aku belum menemukan kata yang cocok. Coba deskripsikan dengan kata lain, atau tanya arti sebuah kata.",
        saran=SARAN_AWAL,
    )


def _saran_kata(e):
    s = [f"kata lain untuk {e['kata']}"] if e["relasi"]["sinonim"] else []
    if e["relasi"]["antonim"]:
        s.append(f"lawan kata {e['kata']}")
    s.append(f"contoh kalimat {e['kata']}")
    return s
