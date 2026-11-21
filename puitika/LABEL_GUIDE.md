# Panduan Label Puitika (arah terbaru)

## Target model utama: TEMA (5 kelas)

| Label | Pokok puisi |
|---|---|
| romansa | cinta, asmara, kekasih/pasangan, patah hati |
| alam | alam sebagai pokok (laut, hujan, gunung, musim), bukan sekadar latar |
| sosial | masyarakat, politik, kemiskinan, perjuangan, kebangsaan, kritik |
| kehidupan | renungan hidup, keseharian, keluarga, waktu, makna, pertanyaan filosofis |
| religius | Tuhan, doa, iman, dosa, akhirat |

Model produksi Puitika hanya dilatih untuk memprediksi tema. Satu puisi mendapat satu tema utama. Bila dua tema benar-benar seimbang atau teks tidak layak dinilai, tandai `perlu_tinjau` atau `skip`; jangan memaksakan label.

## Label emosi lama: arsip eksperimen, bukan target model utama

Kolom `emosi_utama`, `emosi_lain`, `emosi_utama_ai`, dan `emosi_lain_ai` pada lembar label lama tetap dipertahankan agar hasil kerja sebelumnya tidak hilang. Hasil eksperimen model emosi juga boleh disimpan untuk dokumentasi, tetapi tidak digunakan sebagai prediksi utama aplikasi.

Sentiment analysis merupakan tugas berbeda: modul `sentiment_analysis.py` mengembalikan polaritas `positif`, `negatif`, `netral`, atau `campuran` melalui kamus kata (lexicon-based). Polaritas ini bukan label emosi seperti sedih/rindu/bahagia dan tidak boleh disamakan.

## Aturan tema

1. **Alam sebagai metafora.** Hujan/senja yang dipakai untuk menggambarkan kekasih atau kenangan → tema **romansa**, bukan alam. Tema alam hanya bila alam menjadi pokok puisi.
2. **Romansa vs kehidupan.** Relasi asmara/kekasih → romansa; keluarga, keseharian, waktu, atau renungan hidup → kehidupan.
3. **Kritik sosial.** Masyarakat, politik, perjuangan, kemiskinan, kebangsaan → sosial.
4. **Doa/Tuhan/iman/akhirat.** Bila gagasan utamanya hubungan manusia dengan Tuhan atau ajaran agama → religius.
5. **Dua tema bersaing.** Pilih yang dominan di sebagian besar bait. Bila tidak dapat dipastikan, tandai `perlu_tinjau`.

## Kasus yang dilewati

Gunakan `skip` untuk halaman bukan puisi, teks rusak/tidak lengkap, bahasa yang tidak dapat dinilai, atau teks yang tidak cocok dengan kategori. Jangan memaksa label.

## Saran AI dan konfirmasi

`tema_ai` hanya saran awal. Baca isi puisi sebelum menerima atau mengubahnya. Kolom `label_oleh` membedakan `manusia_konfirmasi_ai` dan `manusia`. Laporkan secara transparan bahwa sebagian label awal dibantu AI lalu dikonfirmasi manual.

Untuk anotasi tambahan tema saja, gunakan:

```powershell
python label_cli.py --theme-only
```

Mode ini tidak meminta label emosi dan mempertahankan nilai emosi lama pada CSV.
