from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation  # PostgreSQL uses decimals, we would use them too

from psycopg2.extras import execute_values  # to send many rows in a batch

from database import create_tables, get_connection


app = FastAPI()


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/")
def index():
    return {"message": "Test API"}


@app.post("/upload-csv/")
def upload_csv(file: UploadFile = File(...)):

    # Check file extension
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed"
        )

    conn = get_connection()
    cursor = conn.cursor()

    batch = []
    batch_size = 500
    rows_inserted = 0

    try:
        # Treat the uploaded file as a text file
        text_file = io.TextIOWrapper(
            file.file,  # working directly with file
            encoding="utf-8",
            newline=""
        )

        reader = csv.DictReader(text_file)

        # Check CSV columns
        if not reader.fieldnames:
            raise HTTPException(
                status_code=400,
                detail="CSV has no columns"
            )

        required_columns = {
            "index_code",
            "isin",
            "ticker",
            "name",
            "weight",
            "shares",
            "effective_date",
        }

        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing columns: {sorted(missing_columns)}"
            )

        # Process CSV row by row
        for row in reader:

            try:
                effective_date = datetime.strptime(
                    row["effective_date"],
                    "%Y-%m-%d"
                ).date()

                weight = Decimal(row["weight"])
                shares = Decimal(row["shares"])

            except (ValueError, TypeError, InvalidOperation):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date, weight, or shares value"
                )

            batch.append(
                (
                    row["index_code"],
                    row["isin"],
                    row["ticker"],
                    row["name"],
                    weight,
                    shares,
                    effective_date
                )
            )

            # Insert every 500 rows
            if len(batch) >= batch_size:

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
                batch.clear()

        # Insert remaining rows
        if batch:
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

        if rows_inserted == 0:
            raise HTTPException(
                status_code=400,
                detail="CSV contains no data rows"
            )

        conn.commit()

    except HTTPException:
        conn.rollback()
        raise

    except UnicodeDecodeError:
        conn.rollback()
        raise HTTPException(
            status_code=400,
            detail="CSV file must use UTF-8 encoding"
        )

    except Exception as error:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {error}"
        )

    finally:
        cursor.close()
        conn.close()

    return {
        "message": "CSV uploaded successfully",
        "rows_inserted": rows_inserted
    }


@app.delete("/delete/{row_id}")
def delete_row(row_id: int):
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

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Row not found"
            )

        conn.commit()

    except HTTPException:
        conn.rollback()
        raise

    except Exception as error:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {error}"
        )

    finally:
        cursor.close()
        conn.close()

    return {
        "message": "Row deleted successfully",
        "row_id": row_id
    }


@app.get("/export/")
def export(
        from_date: str,
        to_date: str,
        format: str = "json"
):
    try:
        from_date = datetime.strptime(
            from_date,
            "%Y-%m-%d"
        ).date()

        to_date = datetime.strptime(
            to_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Dates must use YYYY-MM-DD format"
        )

    if from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="'from_date' must be before or equal to 'to_date'"
        )

    if format not in {"json", "csv"}:
        raise HTTPException(
            status_code=400,
            detail="Format must be either 'json' or 'csv'"
        )

    columns = [
        "id",
        "index_code",
        "isin",
        "ticker",
        "name",
        "weight",
        "shares",
        "effective_date",
        "loaded_at"
    ]

    conn = get_connection()

    # creates a server-side cursor instead of loading all database
    # results into Python memory at once
    cursor = conn.cursor(name="export_cursor")

    try:
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
                    /* groups rows according to our business key */
                    ROW_NUMBER() OVER (
                        PARTITION BY index_code, isin, effective_date
                        /* the newest row gets */
                        ORDER BY loaded_at DESC, id DESC
                    ) AS row_number
                FROM index_constituents
                WHERE effective_date BETWEEN %s AND %s
                    /* deleted rows are removed from consideration */
                  AND deleted = FALSE
            ) AS current_rows
            /* keeps only the current version */
            WHERE row_number = 1
            ORDER BY effective_date, id
            """,
            (from_date, to_date)
        )

        # JSON export
        if format == "json":
            result = []
            while True:
                # takes up to 500 results from the database at a time
                rows = cursor.fetchmany(500)

                # stops when there are no more rows
                if not rows:
                    break

                for row in rows:
                    # zip() pairs SQL return with our columns
                    # and dict() turns those pairs into a dictionary
                    result.append(dict(zip(columns, row)))

            return result

    finally:
        # For JSON, the cursor and connection can be closed here
        # because all data has already been read.
        if format == "json":
            cursor.close()
            conn.close()

    # CSV export
    def generate_csv():
        try:
            # create an in-memory text file for one CSV chunk
            output = io.StringIO()

            # creates a CSV writer
            writer = csv.writer(output)

            # writes the CSV column names
            writer.writerow(columns)

            # sends the header to the client
            yield output.getvalue()

            while True:
                # takes up to 500 results from the database at a time
                rows = cursor.fetchmany(500)

                # stops when there are no more rows
                if not rows:
                    break

                # create a new in-memory text file for this batch
                output = io.StringIO()

                # creates a CSV writer
                writer = csv.writer(output)

                # writes the current database records into the CSV
                for row in rows:
                    writer.writerow(row)

                # sends only this batch to the client
                yield output.getvalue()

        finally:
            # close the database resources after the whole CSV
            # has been streamed to the client
            cursor.close()
            conn.close()

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=export.csv"
        }
    )
