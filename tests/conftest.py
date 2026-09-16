import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import database


@pytest.fixture
def client():
    # Save the original database name
    original_database = database.DB_CONFIG["database"]

    # Use the separate test database
    database.DB_CONFIG["database"] = "index_constituents_test"

    # Create the tables in the test database
    database.create_tables()

    # Remove old test data before each test
    conn = database.get_connection()
    cursor = conn.cursor()

    # Remove old test data and reset the ID sequence
    cursor.execute("TRUNCATE TABLE index_constituents RESTART IDENTITY")

    conn.commit()

    cursor.close()
    conn.close()

    yield TestClient(app)

    # Restore the original database name
    database.DB_CONFIG["database"] = original_database
