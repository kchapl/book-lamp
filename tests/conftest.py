import os
import sys

# Ensure the project root is importable
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def app():
    # Set test environment variables
    os.environ["TEST_MODE"] = "1"
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["GOOGLE_CLIENT_ID"] = "dummy-client-id"
    os.environ["GOOGLE_CLIENT_SECRET"] = "dummy-client-secret"
    os.environ["TEST_ALLOWED_EMAIL"] = "user@example.com"

    from book_lamp.app import app as flask_app

    flask_app.config.update(
        {
            "TESTING": True,
        }
    )

    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture()
def authenticated_client(client):
    """Client with active session."""
    with client.session_transaction() as sess:
        sess["user_email"] = "user@example.com"
        sess["user_name"] = "Test User"
    return client


@pytest.fixture(autouse=True)
def _storage_reset(app):
    """Reset mock storage before each test."""
    with app.app_context():
        from book_lamp.app import get_storage

        storage = get_storage()

        if hasattr(storage, "books"):
            storage.books = []
            storage.reading_records = []
            storage.reading_list = []
            storage.next_book_id = 1
            storage.next_record_id = 1
        if hasattr(storage, "set_authorised"):
            storage.set_authorised(True)
        yield
