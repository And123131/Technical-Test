import os

from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv


load_dotenv()


DB_CONFIG = {
    "host": os.getenv("DATABASE_HOST"),
    "port": os.getenv("DATABASE_PORT"),
    "database": os.getenv("DATABASE_NAME"),
    "user": os.getenv("DATABASE_USER"),
    "password": os.getenv("DATABASE_PASSWORD"),
}

connection_pool = ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    **DB_CONFIG
)


def get_connection():
    return connection_pool.getconn()


def release_connection(conn):
    connection_pool.putconn(conn)


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
        # roll back the transaction if an error occurs.
        # the connection is closed in the finally block.
        conn.rollback()
        raise

    finally:
        cursor.close()
        release_connection(conn)
