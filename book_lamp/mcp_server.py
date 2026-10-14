"""Read-only MCP server for Book Lamp.

Gemini's custom apps reach this over Streamable HTTP at `/mcp`. Authentication is
delegated to Google through FastMCP's OAuth proxy: Google has no Dynamic Client
Registration, so the proxy presents the interface MCP clients expect and forwards
the sign-in to Google (see ADR-0004).

The server reads as one configured reader — `BOOK_LAMP_USER_EMAIL` — and refuses
everybody else. Every tool is read-only, so the endpoint has no write path at all
and a mistake cannot damage the Reading Log.

Run it with `python -m book_lamp.mcp_server`, which needs the `mcp` extra.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token

from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.pg_storage import PostgresStorage
from book_lamp.services.storage_factory import _mock_storage_singleton, is_test_mode
from book_lamp.utils.books import normalize_isbn
from book_lamp.utils.readings import filter_reading_log, sort_reading_log

Storage = Union[MockStorage, PostgresStorage]

READER_EMAIL_ENV = "BOOK_LAMP_USER_EMAIL"
CLIENT_ID_ENV = "BOOK_LAMP_MCP_CLIENT_ID"
CLIENT_SECRET_ENV = "BOOK_LAMP_MCP_CLIENT_SECRET"
BASE_URL_ENV = "BOOK_LAMP_MCP_BASE_URL"

#: What the server asks Google for: who the reader is, and nothing else. Both are
#: non-sensitive scopes, so publishing the consent screen needs no verification.
READER_SCOPES = ("openid", "https://www.googleapis.com/auth/userinfo.email")

#: How many Books a search hands back. A model needs the right one near the top,
#: not every near-match.
SEARCH_LIMIT = 10

INSTRUCTIONS = (
    "Book Lamp is one reader's personal reading history. A Book is a work, "
    "identified by its ISBN. A Reading is one attempt at a Book: it begins and "
    "ends, and its Reading Status is 'In Progress', 'Completed' or 'Abandoned'. "
    "This server only reads; it cannot change anything."
)


class NotTheReader(PermissionError):
    """Raised when the caller is not the one reader this server serves."""


def _required(name: str) -> str:
    """Read a required environment variable, or explain what is missing."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} must be set. This server has no unauthenticated mode and no "
            "default reader, so it cannot start without it."
        )
    return value


def reader_email() -> str:
    """The one email this server reads as."""
    return _required(READER_EMAIL_ENV).lower()


def auth_provider() -> GoogleProvider:
    """Google as the authenticator, behind a proxy that speaks MCP's OAuth."""
    return GoogleProvider(
        client_id=_required(CLIENT_ID_ENV),
        client_secret=_required(CLIENT_SECRET_ENV),
        base_url=_required(BASE_URL_ENV),
        required_scopes=list(READER_SCOPES),
    )


def verified_reader_email() -> str:
    """The email on a verified Google token, or a refusal.

    Two things must hold: Google signed the token, and the address it carries is
    the one this server is configured for. Neither is assumed.
    """
    token = get_access_token()
    if token is None:
        raise NotTheReader("no verified token: this server answers over OAuth only")

    email = str(token.claims.get("email") or "").strip().lower()
    if not email or email != reader_email():
        raise NotTheReader(f"this server reads as {reader_email()} only")

    return email


def reader_storage() -> Storage:
    """Storage belonging to the reader the verified token names."""
    verified_reader_email()

    if is_test_mode():
        return _mock_storage_singleton

    user_id = PostgresStorage.find_user_id_by_email(reader_email())
    if user_id is None:
        raise NotTheReader(f"{reader_email()} is not a Book Lamp reader yet; sign in to the app once")
    return PostgresStorage(user_id=user_id)


def _looks_like_an_isbn(identifier: str) -> bool:
    """Whether the identifier is shaped like an ISBN rather than a title."""
    return len(normalize_isbn(identifier)) in (10, 13)


def _book_summary(book: Dict[str, Any]) -> Dict[str, Any]:
    """A Book reduced to what picks it out of a list."""
    return {
        "isbn13": book.get("isbn13", ""),
        "title": book.get("title", ""),
        "author": book.get("author", ""),
        "publication_year": book.get("publication_year"),
        "series": book.get("series"),
    }


def _reading_fields(reading: Dict[str, Any]) -> Dict[str, Any]:
    """A Reading's own fields, without the Book it belongs to."""
    return {
        "status": reading.get("status"),
        "start_date": reading.get("start_date"),
        "end_date": reading.get("end_date"),
        "rating": reading.get("rating") or 0,
    }


def build_server(auth: Optional[Any] = None) -> FastMCP:
    """The server and its three tools.

    ``auth`` is passed in rather than read from the environment so a test can
    build the server without Google credentials; only :func:`main` reads them.
    """
    server = FastMCP(name="Book Lamp", instructions=INSTRUCTIONS, auth=auth)

    @server.tool
    def search_books(query: str) -> List[Dict[str, Any]]:
        """Find Books in the collection by title, author, ISBN, series or category.

        Use this first when you have a title rather than an ISBN: it returns the
        closest matches and each one's ISBN, which `get_book` takes.
        """
        matches = reader_storage().search(query)
        return [_book_summary(book) for book in matches[:SEARCH_LIMIT]]

    @server.tool
    def get_book(identifier: str) -> Dict[str, Any]:
        """One Book and every Reading of it, newest first.

        Pass an ISBN (`9780593135204`), or a title when you do not have one. A
        title has to name exactly one Book; if several Books match, pick the
        right ISBN from `search_books` and pass that instead.
        """
        storage = reader_storage()

        book = storage.get_book_by_isbn(identifier) if _looks_like_an_isbn(identifier) else None

        if book is None:
            matches = storage.search(identifier)
            if not matches:
                raise ValueError(f"no Book in Book Lamp matches {identifier!r}")
            if len(matches) > 1:
                titles = ", ".join(f"{m.get('title')} ({m.get('isbn13')})" for m in matches[:SEARCH_LIMIT])
                raise ValueError(f"{identifier!r} matches {len(matches)} Books: {titles}")
            book = matches[0]

        readings = sorted(
            storage.get_readings(book_id=book["id"]),
            key=lambda reading: str(reading.get("start_date") or ""),
            reverse=True,
        )

        return {
            **_book_summary(book),
            "category": book.get("bisac_category"),
            "page_count": book.get("page_count"),
            "readings": [{"id": reading.get("id"), **_reading_fields(reading)} for reading in readings],
        }

    @server.tool
    def get_reading_log(
        status: Optional[str] = None,
        min_rating: Optional[int] = None,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """The reader's Readings, newest first — what they have started, finished or given up.

        Args:
            status: keep only this Reading Status: 'In Progress', 'Completed' or
                'Abandoned'.
            min_rating: keep only Readings rated at least this, on a 1–5 scale.
            year: keep only Readings that ended in this year — or, for one still
                open, that started in it.
        """
        log = filter_reading_log(
            reader_storage().get_reading_history(),
            status=status,
            min_rating=min_rating,
            year=None if year is None else str(year),
        )

        return [
            {
                "book_title": reading.get("book_title"),
                "book_author": reading.get("book_author"),
                **_reading_fields(reading),
            }
            for reading in sort_reading_log(log)
        ]

    return server


def main() -> None:
    """Serve over Streamable HTTP, which is all Gemini's custom apps accept."""
    # Every setting is read before the port opens, the reader's address included.
    # Left to the tools, a deploy missing only that one would bind, pass its health
    # check and refuse every call — a service that looks like a working one.
    reader_email()
    server = build_server(auth=auth_provider())
    server.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
