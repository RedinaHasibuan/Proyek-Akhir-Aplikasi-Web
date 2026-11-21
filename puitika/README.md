# Puitika — Data, NLP, dan Machine Learning

Puitika adalah platform eksplorasi diksi, penulisan, dan analisis puisi Indonesia.
Backend aplikasi direncanakan menggunakan Flask, database MySQL/MariaDB, dan frontend HTML/CSS/JavaScript.

## Arah sistem terbaru

1. **Klasifikasi otomatis utama: tema puisi** (romansa, alam, sosial, kehidupan, religius).
2. **Sentiment analysis: bagian dari Makna Puisi**, dimulai dengan pendekatan lexicon-based dan dapat dibandingkan dengan supervised learning di tahap lanjutan jika tersedia data polaritas berlabel.
3. **Klasifikasi enam emosi bukan model produksi utama.** Kolom/label emosi dari eksperimen sebelumnya tetap dipertahankan sebagai arsip, bukan dihapus.
4. **Clustering** menjadi eksplorasi tambahan di Dashboard Sastra, bukan pengganti klasifikasi tema.

## Tahap data yang telah dikerjakan

```text
crawl_wikisumber.py  -> data/raw/wikisumber.jsonl
build_dataset.py     -> data/clean/poems.csv
load_to_db.py        -> MySQL: poets, poems, poem_labels
```

Korpus lokal saat ini berisi 341 puisi hasil pembersihan dari 373 halaman yang ditemukan crawler. Data lokal tidak otomatis ikut Git karena folder `data/` diabaikan oleh `.gitignore`.

## Persiapan lingkungan

Dari folder `puitika`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Preprocessing dan eksplorasi

```powershell
python smoke_test.py
python explore_data.py
```

## Pelabelan tema

Lembar label lama dapat tetap menyimpan kolom emosi untuk arsip anotasi. Model aktif hanya menggunakan kolom `tema`.

Untuk anotasi tambahan tema saja:

```powershell
python label_cli.py --theme-only
```

Baca `LABEL_GUIDE.md` sebelum memberi label. Label tema: `romansa`, `alam`, `sosial`, `kehidupan`, `religius`.

## Training dan evaluasi model tema

```powershell
python train_model.py
```

Model utama dan laporan:

```text
models/tema.joblib
reports/eval_tema.txt
reports/confusion_tema.csv
reports/summary.json
```

Skrip ini tidak lagi melatih model emosi. Jika file `models/emosi.joblib` atau `reports/eval_emosi.txt` dari eksperimen terdahulu masih ada, file tersebut dibiarkan sebagai arsip dan tidak digunakan oleh prediksi aplikasi.

## Uji prediksi tema

```powershell
python predict.py --text "Hujan turun pelan, aku menunggumu di beranda"
```

Fungsi untuk integrasi Flask:

```python
from predict import suggest
hasil = suggest(teks_puisi)
# hasil hanya memuat kandidat tema dan indikator ketidakpastian
```

## Sentiment analysis untuk Makna Puisi

Versi awal menggunakan lexicon-based sentiment analysis:

```powershell
python sentiment_analysis.py --text "Aku bersyukur melihat cahaya pagi"
python sentiment_analysis.py --file puisi.txt
python test_sentiment_analysis.py
```

Fungsi untuk integrasi Flask:

```python
from sentiment_analysis import analyze_sentiment
hasil = analyze_sentiment(teks_puisi)
```

Keluaran polaritas: `positif`, `negatif`, `netral`, `campuran`, atau `tidak_terdeteksi`.

- `score` berada di rentang -1 sampai 1 dan merupakan skor polaritas ternormalisasi, **bukan probabilitas**.
- `tidak_terdeteksi` berarti kamus belum menemukan kata bermuatan sentimen; jangan disamakan dengan netral.
- Hasil per bait disediakan sebagai petunjuk, bukan tafsir sastra yang pasti.
- Kamus dalam `sentiment_analysis.py` adalah kamus awal yang perlu ditinjau dan diuji pada puisi Indonesia. Lexicon-based rentan terhadap metafora, ironi, polisemi, dan konteks.

## Database: migrasi aman

Database lokal `puitika` yang telah ada tidak perlu dibuat ulang. Jalankan isi `migration_sentiment_analysis.sql` sekali melalui phpMyAdmin (pilih database `puitika`, buka tab SQL, tempel isi file, lalu Go). Migrasi ini hanya membuat tabel baru `poem_sentiment_analyses`; tidak menghapus atau mengubah tabel/label lama.

Tabel `poem_labels` dipertahankan untuk label tema dan arsip anotasi emosi terdahulu. Aplikasi produksi hanya menulis label tema ke tabel tersebut. Hasil polaritas sentiment disimpan pada `poem_sentiment_analyses`, bukan sebagai label emosi.

Jangan menyimpan teks puisi pribadi secara otomatis. Jika analisis disimpan, simpan hasilnya hanya dengan persetujuan pengguna dan kaitkan `poem_id` hanya bila teks merupakan puisi yang memang tersimpan di database.

## Tahap lanjutan: supervised sentiment

Supervised sentiment bukan bagian dari model yang saat ini sudah selesai. Jika kelak dikembangkan, siapkan dataset puisi yang dianotasi secara terpisah dengan polaritas (`positif`, `negatif`, `netral`, `campuran`), lalu pisahkan data latih/uji dan bandingkan hasilnya dengan lexicon baseline. Jangan mengubah label enam emosi lama menjadi polaritas secara otomatis karena kedua skema label tidak ekuivalen.

## Catatan metodologi

- Laporkan secara transparan bahwa label tema dibantu saran AI lalu dikonfirmasi pengguna jika memang demikian.
- Macro-F1 dan confusion matrix dipakai untuk melihat performa per kelas; accuracy saja tidak cukup untuk korpus yang tidak seimbang.
- Sampel 250 puisi dipilih dengan kuota kata kunci, sehingga distribusinya bukan estimasi sebaran tema seluruh korpus 341 puisi.
- Klasifikasi tema memberi saran, bukan kebenaran mutlak. Tampilkan peringatan jika skor tertinggi rendah.
- Status hak cipta/lisensi karya harus diverifikasi per karya sebelum puisi ditampilkan secara publik.
