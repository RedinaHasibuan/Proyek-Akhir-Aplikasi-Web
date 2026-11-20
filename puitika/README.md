# Puitika — tahap data (hari 1–2)

Alur: **crawl Wikisumber → bersihkan + gabung dengan ID Puisi → MySQL**

```
crawl_wikisumber.py  ->  data/raw/wikisumber.jsonl   (wikitext mentah)
build_dataset.py     ->  data/clean/poems.csv        (bersih, tanpa duplikat)
load_to_db.py        ->  MySQL: poets, poems, poem_labels
```

## Persiapan (sekali saja)

1. Python 3.10+ dan MySQL jalan (XAMPP/Laragon cukup).
2. `pip install -r requirements.txt`
3. Atur environment variable (contoh Windows PowerShell; Linux/Mac pakai `export`):
   ```
   $env:PUITIKA_CONTACT = "emailkamu@contoh.com"   # wajib diisi untuk User-Agent Wikimedia
   # hanya jika DB-mu bukan root tanpa password:
   $env:PUITIKA_DB_USER = "root"
   $env:PUITIKA_DB_PASSWORD = "passwordmu"
   ```

## Langkah

```
python test_textclean.py                 # uji pembersih, harus "Semua uji lulus"
python crawl_wikisumber.py --limit 5     # uji coba 5 halaman dulu
python build_dataset.py --no-idpuisi --inspect 5
```
Perhatikan 5 contoh yang tercetak: judul, penyair, lisensi, dan isi harus masuk akal.
Kalau penyair `None` semua atau isi masih berantakan, kirim saya satu contoh
wikitext dari `data/raw/wikisumber.jsonl`, parser tinggal disesuaikan (tanpa crawling ulang).

Kalau sudah benar:
```
python crawl_wikisumber.py               # semua halaman Kategori:Puisi (±373 + subkategori)
python build_dataset.py                  # gabung Wikisumber + ID Puisi (otomatis diunduh)
python load_to_db.py --init              # buat DB + tabel lalu muat data
```

Cek di MySQL/phpMyAdmin:
```sql
SELECT source, in_public_library, COUNT(*) FROM poems GROUP BY source, in_public_library;
SELECT title, n_words FROM poems ORDER BY RAND() LIMIT 5;
```

## Catatan

- `in_public_library = 1` hanya Wikisumber. Puisi ID Puisi (0) hanya untuk eksperimen internal
  (preprocessing, frekuensi kata, clustering) dan jangan ditampilkan lengkap ke publik.
- Skrip aman dijalankan ulang: crawler melewati halaman yang sudah ada, loader melewati puisi yang sudah ada.
- Crawler diberi jeda 1 detik per permintaan. Jangan dipercepat.
- Tabel `poem_labels` sudah disiapkan untuk pelabelan manual (hari 3–4).
