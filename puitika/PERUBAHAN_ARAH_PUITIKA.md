# Catatan perubahan arah Puitika

## Keputusan produk

- Model klasifikasi otomatis aktif hanya untuk **tema puisi**.
- Enam label emosi yang pernah dibuat tetap dipertahankan dalam CSV/laporan lama sebagai arsip eksperimen, tetapi tidak dipakai untuk training atau prediksi utama.
- Sentiment analysis menjadi komponen terpisah dari fitur **Makna Puisi**.
- Metode sentiment analysis tahap awal adalah lexicon-based; supervised sentiment baru dipertimbangkan setelah tersedia korpus puisi dengan anotasi polaritas yang memadai.
- Clustering tetap digunakan untuk eksplorasi data di Dashboard Sastra.

## Pemetaan fitur

| Fitur Puitika | Teknologi/proses |
|---|---|
| Ruang Diksi | Kamus diksi, pencarian, chatbot rule-based; semantic search dapat dikembangkan kemudian |
| Makna Puisi | Preprocessing, ekstraksi diksi/kata kunci, sentiment analysis lexicon-based |
| Klasifikasi Tema | TF-IDF + Logistic Regression; tema sebagai satu label utama |
| Studio Puisi | CRUD puisi; memakai saran tema dari `predict.py` |
| Perpustakaan | Query puisi, penyair, sumber; filter tema |
| Dashboard Sastra | Agregasi Pandas/SQL, distribusi tema, frekuensi kata, clustering |

## Pipeline terbaru

```text
341 puisi bersih
    -> eksplorasi dan preprocessing
    -> lembar label 250 puisi
    -> konfirmasi label tema
    -> split/evaluasi silang bertingkat + baseline
    -> model tema.joblib
    -> saran tema untuk puisi baru

Teks puisi yang dimasukkan ke Makna Puisi
    -> tokenisasi ringan dan pencocokan kamus sentimen
    -> penanganan negasi/intensifier sederhana
    -> polaritas positif/negatif/netral/campuran/tidak_terdeteksi
    -> penjelasan kata bukti dan hasil per bait
```

## Database

- `poem_labels` tidak dihapus atau diubah agar kompatibel dengan data lama. Model aplikasi hanya menggunakan `label_type='tema'`; catatan `label_type='emosi'` lama bersifat arsip.
- `poem_sentiment_analyses` adalah tabel baru untuk menyimpan hasil polaritas sentimen. Kolom `method` mendukung `lexicon` saat ini dan `supervised` untuk kemungkinan pengembangan.
- Untuk database lokal yang sudah ada, gunakan `migration_sentiment_analysis.sql`. Jangan menjalankan ulang `load_to_db.py --init` hanya untuk menambah tabel sentiment.

## File patch

- `train_model.py`: hanya melatih target tema. Sebelum memperbarui `summary.json`, ringkasan model emosi lama diarsipkan ke `summary_emosi_eksperimen_lama.json` bila tersedia. File `emosi.joblib` dan `eval_emosi.txt` tidak dihapus.
- `predict.py`: hanya memuat `tema.joblib` dan mengembalikan kandidat tema.
- `sentiment_analysis.py`: modul lexicon-based untuk Makna Puisi; terpisah dari classifier tema.
- `test_sentiment_analysis.py`: uji dasar polaritas, negasi, dan pembagian bait.
- `label_cli.py`: menambahkan opsi `--theme-only`; kolom emosi lama tidak dihapus saat mode ini digunakan.
- `smoke_test.py`: menguji bahwa pipeline melatih model tema saja dan modul sentiment berjalan.
- `schema.sql`: skema instalasi baru mencakup tabel sentiment.
- `migration_sentiment_analysis.sql`: migrasi non-destruktif untuk database lokal yang sudah ada.

## Keterbatasan lexicon tahap awal

Kamus dalam `sentiment_analysis.py` adalah seed lexicon buatan proyek, bukan kamus sentimen baku yang sudah tervalidasi. Kata dapat bersifat polisemi, metaforis, ironis, atau berubah makna karena konteks. Hasil `tidak_terdeteksi` berarti kamus tidak menemukan kata yang dikenal, bukan teks terbukti netral. Evaluasi manusia dan penambahan kosakata perlu dilakukan sebelum mengklaim kualitas analisis.
