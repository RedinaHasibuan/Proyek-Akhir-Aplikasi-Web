-- Skema database Puitika (tahap data). Tabel lain (drafts, log aktivitas, dst.)
-- ditambahkan nanti saat fiturnya dikerjakan.

CREATE DATABASE IF NOT EXISTS puitika
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE puitika;

-- Penyair (satu baris per nama unik; name_key = huruf kecil + spasi dirapikan)
CREATE TABLE IF NOT EXISTS poets (
  id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name      VARCHAR(150) NOT NULL,
  name_key  VARCHAR(150) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_poets_name_key (name_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Puisi. in_public_library = 1 hanya untuk puisi yang boleh ditampilkan di
-- Perpustakaan Puisi (Wikisumber: domain publik / lisensi bebas).
-- Puisi ID Puisi (in_public_library = 0) hanya untuk eksperimen internal.
CREATE TABLE IF NOT EXISTS poems (
  id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
  poet_id            INT UNSIGNED NULL,
  title              VARCHAR(200) NOT NULL,
  body               MEDIUMTEXT NOT NULL,
  source             ENUM('wikisumber','idpuisi','user') NOT NULL,
  source_key         VARCHAR(255) NOT NULL,
  source_url         VARCHAR(500) NULL,
  license            VARCHAR(255) NULL,
  in_public_library  TINYINT(1) NOT NULL DEFAULT 0,
  body_hash          CHAR(40) NOT NULL,
  n_lines            INT UNSIGNED NOT NULL DEFAULT 0,
  n_stanzas          INT UNSIGNED NOT NULL DEFAULT 0,
  n_words            INT UNSIGNED NOT NULL DEFAULT 0,
  created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_poems_source_key (source, source_key),
  UNIQUE KEY uq_poems_body_hash (body_hash),
  KEY idx_poems_poet (poet_id),
  KEY idx_poems_public (in_public_library),
  FULLTEXT KEY ft_poems_title_body (title, body),
  CONSTRAINT fk_poems_poet FOREIGN KEY (poet_id) REFERENCES poets(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Label tema utama dan anotasi emosi historis/eksperimen.
-- Model utama aplikasi hanya menghasilkan label_type='tema'.
-- Baris label_type='emosi' dari eksperimen lama dipertahankan untuk dokumentasi,
-- bukan dipakai sebagai klasifikasi produksi. Sentiment polarity disimpan terpisah.
-- source: 'manual' = anotasi, 'model' = prediksi sistem, 'user' = koreksi penulis.
CREATE TABLE IF NOT EXISTS poem_labels (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  poem_id     INT UNSIGNED NOT NULL,
  label_type  ENUM('tema','emosi') NOT NULL,
  label       VARCHAR(50) NOT NULL,
  score       DECIMAL(5,4) NULL,
  source      ENUM('manual','model','user') NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_label (poem_id, label_type, label, source),
  KEY idx_label_lookup (label_type, label),
  CONSTRAINT fk_labels_poem FOREIGN KEY (poem_id) REFERENCES poems(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Hasil sentiment analysis untuk fitur Makna Puisi.
-- poem_id boleh NULL untuk teks yang dianalisis sementara dan tidak disimpan sebagai puisi.
-- Jangan menyimpan teks puisi privat mentah di tabel ini; simpan hasil analisis saja.
CREATE TABLE IF NOT EXISTS poem_sentiment_analyses (
  id                   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  poem_id              INT UNSIGNED NULL,
  method               ENUM('lexicon','supervised') NOT NULL DEFAULT 'lexicon',
  polarity             ENUM('positif','negatif','netral','campuran','tidak_terdeteksi') NOT NULL,
  score                 DECIMAL(7,4) NOT NULL DEFAULT 0.0000,
  positive_score       DECIMAL(8,4) NOT NULL DEFAULT 0.0000,
  negative_score       DECIMAL(8,4) NOT NULL DEFAULT 0.0000,
  token_count           INT UNSIGNED NOT NULL DEFAULT 0,
  matched_token_count   INT UNSIGNED NOT NULL DEFAULT 0,
  positive_terms        TEXT NULL,
  negative_terms        TEXT NULL,
  analyzer_version      VARCHAR(60) NOT NULL DEFAULT 'lexicon-id-puisi-0.1',
  created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_sentiment_poem (poem_id),
  KEY idx_sentiment_polarity (polarity),
  KEY idx_sentiment_method (method),
  CONSTRAINT fk_sentiment_poem FOREIGN KEY (poem_id)
    REFERENCES poems(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
