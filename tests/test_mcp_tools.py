"""Tests for the read-only MCP server.

Two layers, because they fail in different ways. The tool tests drive the real
tools in-process against MockStorage, with only the token check replaced: a fake
verifier can only ever test its own stub, so the parts of the auth boundary that
are actually ours are asserted over HTTP instead — the discovery document, a
tokenless call, and the sign-in finally leaving for Google.
"""

import asyncio
import base64
import hashlib
import json
import os
import re
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

pytest.importorskip("fastmcp")

from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from key_value.aio.stores.memory import MemoryStore  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from book_lamp import mcp_server  # noqa: E402
from book_lamp.services.storage_factory import _mock_storage_singleton as storage  # noqa: E402

READER = "reader@example.com"
BASE_URL = "https://book-lamp-mcp.example.com"
REDIRECT_URI = "https://vertexaisearch.cloud.google.com/oauth-redirect"
SCOPE = "openid https://www.googleapis.com/auth/userinfo.email"


def _seed() -> dict[str, dict]:
    """Three Books and three Readings, as the reader would have them."""
    hail_mary = storage.add_book(isbn13="9780593135204", title="Project Hail Mary", authors=["Andy Weir"])
    storage.add_reading(hail_mary["id"], "Completed", "2026-09-01", "2026-10-11", rating=4)

    prince = storage.add_book(isbn13="9780156012195", title="The Little Prince", authors=["Antoine de Saint-Exupéry"])
    # A rating belongs to a Completed Reading, so the abandoned one has none.
    storage.add_reading(prince["id"], "Abandoned", "2025-02-01", "2025-02-14")

    dune = storage.add_book(isbn13="9780441013593", title="Dune", authors=["Frank Herbert"])
    storage.add_reading(dune["id"], "In Progress", "2026-10-01", rating=0)

    return {"hail_mary": hail_mary, "prince": prince, "dune": dune}


@pytest.fixture
def verified(monkeypatch):
    """A verified Google token for the configured reader, without Google."""
    monkeypatch.setattr(mcp_server, "verified_reader_email", lambda: READER)


def _call(name: str, arguments: dict | None = None):
    """Call a tool in-process, the way an MCP client would."""
    server = mcp_server.build_server()

    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments or {})

    return asyncio.run(run())


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------


def test_search_finds_a_book_by_title_and_offers_its_isbn(verified) -> None:
    _seed()

    found = _call("search_books", {"query": "hail mary"}).data

    assert [book["title"] for book in found] == ["Project Hail Mary"]
    assert found[0]["isbn13"] == "9780593135204"


def test_search_and_get_book_carry_a_stored_subtitle(verified) -> None:
    """A migrated name is title plus subtitle, and both reach the client."""
    storage.add_book(isbn13="9781635575637", title="Piranesi", subtitle="A Novel", authors=["Susanna Clarke"])

    found = _call("search_books", {"query": "piranesi"}).data
    assert found[0]["subtitle"] == "A Novel"

    book = _call("get_book", {"identifier": "9781635575637"}).data
    assert book["subtitle"] == "A Novel"


def test_search_answers_nothing_for_a_title_the_collection_does_not_have(verified) -> None:
    _seed()

    assert _call("search_books", {"query": "The Silmarillion"}).data == []


def test_search_tolerates_a_typo_in_a_title(verified) -> None:
    """The tool's tolerance comes from the shared search, so prove it here too."""
    _seed()

    found = _call("search_books", {"query": "hail mairy"}).data

    assert [book["title"] for book in found] == ["Project Hail Mary"]


def test_get_book_by_isbn_returns_its_readings_newest_first(verified) -> None:
    seed = _seed()
    storage.add_reading(seed["hail_mary"]["id"], "In Progress", "2026-01-05")

    book = _call("get_book", {"identifier": "9780593135204"}).data

    assert book["title"] == "Project Hail Mary"
    assert [reading["start_date"] for reading in book["readings"]] == ["2026-09-01", "2026-01-05"]
    assert book["readings"][0]["end_date"] == "2026-10-11"
    assert book["readings"][0]["rating"] == 4


def test_get_book_accepts_a_title_when_exactly_one_book_matches(verified) -> None:
    _seed()

    book = _call("get_book", {"identifier": "dune"}).data

    assert book["isbn13"] == "9780441013593"
    assert [reading["status"] for reading in book["readings"]] == ["In Progress"]


def test_get_book_refuses_a_title_that_matches_several_books(verified) -> None:
    storage.add_book(isbn13="9780000000001", title="Dune Messiah", authors=["Frank Herbert"])
    _seed()

    with pytest.raises(ToolError) as refusal:
        _call("get_book", {"identifier": "dune"})

    # The refusal has to hand back what the caller needs to disambiguate.
    assert "9780441013593" in str(refusal.value)
    assert "9780000000001" in str(refusal.value)


def test_get_book_refuses_a_title_the_collection_does_not_have(verified) -> None:
    _seed()

    with pytest.raises(ToolError, match="no Book in Book Lamp matches"):
        _call("get_book", {"identifier": "The Silmarillion"})


def test_the_reading_log_is_newest_first(verified) -> None:
    """Newest first by the date the Reading ended, or started when it is open.

    So a Reading finished in October outranks one still open that began in the
    same month — the log's own ordering, which the page shares.
    """
    _seed()

    log = _call("get_reading_log").data

    assert [entry["book_title"] for entry in log] == [
        "Project Hail Mary",
        "Dune",
        "The Little Prince",
    ]


def test_the_reading_log_filters_the_way_the_page_does(verified) -> None:
    _seed()

    by_status = _call("get_reading_log", {"status": "Abandoned"}).data
    assert [entry["book_title"] for entry in by_status] == ["The Little Prince"]

    by_rating = _call("get_reading_log", {"min_rating": 4}).data
    assert [entry["book_title"] for entry in by_rating] == ["Project Hail Mary"]

    by_year = _call("get_reading_log", {"year": 2025}).data
    assert [entry["book_title"] for entry in by_year] == ["The Little Prince"]

    # An open Reading has no end date, so it is filed under the year it started.
    open_reading_year = _call("get_reading_log", {"year": 2026}).data
    assert [entry["book_title"] for entry in open_reading_year] == [
        "Project Hail Mary",
        "Dune",
    ]


def test_a_tool_call_without_a_verified_token_is_refused() -> None:
    """Whatever is in the collection stays out of reach without a token."""
    _seed()

    with pytest.raises(ToolError, match="no verified token"):
        _call("get_reading_log")


# ---------------------------------------------------------------------------
# The reader the token names
# ---------------------------------------------------------------------------


def _token_claiming(email: str) -> SimpleNamespace:
    return SimpleNamespace(claims={"email": email})


def test_the_configured_address_is_accepted(monkeypatch) -> None:
    monkeypatch.setenv(mcp_server.READER_EMAIL_ENV, READER)
    monkeypatch.setattr(mcp_server, "get_access_token", lambda: _token_claiming(READER.upper()))

    assert mcp_server.verified_reader_email() == READER


def test_a_different_address_is_refused(monkeypatch) -> None:
    monkeypatch.setenv(mcp_server.READER_EMAIL_ENV, READER)
    monkeypatch.setattr(mcp_server, "get_access_token", lambda: _token_claiming("somebody@else.example"))

    with pytest.raises(mcp_server.NotTheReader):
        mcp_server.verified_reader_email()


def test_a_token_with_no_address_is_refused(monkeypatch) -> None:
    monkeypatch.setenv(mcp_server.READER_EMAIL_ENV, READER)
    monkeypatch.setattr(mcp_server, "get_access_token", lambda: SimpleNamespace(claims={}))

    with pytest.raises(mcp_server.NotTheReader):
        mcp_server.verified_reader_email()


def _all_settings(monkeypatch) -> None:
    """Every setting the server starts from, with placeholder credentials."""
    for name, value in {
        mcp_server.READER_EMAIL_ENV: READER,
        mcp_server.CLIENT_ID_ENV: "123.apps.googleusercontent.com",
        mcp_server.CLIENT_SECRET_ENV: "GOCSPX-not-a-real-secret",
        mcp_server.BASE_URL_ENV: BASE_URL,
        mcp_server.DATABASE_URL_ENV: "postgresql://book-lamp.invalid/book-lamp",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize(
    "missing",
    [
        mcp_server.READER_EMAIL_ENV,
        mcp_server.CLIENT_ID_ENV,
        mcp_server.CLIENT_SECRET_ENV,
        mcp_server.BASE_URL_ENV,
        mcp_server.DATABASE_URL_ENV,
    ],
)
def test_a_missing_setting_stops_the_server_rather_than_defaulting(monkeypatch, missing: str) -> None:
    """There is no unauthenticated mode to fall back into, so this cannot be soft."""
    _all_settings(monkeypatch)
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(RuntimeError, match=missing):
        mcp_server._required(missing)


def test_starting_refuses_without_the_reader_email(monkeypatch) -> None:
    """The address is checked before the port opens, not on the first tool call.

    Read only when a tool ran, a deploy missing it would bind, answer its health
    check and refuse every call afterwards — a service that looks like a working
    one, which is the one thing this server must never be (ADR-0004).
    """
    _all_settings(monkeypatch)
    monkeypatch.delenv(mcp_server.READER_EMAIL_ENV, raising=False)

    def served_anyway(*args, **kwargs):
        raise AssertionError("served a request without a reader to read as")

    monkeypatch.setattr(mcp_server.FastMCP, "run", served_anyway)

    with pytest.raises(RuntimeError, match=mcp_server.READER_EMAIL_ENV):
        mcp_server.main()


def test_starting_serves_once_every_setting_is_present(monkeypatch) -> None:
    """The guard refuses a missing setting, not a complete one."""
    _all_settings(monkeypatch)
    monkeypatch.setenv("PORT", "8123")

    served: dict = {}
    monkeypatch.setattr(mcp_server.FastMCP, "run", lambda self, **kwargs: served.update(kwargs))

    mcp_server.main()

    # Render hands the port in PORT; hard-coding one would leave the service unable
    # to answer on the port it is probed on.
    assert served == {"transport": "http", "host": "0.0.0.0", "port": 8123}


def test_a_libpq_only_url_parameter_is_removed_for_asyncpg() -> None:
    """Neon's shared URL may carry options libpq knows and asyncpg does not."""
    url = "postgresql://reader:secret@db.example.com/book-lamp?sslmode=require&channel_binding=require"

    assert mcp_server.asyncpg_dsn(url) == (
        "postgresql://reader:secret@db.example.com/book-lamp?sslmode=require"
    )


def test_the_store_pool_is_small_and_has_no_statement_cache(monkeypatch) -> None:
    """PgBouncer transaction pooling cannot keep asyncpg's prepared statements."""
    captured: dict = {}

    async def fake_create_pool(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(mcp_server.asyncpg, "create_pool", fake_create_pool)
    store = mcp_server.BookLampOAuthStore(url="postgresql://db.example.com/book-lamp?channel_binding=require")

    asyncio.run(store._create_pool())

    assert captured["url"] == "postgresql://db.example.com/book-lamp"
    assert captured["min_size"] == 1
    assert captured["max_size"] == 2
    assert captured["statement_cache_size"] == 0


def test_startup_fails_when_the_oauth_store_cannot_be_set_up() -> None:
    """An unreachable database must stop the service before it serves anything."""

    class UnreachableStore:
        async def setup(self) -> None:
            raise ConnectionError("database unreachable")

    lifespan = mcp_server.oauth_state_lifespan(UnreachableStore())

    async def start() -> None:
        async with lifespan(None):
            raise AssertionError("served with an unreachable OAuth store")

    with pytest.raises(ConnectionError, match="database unreachable"):
        asyncio.run(start())


# ---------------------------------------------------------------------------
# The auth boundary, over HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def google_app(monkeypatch):
    """The server as the Google proxy configures it, with placeholder credentials."""
    monkeypatch.setenv(mcp_server.CLIENT_ID_ENV, "123.apps.googleusercontent.com")
    monkeypatch.setenv(mcp_server.CLIENT_SECRET_ENV, "GOCSPX-not-a-real-secret")
    monkeypatch.setenv(mcp_server.BASE_URL_ENV, BASE_URL)

    return _server_with(MemoryStore())


def test_the_mcp_endpoint_refuses_a_tokenless_call(google_app) -> None:
    with TestClient(google_app) as client:
        response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response.status_code == 401
    # The refusal has to say where to get a token, or a client cannot recover.
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_discovery_points_clients_at_this_server(google_app) -> None:
    with TestClient(google_app) as client:
        response = client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 200
    document = response.json()
    assert document["resource"] == f"{BASE_URL}/mcp"
    assert document["authorization_servers"] == [f"{BASE_URL}/"]
    assert SCOPE.split()[1] in document["scopes_supported"]


def _server_with(store):
    """A server whose OAuth state lives in this store, set up by its lifespan."""
    return mcp_server.build_server(
        auth=mcp_server.auth_provider(client_storage=store),
        lifespan=mcp_server.oauth_state_lifespan(store),
    ).http_app()


def _register(client: TestClient) -> str:
    """Register a client the way an MCP client does, and return its id."""
    response = client.post("/register", json={"client_name": "Gemini", "redirect_uris": [REDIRECT_URI]})
    assert response.status_code < 400, response.text
    client_id: str = response.json()["client_id"]
    return client_id


def _authorize(client: TestClient, client_id: str) -> str:
    """Start the flow and return the location of this server's consent page."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")

    response = client.get(
        "/authorize",
        params={
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "state": "state",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302, response.text
    return response.headers["location"]


def test_a_registration_survives_rebuilding_the_server(monkeypatch) -> None:
    """A deploy rebuilds the server; the client Gemini registered must still work.

    This is the failure from issue #389: the OAuth routes accepted a client ID
    into an ephemeral store, the next instance did not know it, and Gemini was
    sent to the "Client Not Registered" page.
    """
    _all_settings(monkeypatch)
    store = MemoryStore()

    with TestClient(_server_with(store)) as first:
        client_id = _register(first)

    with TestClient(_server_with(store)) as second:
        consent_url = _authorize(second, client_id)

    assert consent_url.startswith(f"{BASE_URL}/")


def test_oauth_state_is_encrypted_with_the_client_secret() -> None:
    """The same secret reopens the store; a different one cannot read the value."""
    underlying = MemoryStore()
    first = mcp_server.encrypted_client_storage(underlying, "GOCSPX-secret-one")
    value = {"upstream_token": "plaintext-token"}
    asyncio.run(first.put("reader", value, collection="mcp-upstream-tokens"))

    stored = asyncio.run(underlying.get("reader", collection="mcp-upstream-tokens"))
    assert stored is not None
    assert "plaintext-token" not in json.dumps(stored)

    same_secret = mcp_server.encrypted_client_storage(underlying, "GOCSPX-secret-one")
    assert asyncio.run(same_secret.get("reader", collection="mcp-upstream-tokens")) == value

    different_secret = mcp_server.encrypted_client_storage(underlying, "GOCSPX-secret-two")
    assert asyncio.run(different_secret.get("reader", collection="mcp-upstream-tokens")) is None


def test_consenting_hands_the_reader_to_google(google_app) -> None:
    """The whole point of the proxy: Google authenticates, this server does not.

    It owns the OAuth routes so an MCP client can discover and register, and then
    forwards the actual sign-in to Google.
    """
    with TestClient(google_app) as client:
        consent_url = _authorize(client, _register(client))
        consent = client.get(consent_url)
        assert consent.status_code == 200

        csrf = re.search(r'name="csrf_token" value="([^"]+)"', consent.text)
        txn = re.search(r'name="txn_id" value="([^"]+)"', consent.text)
        # A consent page that omits either field would make the POST below a
        # silent no-op, so fail here where the reason is visible.
        assert csrf and txn, consent.text
        form = {
            "csrf_token": csrf.group(1),
            "txn_id": txn.group(1),
            "submit": "true",
            "action": "approve",
        }
        approved = client.post(consent_url, data=form, follow_redirects=False)

    assert approved.status_code == 302, approved.text
    # A missing host cannot match either branch; the empty default keeps both
    # the comparison and the suffix check total for the type checker.
    hostname = urlparse(approved.headers["location"]).hostname or ""
    assert hostname == "accounts.google.com" or hostname.endswith(".accounts.google.com")
