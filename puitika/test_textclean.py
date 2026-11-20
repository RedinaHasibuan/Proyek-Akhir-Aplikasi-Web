"""Uji cepat pembersih teks (tanpa jaringan dan tanpa database).

Jalankan: python test_textclean.py
Contoh puisi di bawah adalah teks buatan untuk pengujian, bukan data sungguhan.
"""
import textclean as tc

# --- 1. Halaman Wikisumber dengan <poem>, header, lisensi, kategori
WIKI_POEM = """{{header
 | title = Contoh Puisi
 | author = [[Pengarang:Nama Penyair|Nama Penyair]]
 | year = 1943
}}
<!-- komentar -->
<poem>
Di ujung senja yang '''sunyi'''
: angin membawa [[kabar|berita]] lama<ref>catatan kaki</ref>

Kita pulang tanpa suara&nbsp;lagi
</poem>
{{DP-ID-lama|1949}}
[[Kategori:Puisi]]
"""
r = tc.parse_wikitext(WIKI_POEM)
assert not r["is_redirect"]
assert r["author"] == "Nama Penyair", r["author"]
assert r["license"] == "DP-ID-lama", r["license"]
assert r["body"] == (
    "Di ujung senja yang sunyi\nangin membawa berita lama\n\nKita pulang tanpa suara lagi"
), repr(r["body"])

# --- 2. Tanpa <poem>, templat bersarang, tabel, tautan luar
WIKI_PLAIN = """{{header|title=Lain|author=[[Pengarang:Si Anu]]|notes={{small|catatan}}}}
Baris pertama ''miring''
Baris kedua [https://contoh.org tautan]

== Bait Dua ==
Baris ketiga
[[Berkas:gambar.jpg|thumb|keterangan]]
[[Kategori:Puisi]]"""
r = tc.parse_wikitext(WIKI_PLAIN)
assert r["author"] == "Si Anu", r["author"]
assert "Baris pertama miring" in r["body"]
assert "Baris kedua tautan" in r["body"]
assert "Bait Dua" in r["body"] and "gambar" not in r["body"] and "Kategori" not in r["body"]
assert "{{" not in r["body"] and "}}" not in r["body"]

# --- 3. Redirect
assert tc.parse_wikitext("#ALIH [[Doa]]")["is_redirect"]

# --- 4. Judul
assert tc.display_title("Buah Rindu (puisi)") == "Buah Rindu"

# --- 5. ID Puisi
row = tc.clean_idpuisi_row(
    puisi="Mungkin kau datang  \nmembawa hujan \n \n \n \nLalu kita pergi",
    title="JUDUL CONTOH",
    author="Oleh Penulis Contoh ",
    puisi_with_header="JUDUL CONTOH\nOleh Penulis Contoh\n\nMungkin kau datang",
)
assert row["author"] == "Penulis Contoh", row
assert row["body"] == "Mungkin kau datang\nmembawa hujan\n\nLalu kita pergi", repr(row["body"])
# judul/penulis gagal diekstrak -> pakai teks mentah
row = tc.clean_idpuisi_row("isi puisi cukup panjang di sini", "", "", "SENJA\nOleh Orang Lain\n\nisi puisi cukup panjang di sini")
assert row["title"] == "SENJA" and row["author"] == "Orang Lain", row

# --- 6. Hash, statistik, penyaring
assert tc.body_hash("Halo  Dunia") == tc.body_hash("halo\ndunia")
assert tc.text_stats("a b\nc d\n\ne f") == (3, 2, 6)
assert tc.is_probably_poem("satu\ndua")[0] is False
assert tc.is_probably_poem("baris satu dua tiga\nbaris empat lima enam")[0] is True
assert tc.clean_author("x" * 200) is None

print("Semua uji lulus.")
