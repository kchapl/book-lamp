"""The version the About page reports for the running deployment."""

from book_lamp.routes.app_info import VERSION_ENV_VARS


def clear_version_env(monkeypatch):
    for env_var in VERSION_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_reports_the_short_commit_the_host_deployed(client, monkeypatch):
    clear_version_env(monkeypatch)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "0123456789abcdef")

    response = client.get("/api/app-info")

    assert response.status_code == 200
    assert response.json == {"version": "0123456"}


def test_falls_back_to_the_configured_version_when_the_host_names_no_commit(client, monkeypatch):
    clear_version_env(monkeypatch)
    monkeypatch.setenv("APP_VERSION", "1.2.3")

    assert client.get("/api/app-info").json == {"version": "1.2.3"}


def test_a_local_run_has_no_commit_to_report(client, monkeypatch):
    clear_version_env(monkeypatch)
    monkeypatch.delenv("APP_VERSION", raising=False)

    assert client.get("/api/app-info").json == {"version": "dev"}


def test_an_anonymous_visitor_can_read_it(client):
    assert client.get("/api/app-info").status_code == 200
