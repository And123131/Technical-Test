# Index Constituents API - Python + PostgreSQL

## 1. Overview
**The application:**

Service for ingesting, storing, versioning, soft-deleting, and exporting index constituent data using Fast API and PostgreSQL.


## 2. Technologies

- **Python**
- **FastAPI** — REST API framework
- **PostgreSQL** — relational database
- **psycopg2** — PostgreSQL database driver
- **python-dotenv** — environment variable management
- **csv** — Python standard library for CSV processing
- **Pytest** — automated testing
- **Uvicorn** — ASGI server

## 3. Project Structure

```text
Project/
├── app/
│   ├── __init__.py
│   ├── api.py
│   ├── database.py
│   ├── main.py
│   ├── repository.py
│   └── service.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_delete.py
│   ├── test_export.py
│   └── test_upload.py
│
├── .gitignore
├── pytest.ini
├── README.md
└── requirements.txt
```
```.env``` is not committed to the repository because it contains database credentials.

The application is separated into several layers:
* main.py — FastAPI application startup;
* api.py — API routes;
* service.py — Functionality of application;
* repository.py — PostgreSQL queries;
* database.py — database configuration, connection handling, table creation;
* tests/ — behavior tests.

## 4. Requirements

- **Python 3.10+**
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


### 5.4 Create the PostgreSQL database
Create a PostgreSQL database named: ```index_constituents```
<br />The application automatically creates the required table and indexes when it starts.

Also create a PostgreSQL database named `index_constituents_test` for tests.

## 6. Running the Application
Start the FastAPI application with:
<br />```uvicorn app.main:app --reload```

The API will be available at:
<br />```http://127.0.0.1:8000```

Interactive Swagger documentation is available at:
<br />```http://127.0.0.1:8000/docs```


## 7. API Endpoints

### 7.1 Root Endpoint
Endpoint:
``GET /``
Returns a simple message confirming that the API is running.
<br />Example response:
```text
{
    "message": "Test API"
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


Successful response:
```text
{
    "message": "CSV uploaded successfully",
    "rows_inserted": 2
}
```
Existing rows are never overwritten.

Uploading the same business key again creates a new database record so that the loading history is preserved.


### 7.3 Export Data
Endpoint:
```text
GET /export/
```
Required query parameters:
```text
from_date
to_date
format (optional and defaults to JSON)
```

Supported formats:
```text
json
csv
```

**JSON** example:
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
        "weight": "10.5",
        "shares": "1000",
        "effective_date": "2026-01-01",
        "loaded_at": "2026-09-15T12:00:00"
    }
]
```

**CSV** example: ```GET /export/?from_date=2026-01-01&to_date=2026-01-31&format=csv```

The CSV response is returned as a downloadable file named: ```export.csv```

The export:
* filters records by `effective_date` using an inclusive date range;
* excludes soft-deleted records;
* groups records by the business key;
* selects the latest non-deleted version of each business key;
* returns the resulting records in the requested format.

Invalid dates or unsupported formats are rejected with HTTP ```422```.

An invalid date range, where ```from_date``` is later than ```to_date```, returns HTTP ```400```.


### 7.4 Soft Delete
Rows are never physically deleted from the database.
<br />Instead, was used:
```text
UPDATE index_constituents
SET deleted = TRUE
WHERE id = %s
```
This was chosen because the technical test requires deleted data to remain intact and recoverable.

A deleted row can therefore be restored by setting: ```deleted = FALSE``` if recovery is required.
<br />Deleted rows are excluded from exports.


Endpoint:
```text
DELETE /delete/{row_id}
```
Example:
```text
DELETE /delete/123
```
<br />After, it performs a **Soft Delete**: The original row therefore remains in the database.

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

This is intentional because the same business key can be loaded multiple times and historical versions must be preserved.

When multiple non-deleted records have the same business key, the newest ```loaded_at``` value is considered the current version.


### 9.2 CSV Upload Strategy

Rows are processed incrementally instead of loading the complete CSV file into a Python list.
<br />This reduces application memory usage for larger uploads.

### 9.3 Batch Insertion
Rows are collected into batches of 500: ```BATCH_SIZE = 500```
<br />This provides better insertion performance than going through every CSV row.


## 10. Transactions and Error Handling
If any error occurs while processing the upload - it will roll back.

This provides an all-or-nothing behavior:
* successful CSV → all valid rows are committed;
* failed CSV → rows from that upload are rolled back.

For example, if a CSV contains two valid rows followed by an invalid row, the first two rows are also rolled back.


## 11. Database Indexes
Two indexes are created: **Effective date**, **index**

This supports queries that filter data by ```effective_date```, which is used by the export endpoint.

**Business key index**
<br />This index supports queries that filter or organize records by the business key used for current-version resolution.
<br />Application startup can be run repeatedly without attempting to recreate existing indexes.


**Database**
<br />Indexes are created for the main query patterns:
* filtering by ```effective_date```;
* grouping/filtering by the business key.


## 12.Alternatives Considered
PostgreSQL ```COPY```
<br />```COPY``` would provide very high-performance bulk loading.

Instead, execute_values() is used with batches of 500 rows.
<br />Soft deletion was chosen to preserve history and allow recovery.
<br />Physical delete was rejected because data must remain recoverable.

## 14. Testing
The project contains automated tests implemented with ```pytest```.
<br /> Run the complete test suite with: ```pytest```

The current test suite contains automated tests covering the behavior.

The API was also manually tested through FastAPI Swagger documentation.