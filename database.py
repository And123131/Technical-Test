import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()


DB_CONFIG = {
    "host": os.getenv("DATABASE_HOST"),
    "port": os.getenv("DATABASE_PORT"),
    "database": os.getenv("DATABASE_NAME"),
    "user": os.getenv("DATABASE_USER"),
    "password": os.getenv("DATABASE_PASSWORD"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS index_constituents (
                id BIGSERIAL PRIMARY KEY,
                index_code TEXT NOT NULL,
                isin TEXT NOT NULL,
                ticker TEXT,
                name TEXT,
                weight NUMERIC,
                shares NUMERIC,
                effective_date DATE NOT NULL,
                loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

        # helps PostgreSQL find rows for 'WHERE effective_date BETWEEN %s AND %s' in export
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_index_constituents_effective_date
            ON index_constituents (effective_date)
        """)

        # matches our business key, used in export 'PARTITION BY index_code, isin, effective_date'
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_index_constituents_business_key
            ON index_constituents (index_code, isin, effective_date)
        """)

        conn.commit()

    except Exception:
        # to rollback and have ability to close connection
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()
