import os
import sys
import pytest

# Ensure the app uses an in-memory SQLite database during tests
os.environ.setdefault("DB_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "dummy-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dummy-client-secret")

# Ensure the project root is importable when pytest changes CWD
PROJECT_ROOT = "/Users/kelvin/code/book-lamp"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app as flask_app  # noqa: E402


@pytest.fixture()
def client():
    with flask_app.test_client() as client:
        yield client 