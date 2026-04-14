import logging
import os
import re
from functools import wraps
from typing import Any, Union, cast
from urllib.parse import urlparse

from flask import current_app, g, redirect, request, session, url_for

from book_lamp.services.llm_client import LLMClient
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.sheets_storage import GoogleSheetsStorage

# Global singleton for test mode only.
_mock_storage_singleton = MockStorage()


def get_test_storage_singleton() -> MockStorage:
    return _mock_storage_singleton


def is_test_mode() -> bool:
    """Return True when the application is running under the test harness."""
    return os.environ.get("TEST_MODE", "0") == "1"


def get_storage():
    """Get the appropriate storage backend for the current request context."""
    if is_test_mode():
        return _mock_storage_singleton
    if "storage" not in g:
        current_app.logger.info("Initializing storage for request...")
        is_prod = os.environ.get("FLASK_ENV") == "production"
        sheet_name = "BookLampData" if is_prod else "DevBookLampData"
        credentials = session.get("credentials")
        spreadsheet_id = session.get("spreadsheet_id")
        g.storage = GoogleSheetsStorage(
            sheet_name=sheet_name,
            credentials_dict=credentials,
            spreadsheet_id=spreadsheet_id,
        )
    return g.storage


def get_llm_client() -> LLMClient:
    """Return a per-request LLMClient singleton (cheap to construct)."""
    if "llm_client" not in g:
        g.llm_client = LLMClient()
    return cast(LLMClient, g.llm_client)


def authorisation_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.info(f"AUTHORISATION_CHECK for route: {f.__name__}")
        if not get_storage().is_authorised():
            return redirect(url_for("unauthorised"))
        return f(*args, **kwargs)

    return decorated_function


def _normalize_publisher(name: str) -> str:
    if not name:
        return ""
    suffixes = [
        r"\bbooks\b",
        r"\blimited\b",
        r"\bltd\.?\b",
        r"\binc\.?\b",
        r"\bllc\b",
        r"\bpublishers?\b",
        r"\bpublishing\b",
        r"\bpress\b",
        r"\bgroup\b",
        r"\bcompany\b",
        r"\bco\.?\b",
    ]
    pattern = re.compile("|".join(suffixes), flags=re.IGNORECASE)
    cleaned = pattern.sub("", name)
    cleaned = re.sub(r"[,.;:]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return name.strip()
    return cleaned


def _get_safe_redirect_target(target: str | None) -> str | None:
    """
    Return a safe redirect target derived from user-controlled input.

    Only relative URLs (no scheme, no netloc) are allowed. Backslashes are
    stripped to avoid alternative path separators being interpreted by browsers.
    """
    if not target:
        return None
    cleaned = target.replace("\\", "")
    parsed = urlparse(cleaned)
    if parsed.scheme or parsed.netloc:
        return None
    return cleaned


def get_safe_redirect_target(fallback_endpoint: str) -> str:
    """
    Return a safe redirect target derived from the request referrer.

    If the referrer is an absolute URL, only accept it if it points to the
    same host as the current request. Otherwise, or if no referrer is set,
    fall back to the URL for the given endpoint.
    """
    referrer = request.referrer
    if referrer:
        normalized = referrer.replace("\\", "/")
        parsed = urlparse(normalized)
        if not parsed.scheme and not parsed.netloc:
            return normalized
        if parsed.scheme in ("http", "https") and parsed.netloc == request.host:
            return normalized
    return url_for(fallback_endpoint)


def _background_fetch_missing_data(job_id: str, credentials_dict, sheet_name: str):
    """Background task: bulk fetch missing data (covers, metadata) for all books."""
    from book_lamp.services.book_lookup import enhance_books_batch

    logger = logging.getLogger(__name__)
    try:
        storage: Union[MockStorage, GoogleSheetsStorage]
        if is_test_mode():
            storage = _mock_storage_singleton
        else:
            storage = GoogleSheetsStorage(
                sheet_name=sheet_name, credentials_dict=credentials_dict
            )

        books = storage.get_all_books()
        logger.info(
            "Background job %s: checking %s books for missing data...",
            job_id,
            len(books),
        )
        updated_count = enhance_books_batch(books, force_refresh=True)
        items_to_update: list[dict[str, Any]] = [
            {"book": b, "record": None} for b in books
        ]
        storage.bulk_import(items_to_update)

        result_msg = (
            f"Found and updated missing data for {updated_count} book(s)."
            if updated_count > 0
            else "No missing data found to update."
        )
        logger.info("Background job %s: completed - %s", job_id, result_msg)
        return result_msg
    except Exception:
        logger.exception("Background job %s failed", job_id)
        raise
