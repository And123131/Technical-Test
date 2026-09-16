from psycopg2.extras import execute_values

from app.database import get_connection


def insert_rows(batches):
    conn = get_connection()
    cursor = conn.cursor()

    rows_inserted = 0

    try:
        for batch in batches:

            execute_values(
                cursor,
                """
                INSERT INTO index_constituents (
                    index_code,
                    isin,
                    ticker,
                    name,
                    weight,
                    shares,
                    effective_date
                )
                VALUES %s
                """,
                batch
            )

            rows_inserted += len(batch)

        # Commit only after ALL batches succeeded
        conn.commit()

        return rows_inserted

    except Exception:
        # Undo ALL batches if any batch fails
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def soft_delete_row(row_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE index_constituents
            SET deleted = TRUE
            WHERE id = %s
            """,
            (row_id,)
        )

        # Check whether a row with this ID exists
        if cursor.rowcount == 0:
            return False

        conn.commit()

        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


def get_export_cursor(from_date, to_date):
    conn = get_connection()

    # Server-side cursor prevents PostgreSQL from sending
    # the entire result set to Python at once.
    cursor = conn.cursor(name="export_cursor")

    cursor.execute(
        """
        SELECT
            id,
            index_code,
            isin,
            ticker,
            name,
            weight,
            shares,
            effective_date,
            loaded_at
        FROM (
            SELECT
                id,
                index_code,
                isin,
                ticker,
                name,
                weight,
                shares,
                effective_date,
                loaded_at,
                deleted,

                /*
                    The business key is:
                    (index_code, isin, effective_date).
                
                    Multiple rows with the same business key are allowed.
                    We consider the newest non-deleted upload to be the current version.
                    'id' is used as a tie-breaker if two rows have the same loaded_at.
                */
                ROW_NUMBER() OVER (
                    PARTITION BY index_code, isin, effective_date

                    /* newest row gets number 1 */
                    ORDER BY loaded_at DESC, id DESC
                ) AS row_number

            FROM index_constituents

            WHERE effective_date BETWEEN %s AND %s

                /* deleted rows are removed from consideration */
                AND deleted = FALSE

        ) AS current_rows

        /* Keep only the current version for each business key */
        WHERE row_number = 1

        ORDER BY effective_date, id
        """,
        (from_date, to_date)
    )

    return conn, cursor
