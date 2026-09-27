"""WSGI application entry point and backward-compatible exports.

This module exposes the Flask application instance and re-exports common
utilities and services for backward compatibility with existing tests and scripts.
"""

import os

from book_lamp import APP_VERSION, create_app
from book_lamp.middleware.auth import authorisation_required
from book_lamp.middleware.csrf import add_csrf_token_header, csrf_protect, generate_csrf_token
from book_lamp.services.storage_factory import (
    TEST_ISBN,
    _mock_storage_singleton,
    get_llm_client,
    get_storage,
    is_test_mode,
)
from book_lamp.utils import (
    SORT_OPTIONS,
    is_valid_isbn13,
    parse_bisac_category,
    parse_publication_year,
    sort_books,
)
from book_lamp.utils.redirects import get_safe_redirect_target

app = create_app()

__all__ = [
    "app",
    "create_app",
    "get_storage",
    "is_test_mode",
    "TEST_ISBN",
    "_mock_storage_singleton",
    "get_llm_client",
    "authorisation_required",
    "csrf_protect",
    "generate_csrf_token",
    "add_csrf_token_header",
    "get_safe_redirect_target",
    "is_valid_isbn13",
    "parse_publication_year",
    "parse_bisac_category",
    "sort_books",
    "SORT_OPTIONS",
    "APP_VERSION",
]

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
