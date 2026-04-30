from unittest.mock import patch

from book_lamp.app import app


def test_sync_diagnostics_endpoint_with_async_storage():
    class FakeAsyncStorage:
        def is_authorised(self):
            return True

        def get_sync_diagnostics(self):
            return {"outbox": {"failed": 0}, "bootstrapped": True}

    app.config["TESTING"] = True
    with app.test_client() as client:
        with patch("book_lamp.app.get_storage", return_value=FakeAsyncStorage()):
            resp = client.get("/api/sync/diagnostics")
            assert resp.status_code == 200
            assert resp.json["bootstrapped"] is True


def test_sync_diagnostics_endpoint_when_disabled():
    class FakeStorage:
        def is_authorised(self):
            return True

    app.config["TESTING"] = True
    with app.test_client() as client:
        with patch("book_lamp.app.get_storage", return_value=FakeStorage()):
            resp = client.get("/api/sync/diagnostics")
            assert resp.status_code == 200
            assert resp.json["enabled"] is False
