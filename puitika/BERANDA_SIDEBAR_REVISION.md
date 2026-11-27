# Revisi Beranda dan Sidebar Puitika

## Keputusan UI
- Kartu/quote “Catatan Puitika” dipindahkan dari sidebar ke Beranda sebagai catatan editorial kecil setelah lima kartu pintasan fitur.
- Status “Server tersambung”, jumlah kata kamus, dan status model tidak lagi ditampilkan kepada pengunjung biasa. Informasi diagnostik tetap tersedia melalui `GET /api/health`.
- Sidebar dipertahankan gelap, tetapi hanya berisi identitas Puitika dan enam tautan navigasi. Ini mengurangi tinggi panel dan menghilangkan scrollbar internal yang tidak perlu.
- Kalimat intro sidebar dipersingkat agar tidak menduplikasi headline Beranda.
- Hero Beranda, ilustrasi buku, jarak pencarian, dan tinggi kartu fitur dipadatkan. Lima kartu fitur tetap tersedia.
- Hijau muda `#E3EAD9` dan sage mist `#EEF2E9` tetap menjadi warna pendamping yang terlihat pada hero, kartu, ikon, dan Catatan Puitika.

## File yang berubah
- `frontend/index.html`
- `frontend/css/style.css`
- `frontend/js/app.js`
- `frontend/js/pages/home.js`
- `test_frontend.py`

## Backend
Tidak ada perubahan pada `app.py`, database, model NLP, atau endpoint. Endpoint health tetap tersedia untuk pemeriksaan teknis, tetapi tidak ditampilkan sebagai elemen UI.
