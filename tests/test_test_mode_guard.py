"""TEST_MODE bypasses Google sign-in, so it must never run in production."""

import pytest

from book_lamp import create_app


def _test_mode_environment(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


def test_test_mode_is_refused_outside_development_or_ci(monkeypatch):
    _test_mode_environment(monkeypatch)

    with pytest.raises(RuntimeError, match="TEST_MODE"):
        create_app()


def test_test_mode_is_allowed_in_development(monkeypatch):
    _test_mode_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "development")

    assert create_app() is not None


def test_a_production_environment_refuses_test_mode_even_in_ci(monkeypatch):
    _test_mode_environment(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="TEST_MODE"):
        create_app()
