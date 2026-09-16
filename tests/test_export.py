def test_export_json(client):
    # First upload a row
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Test Company,10.5,100,2026-01-01\n"
    )

    upload_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert upload_response.status_code == 200

    # Request the data as JSON
    response = client.get(
        "/export/?from_date=2026-01-01&to_date=2026-01-01&format=json"
    )

    assert response.status_code == 200

    data = response.json()

    # We uploaded one row, so export should contain one row
    assert len(data) == 1

    # Check the exported values
    assert data[0]["id"] == 1
    assert data[0]["index_code"] == "TEST"
    assert data[0]["isin"] == "TESTISIN"
    assert data[0]["ticker"] == "TEST"
    assert data[0]["name"] == "Test Company"
    assert float(data[0]["weight"]) == 10.5
    assert float(data[0]["shares"]) == 100
    assert data[0]["effective_date"] == "2026-01-01"


def test_export_csv(client):
    # First upload a row
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Test Company,10.5,100,2026-01-01\n"
    )

    upload_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert upload_response.status_code == 200

    # Request the data as CSV
    response = client.get(
        "/export/?from_date=2026-01-01&to_date=2026-01-01&format=csv"
    )

    assert response.status_code == 200

    # Check that the response is a CSV file
    assert response.headers["content-type"].startswith("text/csv")

    # Read the CSV content
    csv_output = response.text

    # Check the header
    assert "id,index_code,isin,ticker,name,weight,shares,effective_date,loaded_at" in csv_output

    # Check the exported row
    assert "1,TEST,TESTISIN,TEST,Test Company,10.5,100,2026-01-01" in csv_output


def test_export_respects_date_range(client):
    # Upload two rows with different effective dates
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST1,ISIN1,TICK1,Company One,10.5,100,2026-01-01\n"
        "TEST2,ISIN2,TICK2,Company Two,20.5,200,2026-02-01\n"
    )

    upload_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert upload_response.status_code == 200
    assert upload_response.json()["rows_inserted"] == 2

    # Export only January data
    response = client.get(
        "/export/?from_date=2026-01-01&to_date=2026-01-31&format=json"
    )

    assert response.status_code == 200

    data = response.json()

    # Only the January row should be returned
    assert len(data) == 1
    assert data[0]["index_code"] == "TEST1"
    assert data[0]["effective_date"] == "2026-01-01"


def test_export_excludes_deleted_row(client):
    # First upload a row
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Test Company,10.5,100,2026-01-01\n"
    )

    upload_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert upload_response.status_code == 200

    # Delete the row using the API
    delete_response = client.delete("/delete/1")

    assert delete_response.status_code == 200

    # Export the same date range
    response = client.get(
        "/export/?from_date=2026-01-01&to_date=2026-01-01&format=json"
    )

    assert response.status_code == 200

    data = response.json()

    # Deleted rows must not appear in the export
    assert data == []


def test_export_returns_latest_version(client):
    # Upload the first version
    first_csv = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Old Company Name,10.5,100,2026-01-01\n"
    )

    first_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "first.csv",
                first_csv,
                "text/csv"
            )
        }
    )

    assert first_response.status_code == 200

    # Upload a second version with the same business key
    # but different data
    second_csv = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,New Company Name,20.5,200,2026-01-01\n"
    )

    second_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "second.csv",
                second_csv,
                "text/csv"
            )
        }
    )

    assert second_response.status_code == 200

    # Export the data
    response = client.get(
        "/export/?from_date=2026-01-01&to_date=2026-01-01&format=json"
    )

    assert response.status_code == 200

    data = response.json()

    # Only the latest version should be returned
    assert len(data) == 1

    assert data[0]["id"] == 2
    assert data[0]["name"] == "New Company Name"
    assert float(data[0]["weight"]) == 20.5
    assert float(data[0]["shares"]) == 200


def test_export_returns_previous_version_when_latest_is_deleted(client):
    # Upload the first version
    first_csv = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Old Company Name,10.5,100,2026-01-01\n"
    )

    first_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "first.csv",
                first_csv,
                "text/csv"
            )
        }
    )

    assert first_response.status_code == 200

    # Upload the second version with the same business key
    second_csv = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,New Company Name,20.5,200,2026-01-01\n"
    )

    second_response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "second.csv",
                second_csv,
                "text/csv"
            )
        }
    )

    assert second_response.status_code == 200

    # Delete the latest version
    delete_response = client.delete("/delete/2")

    assert delete_response.status_code == 200

    # Export the data
    response = client.get(
        "/export/?from_date=2026-01-01&to_date=2026-01-01&format=json"
    )

    assert response.status_code == 200

    data = response.json()

    # The previous active version should be returned
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["name"] == "Old Company Name"
    assert float(data[0]["weight"]) == 10.5
    assert float(data[0]["shares"]) == 100


def test_export_rejects_invalid_date(client):
    response = client.get(
        "/export/?from_date=wrong-date&to_date=2026-01-01&format=json"
    )

    assert response.status_code == 422


def test_export_rejects_invalid_date_range(client):
    response = client.get(
        "/export/?from_date=2026-02-01&to_date=2026-01-01&format=json"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "'from_date' must be before or equal to 'to_date'"
    )


def test_export_rejects_invalid_format(client):
    response = client.get(
        "/export/?from_date=2026-01-01&to_date=2026-01-01&format=xml"
    )

    assert response.status_code == 422


def test_export_returns_empty_result_when_no_data_matches(client):
    response = client.get(
        "/export/?from_date=2027-01-01&to_date=2027-01-31&format=json"
    )

    assert response.status_code == 200

    data = response.json()

    # No rows exist in this date range
    assert data == []
