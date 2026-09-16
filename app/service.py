import csv
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.repository import insert_rows, soft_delete_row, get_export_cursor

# Number of CSV rows inserted into PostgreSQL per database operation.
BATCH_SIZE = 500


def process_csv(file):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed"
        )

    # Treat the uploaded file as a text file
    text_file = io.TextIOWrapper(
        file.file,
        encoding="utf-8",
        newline=""
    )

    reader = csv.DictReader(text_file)

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

    def generate_batches():
        batch = []

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

            # Yield a batch when it reaches 500 rows
            if len(batch) >= BATCH_SIZE:
                yield batch
                batch = []

        # Yield the final batch if it contains rows
        if batch:
            yield batch

    try:
        rows_inserted = insert_rows(generate_batches())

    except HTTPException:
        raise

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="CSV file must use UTF-8 encoding"
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )

    if rows_inserted == 0:
        raise HTTPException(
            status_code=400,
            detail="CSV contains no data rows"
        )

    return {
        "message": "CSV uploaded successfully",
        "rows_inserted": rows_inserted
    }


def delete_row(row_id):

    deleted = soft_delete_row(row_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Row not found"
        )

    return {
        "message": "Row deleted successfully",
        "row_id": row_id
    }


def export_data(from_date, to_date, format):
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

    # Get a server-side database cursor
    conn, cursor = get_export_cursor(
        from_date,
        to_date
    )

    # JSON export
    if format == "json":
        def generate_json():
            try:
                yield "["

                first_row = True

                while True:
                    rows = cursor.fetchmany(500)

                    if not rows:
                        break

                    for row in rows:
                        data = dict(zip(columns, row))

                        # Add a comma before every row except the first one
                        if not first_row:
                            yield ","


                        yield json.dumps(
                            data,
                            default=str
                        )

                        first_row = False

                yield "]"

            finally:
                cursor.close()
                conn.close()

        return StreamingResponse(
            generate_json(),
            media_type="application/json"
        )

    # CSV export
    def generate_csv():
        try:
            # Create the CSV header
            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(columns)

            # Send the header first
            yield output.getvalue()

            while True:
                rows = cursor.fetchmany(500)

                if not rows:
                    break

                # Create CSV for this batch
                output = io.StringIO()
                writer = csv.writer(output)

                for row in rows:
                    writer.writerow(row)

                # Send this batch to the client
                yield output.getvalue()

        finally:
            cursor.close()
            conn.close()

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=export.csv"
        }
    )
