-- Jalankan sekali pada database puitika yang sudah ada.
-- Migration aman: hanya membuat tabel baru, tidak menghapus/mengubah data lama.
USE puitika;

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
