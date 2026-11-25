-- Tabel draf Studio Puisi. Dibuat otomatis saat python app.py dijalankan (aman diulang).
-- Satu draf = satu puisi yang sedang ditulis. Tanpa akun: semua draf milik instalasi ini.

CREATE TABLE IF NOT EXISTS drafts (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  title      VARCHAR(200) NOT NULL DEFAULT '',
  body       MEDIUMTEXT NOT NULL,
  tema       VARCHAR(50) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_drafts_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
