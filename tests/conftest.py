import os
import sys

import pytest

# Test environment configuration
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "dummy-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dummy-client-secret")

# Ensure the project root is importable when pytest changes CWD
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from book_lamp.app import app as flask_app  # noqa: E402


@pytest.fixture()
def client():
    with flask_app.test_client() as client:
        yield client
