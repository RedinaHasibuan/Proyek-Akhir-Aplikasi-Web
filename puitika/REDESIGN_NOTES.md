# Catatan Redesign Puitika — Cozy Literary Archive

## Arah desain
Puitika tetap menjadi arsip dan ruang olah puisi Indonesia. Referensi LokaSajak dipakai sebagai inspirasi nuansa journaling, kertas hangat, tipografi editorial, kartu dengan aksen bookmark, dan komposisi baca yang tenang—bukan untuk mengganti nama Puitika atau mengklaim fitur komunitas yang belum didukung backend.

## Palet warna
| Peran | Hex |
|---|---|
| Latar warm paper | `#F5F1EA` |
| Permukaan kartu | `#FFFCF7` |
| Krem/border | `#D4CCC1` |
| Tinta espresso | `#42250B` |
| Caramel | `#A9682A` |
| Autumn highlight | `#E48025` |
| Muted sage | `#8E957F` |
| **Light sage / hijau muda** | **`#E3EAD9`** |
| Sage mist | `#EEF2E9` |
| Sage ink | `#596A4E` |

Hijau muda dipakai pada surface hero, ikon, label, state aktif, kartu fitur, dan bidang catatan Puitika agar menjadi warna penyeimbang nyata—bukan sekadar aksen kecil.

## Tipografi
- Playfair Display untuk judul.
- Lora untuk isi puisi dan teks editorial.
- Plus Jakarta Sans untuk navigasi dan UI.
- Caveat untuk catatan tangan.
- Google Fonts opsional; fallback lokal tetap disediakan. Sesuaikan CSP sesuai `APP_CSP_FONT_PATCH.md`.

## Layout dan panjang halaman
- Desktop: sidebar espresso sekitar 248px; area kerja menggunakan kanvas terang dan lebar konten fleksibel.
- Tablet/ponsel: sidebar desktop diganti topbar ringkas dan drawer; tidak lagi memaksa sidebar tinggi di sisi kiri layar sempit. Drawer bisa ditutup dengan tombol, backdrop, klik menu, atau tombol Escape.
- Beranda diringkas menjadi hero pencarian diksi yang lebih pendek + lima kartu pintasan + catatan Puitika yang dipindahkan dari sidebar. Sidebar hanya berisi identitas dan navigasi; status server tidak ditampilkan kepada pengunjung (endpoint /api/health tetap tersedia untuk diagnostik). Hero dan kartu dipadatkan agar desktop mengurangi scroll yang tidak perlu; pada ponsel, scroll tetap wajar karena kartu ditumpuk responsif.
- Halaman lain mempertahankan fungsi berbeda, namun menggunakan sistem warna, tipografi, jarak, tombol, dan kartu yang konsisten.

## Batas fungsional
Frontend tetap memakai endpoint backend Puitika yang tersedia. Tema memakai label backend: `romansa`, `alam`, `sosial`, `kehidupan`, `religius`. Autentikasi, akun, like, komentar, dan profil komunitas tidak ditampilkan sebagai fitur aktif karena backend saat ini belum menyediakan API untuk itu. Draf Studio tetap tersimpan sebagai data instalasi, bukan akun pengguna.
