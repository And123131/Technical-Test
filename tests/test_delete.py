from app import database


def test_delete_existing_row(client):
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

    # The first inserted row gets ID 1 in our clean test database
    delete_response = client.delete("/delete/1")

    assert delete_response.status_code == 200
    assert delete_response.json()["row_id"] == 1

    # Check that the row still exists in the database
    conn = database.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT deleted
        FROM index_constituents
        WHERE id = %s
        """,
        (1,)
    )

    row = cursor.fetchone()

    cursor.close()
    conn.close()

    assert row is not None

    # The row must be marked as deleted
    assert row[0] is True


def test_delete_nonexistent_row(client):
    response = client.delete("/delete/999999")

    assert response.status_code == 404
