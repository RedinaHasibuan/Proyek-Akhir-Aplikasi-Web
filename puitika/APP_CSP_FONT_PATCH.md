# Penyesuaian CSP untuk font Puitika

Frontend memakai Playfair Display, Lora, Plus Jakarta Sans, dan Caveat melalui Google Fonts. Karena `app.py` memakai Content Security Policy, izinkan origin font tersebut agar font tampil; jika tidak, browser akan memakai fallback lokal Georgia/sans-serif.

Pada `app.py`, cari konstanta `CSP` dan ubah **konstanta itu saja** menjadi:

```python
CSP = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)
```

Jangan mengganti endpoint, koneksi database, atau keseluruhan `app.py`. Semua script aplikasi tetap dimuat dari origin sendiri (`/app/js/...`). Jika ingin sepenuhnya offline, hapus dua tag `preconnect` dan link Google Fonts di `frontend/index.html`; font fallback tetap tersedia.
