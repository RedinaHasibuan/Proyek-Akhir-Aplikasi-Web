"""Penyimpanan opsional hasil sentiment analysis ke MySQL Puitika.

Hasil hanya disimpan setelah pengguna secara eksplisit menyetujui penyimpanan.
Teks puisi mentah tidak disimpan di tabel ini.
"""
import json

import pymysql

import config


def save_sentiment_result(result, poem_id=None, consent=False):
    """Simpan hasil analyze_sentiment() ke poem_sentiment_analyses.

    consent harus True setelah pengguna memilih menyimpan hasil.
    poem_id boleh None untuk analisis teks sementara yang disetujui untuk disimpan.
    """
    if consent is not True:
        raise PermissionError("Hasil analisis tidak disimpan tanpa persetujuan eksplisit pengguna.")
    if not isinstance(result, dict) or "polarity" not in result:
        raise ValueError("result harus berupa keluaran analyze_sentiment().")

    evidence = result.get("evidence", {})
    positive_terms = json.dumps(evidence.get("positif", []), ensure_ascii=False)
    negative_terms = json.dumps(evidence.get("negatif", []), ensure_ascii=False)

    connection = pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO poem_sentiment_analyses
                   (poem_id, method, polarity, score, positive_score, negative_score,
                    token_count, matched_token_count, positive_terms, negative_terms, analyzer_version)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    poem_id,
                    result.get("method", "lexicon"),
                    result["polarity"],
                    result.get("score", 0.0),
                    result.get("positive_score", 0.0),
                    result.get("negative_score", 0.0),
                    result.get("token_count", 0),
                    result.get("matched_token_count", 0),
                    positive_terms,
                    negative_terms,
                    result.get("analyzer_version", "lexicon-id-puisi-0.1"),
                ),
            )
            saved_id = cursor.lastrowid
        connection.commit()
        return saved_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
