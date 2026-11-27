# Peta API Frontend Puitika

| Halaman | Endpoint | Pemakaian |
|---|---|---|
| Beranda | `POST /api/diksi/search` | Menemukan kandidat kata dari deskripsi makna |
| Perpustakaan | `GET /api/filters` | Jumlah koleksi, tema, dan periode |
| Perpustakaan | `GET /api/poems` | Pencarian, filter tema/periode, urut, paginasi |
| Detail puisi | `GET /api/poems/<id>` | Isi puisi dan metadata sumber |
| Ruang Diksi | `POST /api/diksi/chat` | Teman Diksi |
| Ruang Diksi | `POST /api/diksi/search` | Pencarian diksi dari deskripsi |
| Ruang Diksi | `GET /api/diksi/words` | Daftar kosakata |
| Ruang Diksi | `GET /api/diksi/words/<kata>` | Detail kata dan relasi |
| Studio | `GET/POST /api/drafts` | Daftar dan pembuatan draf |
| Studio | `GET/PUT/DELETE /api/drafts/<id>` | Buka, simpan perubahan, dan hapus draf |
| Studio | `POST /api/studio/rekomendasi` | Saran tema dan diksi |
| Makna Puisi | `POST /api/makna` | Analisis teks baru |
| Makna Puisi | `GET /api/poems/<id>/makna` | Analisis puisi dari Perpustakaan |
| Dashboard | `GET /api/dashboard?k=` | Statistik, distribusi, frekuensi kata, clustering |
| Status | `GET /api/health` | Ketersediaan database, model, dan kamus |

Semua request memakai helper `api()` dari `frontend/js/ui.js` dan origin Flask yang sama.

## Batas fitur

- Like, komentar, login, registrasi, profil pengguna, dan publikasi puisi komunitas tidak disertakan karena API backend Puitika belum mendukungnya.
- Draf Studio disimpan pada instalasi Puitika dan belum memiliki autentikasi/pemisahan pemilik.
- Tema di Puitika mengikuti label backend, bukan kategori contoh LokaSajak.
