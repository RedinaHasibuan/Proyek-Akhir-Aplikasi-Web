-- Skema Ruang Diksi. Dijalankan oleh: python load_diksi.py --init
-- Aman diulang (IF NOT EXISTS). Jangan taruh tanda titik koma di dalam komentar.

CREATE TABLE IF NOT EXISTS dictionary_entries (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  word       VARCHAR(100) NOT NULL,
  word_key   VARCHAR(100) NOT NULL,
  pos        VARCHAR(40) NULL,
  meaning    TEXT NOT NULL,
  nuance     VARCHAR(255) NULL,
  example    TEXT NULL,
  keywords   VARCHAR(500) NULL,
  emotion    VARCHAR(20) NULL,
  verified   TINYINT(1) NOT NULL DEFAULT 0,
  source     VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dict_word_key (word_key),
  KEY idx_dict_emotion (emotion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dictionary_relations (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  entry_id      INT UNSIGNED NOT NULL,
  related_id    INT UNSIGNED NOT NULL,
  relation_type VARCHAR(20) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_dict_rel (entry_id, related_id, relation_type),
  KEY idx_dict_rel_related (related_id),
  CONSTRAINT fk_rel_entry FOREIGN KEY (entry_id) REFERENCES dictionary_entries(id) ON DELETE CASCADE,
  CONSTRAINT fk_rel_related FOREIGN KEY (related_id) REFERENCES dictionary_entries(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
