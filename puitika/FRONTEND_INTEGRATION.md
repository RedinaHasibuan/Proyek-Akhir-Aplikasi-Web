# Redesign Frontend Puitika — Cozy Literary Archive

Paket ini merombak lapisan tampilan Puitika dengan mengambil inspirasi visual dari referensi LokaSajak yang diberikan: kertas hangat, tekstur halus, serif editorial, isi puisi yang lega, kartu seperti halaman buku, dan aksen musim gugur.

## Yang dipertahankan

- Nama dan identitas aplikasi tetap **Puitika**.
- Router modular JavaScript dan pola DOM aman dari proyek Puitika.
- Endpoint Flask yang telah tersedia: `/api/health`, `/api/filters`, `/api/poems`, `/api/diksi/*`, `/api/makna`, `/api/drafts/*`, `/api/studio/rekomendasi`, dan `/api/dashboard`.
- Tema klasifikasi sesuai backend: `romansa`, `alam`, `sosial`, `kehidupan`, `religius`.
- Fitur yang benar-benar didukung backend: pencarian puisi, filter, detail puisi, mode fokus baca, pencarian diksi, Teman Diksi, editor/draf, analisis makna, dan dashboard.

## Yang diambil dari referensi LokaSajak

- Kertas hangat `#F5F1EA` dan kartu terang.
- Tinta espresso `#42250B`.
- Karamel `#A9682A`, oranye musim gugur `#E48025`, dan sage `#8E957F`.
- Playfair Display, Lora, Plus Jakarta Sans, dan Caveat (Google Fonts, dengan fallback lokal).
- Tekstur kertas, garis halus, bayangan lembut, transisi ringan, bookmark pada kartu, halaman baca terpusat, dan mode fokus.

## Yang sengaja tidak disalin

Referensi LokaSajak menggambarkan komunitas dengan autentikasi, profil, like, dan komentar. Backend Puitika saat ini belum menyediakan API pengguna, autentikasi, like, komentar, atau profil. Karena itu fitur-fitur tersebut tidak ditampilkan sebagai fitur aktif/palsu. Studio tetap menggunakan API draf Puitika yang sudah ada; draf belum memiliki pemisahan pemilik sehingga server tidak boleh diekspos ke publik tanpa autentikasi/otorisasi.

## Struktur paket

```text
frontend/
  index.html
  css/style.css
  js/
    app.js
    ui.js
    charts.js
    pages/
      home.js
      library.js
      diksi.js
      studio.js
      makna.js
      dashboard.js
test_frontend.py
FRONTEND_INTEGRATION.md
FRONTEND_API_MAP.md
APP_CSP_FONT_PATCH.md
```

## Pemasangan

1. Cadangkan folder `frontend/` yang ada.
2. Ekstrak folder `frontend/` dari ZIP ini ke folder proyek `puitika/`, sejajar dengan `app.py`.
3. Jangan menimpa `app.py`, `repo.py`, `db.py`, model, atau database dari paket frontend.
4. Ikuti `APP_CSP_FONT_PATCH.md` agar Google Fonts boleh dimuat oleh Content Security Policy.
5. Dari folder `puitika/`, jalankan:

```powershell
python -m py_compile app.py
python test_frontend.py
python test_backend.py
python test_diksi.py
python test_advanced_api.py
```

6. Jalankan `python app.py`, lalu buka `http://127.0.0.1:5000/`.

## Catatan integrasi

Frontend disajikan oleh Flask pada origin yang sama. CSS dan JavaScript dimuat dari `/app/...`; panggilan API memakai URL relatif `/api/...`. Tidak perlu npm, Vite, Tailwind CDN, atau konfigurasi CORS baru.


## Responsif dan tampilan ringkas
- `frontend/index.html` menambah mobile topbar, tombol menu, dan backdrop drawer.
- `frontend/js/app.js` mengatur buka/tutup drawer (tombol, backdrop, klik navigasi, Escape).
- `frontend/css/style.css` memakai sidebar desktop + drawer pada lebar 900px ke bawah; pada mobile tidak ada sidebar desktop yang memenuhi viewport.
- Beranda hanya berisi hero pencarian, lima pintasan fitur, dan catatan pendek. Tidak ada banner promosi panjang.
- Palet menambahkan hijau muda sage `#E3EAD9` dan sage mist `#EEF2E9` sebagai surface.
- Terapkan CSP Google Fonts dari `APP_CSP_FONT_PATCH.md` bila ingin font web aktif; fallback lokal tetap bekerja tanpa jaringan.

## Revisi Beranda dan sidebar

- Catatan Puitika ditempatkan di Beranda sebagai catatan editorial ringkas, bukan di sidebar.
- Status server tidak ditampilkan di UI biasa; endpoint `GET /api/health` tetap tersedia untuk pemeriksaan teknis.
- Sidebar desktop kini hanya berisi brand, intro singkat, dan navigasi agar tidak memerlukan scrollbar internal pada tinggi layar normal.
- Hero, ilustrasi buku, dan kartu pintasan dipadatkan untuk mengurangi panjang Beranda.
