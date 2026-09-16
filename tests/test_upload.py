def test_upload_csv(client):
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Test Company,10.5,100,2026-01-01\n"
    )

    response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert response.status_code == 200
    assert response.json()["rows_inserted"] == 1


def test_upload_rejects_non_csv(client):
    response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.txt",
                "some text",
                "text/plain"
            )
        }
    )

    assert response.status_code == 400


def test_upload_rejects_missing_columns(client):
    csv_content = (
        "index_code,isin,ticker\n"
        "TEST,TESTISIN,TEST\n"
    )

    response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert response.status_code == 400


def test_upload_rejects_invalid_date(client):
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Test Company,10.5,100,wrong-date\n"
    )

    response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert response.status_code == 400


def test_upload_rejects_invalid_number(client):
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
        "TEST,TESTISIN,TEST,Test Company,not-a-number,100,2026-01-01\n"
    )

    response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert response.status_code == 400


def test_upload_rejects_empty_csv(client):
    csv_content = (
        "index_code,isin,ticker,name,weight,shares,effective_date\n"
    )

    response = client.post(
        "/upload-csv/",
        files={
            "file": (
                "test.csv",
                csv_content,
                "text/csv"
            )
        }
    )

    assert response.status_code == 400
