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

-- Label tema/emosi. Satu puisi boleh punya banyak baris (emosi multi-label).
-- source: 'manual' = dilabeli sendiri, 'model' = prediksi sistem, 'user' = koreksi penulis.
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
