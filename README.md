# Technical Test — Python + PostgreSQL

## 1. Overview

This project implements a REST API for importing, storing, managing, and exporting index constituent data.

The application:

- accepts CSV files through an API endpoint;
- validates and stores the CSV data in PostgreSQL;
- preserves historical records when the same business key is uploaded multiple times;
- supports soft deletion without physically removing data from the database;
- exports the current version of records for a requested date range;
- supports JSON and CSV export formats.

The implementation was developed as part of the BITA Technical Selection Process.

## 2. Technologies

- **Python**
- **FastAPI** — REST API framework
- **PostgreSQL** — relational database
- **psycopg2** — PostgreSQL database driver
- **python-dotenv** — environment variable management
- **csv** — Python standard library for CSV processing
- **Uvicorn** — ASGI server

## 3. Project Structure

```text
ThTst/
├── .venv/
├── database.py
├── main.py
├── README.md
└── requirements.txt
```
```.env``` is not committed to the repository because it contains database credentials.

## 4. Requirements

- **Python 3.9+**
- **PostgreSQL**
- **pip**

The application was developed and tested on Windows with a local PostgreSQL database

## 5. Installation and Setup
### 5.1 Create a virtual environment

Create and activate a Python virtual environment:
```text
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell does not allow script execution, the execution policy may need to be adjusted for the current user.

### 5.2 Install dependencies
Install the required dependencies from ```requirements.txt```:
```text
pip install -r requirements.txt
```

### 5.3 Configure environment variables
Create a ```.env``` file in the project root:
```text
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=index_constituents
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password
```
Replace ```your_password``` with the password of the local PostgreSQL user.
<br />The ```.env``` file is excluded from version control because it contains database credentials.

### 5.4 Create the PostgreSQL database
Create a PostgreSQL database named:
<br />```index_constituents```
<br />The application automatically creates the required table and indexes when it starts.

## 6. Running the Application
Start the FastAPI application with:
<br />```uvicorn main:app --reload```

The API will be available at:
<br />```The API will be available at:```

Interactive Swagger documentation is available at:
<br />```http://127.0.0.1:8000/docs```

The database table and indexes are created automatically when the application starts.

## 7. API Endpoints

### 7.1 Health / Root Endpoint
Endpoint:
``GET /``
Returns a simple message confirming that the API is running.
<br />Example response:
```text
{
    "message": "BITA Technical Test API"
}
```

### 7.2 Upload CSV
Endpoint:
```POST /upload-csv/```
Uploads and processes a CSV file.
<br />The expected CSV columns are:
```text
index_code
isin
ticker
name
weight
shares
effective_date
```

Example CSV:

| index_code | isin         | ticker | name                     | weight | shares | effective_date |
|------------|--------------|--------|--------------------------|--------|--------|----------------|
| DAX        | DE0007164600 | SAP    | SAP SE                   | 10.5   | 1000   | 2026-01-01     |
| DAX        | DE0007100000 | MBG    | Mercedes-Benz Group AG  | 5.2    | 500    | 2026-01-01     |

The endpoint:
1. validates that the uploaded file has a ```.csv``` extension;
2. reads the file as UTF-8 text;
3. validates the required columns;
4. processes rows one by one;
5. validates dates and numeric values;
6. inserts rows into PostgreSQL in batches;
7. commits the complete upload as one transaction.

Successful response:
```text
{
    "message": "CSV uploaded successfully",
    "rows_inserted": 2
}
```
The application does not overwrite existing rows. Re-uploading the same data creates additional records so that loading history is preserved.

### 7.3 Delete a Row
Endpoint:
```text
DELETE /delete/{row_id}
```
Example:
```text
DELETE /delete/123
```
The API does not physically delete the database row.
<br />Instead, it sets:
```
deleted = TRUE
```
The row therefore remains available in the database for historical purposes and potential recovery.
<br />It calls **Soft Delete**.

Successful response:
```text
{
    "message": "Row deleted successfully",
    "row_id": 123
}
```

If the specified ID does not exist:
<br />```404 Not Found```
<br />with:
```
{
    "detail": "Row not found"
}
```

### 7.4 Export Data
Endpoint:
```text
GET /export/
```
Required query parameters:
```text
from_date
to_date
format
```

Supported formats:
```text
json
csv
```

JSON example:
```GET /export/?from_date=2026-01-01&to_date=2026-01-31&format=json```

Example response:
```text
[
    {
        "id": 123,
        "index_code": "DAX",
        "isin": "DE0007164600",
        "ticker": "SAP",
        "name": "SAP SE",
        "weight": 10.5,
        "shares": 1000,
        "effective_date": "2026-01-01",
        "loaded_at": "2026-09-15T12:00:00"
    }
]
```

CSV example: ```GET /export/?from_date=2026-01-01&to_date=2026-01-31&format=csv```

The CSV response is returned as a downloadable file named: ```export.csv```

The export:
* filters records by ```effective_date```;
* excludes soft-deleted records;
* resolves multiple records with the same business key;
* returns only the current version of each business key.

## 8. Data Model
The application uses the following PostgreSQL table: ```index_constituents```

| Column           | Type        | Description                                      |
|------------------|-------------|--------------------------------------------------|
| `id`             | `BIGSERIAL` | Unique database row ID                           |
| `index_code`     | `TEXT`      | Index identifier                                 |
| `isin`           | `TEXT`      | Security identifier                              |
| `ticker`         | `TEXT`      | Security ticker                                  |
| `name`           | `TEXT`      | Security name                                    |
| `weight`         | `NUMERIC`   | Index weight                                     |
| `shares`         | `NUMERIC`   | Number of shares                                 |
| `effective_date` | `DATE`      | Date for which the constituent data is effective |
| `loaded_at`      | `TIMESTAMP` | Time when the row was loaded                     |
| `deleted`        | `BOOLEAN`   | Indicates whether the row has been soft-deleted  |

The database uses: ```id``` as the physical primary key.

## 9. Technical Decisions
### 9.1 Business Key and Versioning
The business key is: ```(index_code, isin, effective_date)```
<br />The database does not enforce this combination as a unique constraint.

<br />This is intentional because the same business key can be loaded multiple times and historical versions must be preserved.

When multiple records have the same business key, the API determines the current version using:
<br /> ```ORDER BY loaded_at DESC, id DESC```

The newest ```loaded_at``` value is considered the latest version.
<br />```id DESC``` is used as a deterministic tie-breaker if two records have the same ```loaded_at``` timestamp.

The export query uses:
```text
ROW_NUMBER() OVER (
    PARTITION BY index_code, isin, effective_date
    ORDER BY loaded_at DESC, id DESC
)
```
and returns only: ```row_number = 1```
<br /> This means that repeated uploads do not overwrite previous data.

### 9.2 CSV Upload Strategy
The application uses FastAPI's ```UploadFile```.

Instead of loading the entire uploaded file into memory, the file is processed through:
```text
io.TextIOWrapper(
    file.file,
    encoding="utf-8",
    newline=""
)
```
The CSV is then read row by row using Python's: ```csv.DictReader```
<br />This approach avoids unnecessarily loading the complete CSV file into Python memory.

### 9.3 Batch Insertion
Rows are collected into batches of 500: ```batch_size = 500```
<br />The application uses: ```execute_values()``` from ```psycopg2.extras``` to insert each batch efficiently.
<br />This provides better insertion performance than executing one SQL ```INSERT``` statement for every CSV row.
<br />The implementation intentionally does not use PostgreSQL's ```COPY``` command or another native bulk-import mechanism.

### 9.4 Numeric Values
The PostgreSQL columns ```weight``` and ```shares``` use: ```NUMERIC```
<br /> Python therefore uses: ```Decimal``` for these values instead of converting them to floating-point numbers.
<br /> This avoids unnecessary floating-point precision issues when working with database numeric values.

### 9.5 Soft Delete
Rows are never physically deleted from the database.
<br />Instead, was used:
```text
UPDATE index_constituents
SET deleted = TRUE
WHERE id = %s
```
This was chosen because the technical test requires deleted data to remain intact and recoverable.

<br />A deleted row can therefore be restored by setting: ```deleted = FALSE``` if recovery is required.
<br />Deleted rows are excluded from exports.

### 9.6 Export and Current Version Resolution
The export query first filters by: ```effective_date BETWEEN %s AND %s``` and ```deleted = FALSE```
<br />It then groups records by the business key and selects the newest non-deleted version.
<br />The current version is determined using:
```text
ROW_NUMBER() OVER (
    PARTITION BY index_code, isin, effective_date
    ORDER BY loaded_at DESC, id DESC
)
```
Only records with: ```row_number = 1``` are returned.

### 9.7 CSV Export Streaming
For CSV exports, the application uses a PostgreSQL server-side cursor:
```conn.cursor(name="export_cursor")```

<br />Results are retrieved in batches: ```cursor.fetchmany(500)``` and written to the response incrementally using a generator and ```StreamingResponse```.

This prevents the complete export from being loaded into Python memory at once.

The database cursor and connection are closed after the streaming generator finishes.

### 9.8 JSON Export
JSON exports also use a server-side cursor and: ```fetchmany(500)``` to read database results in batches.
<br />The resulting records are then collected into a Python list before being returned as a JSON response.

This means the database results are fetched incrementally, although the final JSON response is held in memory.

This is a deliberate trade-off to keep the JSON endpoint simple while still avoiding a large database ```fetchall()``` operation.


## 10. Transactions and Error Handling
CSV uploads are processed inside a single database transaction.
<br />If any error occurs while processing the upload: ```conn.rollback()``` is executed.

This provides an all-or-nothing behavior:
* successful CSV → all valid rows are committed;
* failed CSV → rows from that upload are rolled back.

For example, if a CSV contains two valid rows followed by an invalid row, the first two rows are also rolled back.

The API returns appropriate HTTP errors for common input problems, including:
* invalid file type;
* empty CSV;
* missing CSV columns;
* invalid dates;
* invalid numeric values;
* invalid date ranges;
* unsupported export formats;
* non-existent row IDs.


## 11. Database Indexes
Two indexes are created: **Effective date index**
```text
CREATE INDEX IF NOT EXISTS idx_index_constituents_effective_date
ON index_constituents (effective_date)
```
This supports queries that filter data by effective_date, which is used by the export endpoint.

**Business key index**
```text
CREATE INDEX IF NOT EXISTS idx_index_constituents_business_key
ON index_constituents (index_code, isin, effective_date)
```
This supports operations involving the business key used for current-version resolution.

The indexes are created automatically when the application starts.


## 12. Performance Considerations
Several decisions were made to avoid unnecessary memory usage and improve database performance.

**Upload**
<br />The upload process:
* reads the file incrementally;
* does not load the entire CSV into memory;
* inserts rows in batches of 500;
* uses ```execute_values()``` instead of one INSERT statement per row.

**Export**
<br />The CSV export:
* uses a server-side database cursor;
* fetches rows in batches of 500;
* streams the response to the client.

Therefore, a large CSV export does not need to be fully loaded into application memory.

**Database**
<br />Indexes are created for the main query patterns:
* filtering by effective_date;
* grouping by the business key.


## 13. Alternatives Considered
PostgreSQL ```COPY```
<br />```COPY``` would provide very high-performance bulk loading.

However, it was intentionally not used because the technical test explicitly excludes native PostgreSQL bulk-import mechanisms.

Instead, ```execute_values()``` is used with batches of 500 rows.

**One INSERT per row**
<br />Physical deletion would be simpler:
```text
DELETE FROM index_constituents
WHERE id = %s
```
However, it would permanently remove the underlying data.
<br />Soft deletion was chosen to preserve history and allow recovery.

**Unique constraint on the business key**
<br />A unique constraint such as:
```UNIQUE(index_code, isin, effective_date)``` would prevent duplicate business keys.

However, this would conflict with the requirement to preserve multiple historical loads of the same business key.

Therefore, the business key is handled at the application/query level instead.


## 14. Testing
The API was manually tested through the FastAPI Swagger documentation.
<br />The following cases were tested:
* non-CSV file upload;
* completely empty CSV;
* CSV containing headers but no data rows;
* missing required CSV column;
* invalid date;
* invalid numeric value;
* transaction rollback after an invalid row;
* deletion of a non-existent row;
* repeated deletion of the same row;
* soft deletion;
* confirmation that deleted rows remain in PostgreSQL;
* confirmation that deleted rows are excluded from exports;
* export with no matching records;
* JSON export;
* CSV export;
* inclusive date range filtering;
* repeated upload of the same data;
* current-version resolution after repeated uploads;
* deletion and current-version behavior.


## 15. Possible Improvements
For a production system, several additional improvements could be considered:
* add automated unit and integration tests with pytest;
* add structured application logging;
* add more detailed validation for empty required CSV fields;
* add authentication and authorization;
* use a more advanced configuration management approach for production environments;

These improvements were not necessary for the scope of the technical test but could be appropriate for a production environment.


## 16. Summary
The implementation focuses on:
* clear API design;
* reliable CSV validation;
* efficient batch insertion;
* PostgreSQL persistence;
* historical data preservation;
* recoverable soft deletion;
* deterministic current-version resolution;
* efficient CSV streaming;
* reasonable database indexing.

The implementation intentionally favors a simple and understandable architecture while addressing the main functional and performance requirements of the technical test.