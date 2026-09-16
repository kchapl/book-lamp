"""Tests for SPA shell serving and client-side routing fallback."""

import os
from pathlib import Path

import pytest

REACT_DIR = Path(__file__).resolve().parents[1] / "book_lamp" / "static" / "react"
SHELL_PATH = REACT_DIR / "index.html"
MISSING_SHELL_MESSAGE = b"SPA build missing"


@pytest.fixture
def restore_shell():
    """Allow a test to hide the built SPA shell and restore it afterwards."""
    yield
    backup = SHELL_PATH.with_suffix(".html.bak")
    if backup.exists():
        backup.replace(SHELL_PATH)


def test_root_serves_react_shell(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'id="root"' in resp.data


@pytest.mark.parametrize(
    "path",
    ["/books", "/history", "/dashboard", "/author/some-author", "/unauthorised", "/definitely-missing"],
)
def test_client_routes_all_serve_shell(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert b'id="root"' in resp.data


def test_unknown_api_route_returns_json_404(client):
    resp = client.get("/api/definitely-missing")
    assert resp.status_code == 404
    assert resp.json == {"error": "Not found"}


def test_missing_shell_returns_503(client, restore_shell):
    SHELL_PATH.replace(SHELL_PATH.with_suffix(".html.bak"))
    try:
        resp = client.get("/")
        assert resp.status_code == 503
        assert MISSING_SHELL_MESSAGE in resp.data
    finally:
        backup = SHELL_PATH.with_suffix(".html.bak")
        if backup.exists():
            backup.replace(SHELL_PATH)


def test_built_shell_exists():
    """The repository ships a built SPA shell so the app works without a Node build step."""
    assert SHELL_PATH.exists()
