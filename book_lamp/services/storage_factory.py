"""Storage factory and request context dependency injection."""

import os
from typing import Union, cast

from flask import current_app, g, session

from book_lamp.services.llm_client import LLMClient
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.pg_storage import PostgresStorage

TEST_ISBN = "9780000000000"

# Global singleton for test mode only
_mock_storage_singleton = MockStorage()


def is_test_mode() -> bool:
    """Return True when the application is running under the test harness."""
    return os.environ.get("TEST_MODE", "0") == "1"


def get_storage() -> Union[MockStorage, PostgresStorage]:
    """Get the appropriate storage backend for the current request context."""
    if is_test_mode():
        # Authorise storage for automated testing
        _mock_storage_singleton.set_authorised(True)
        return _mock_storage_singleton

    user_id = session.get("user_id")
    if user_id:
        return PostgresStorage(user_id=user_id)

    # Authentication is required - return storage that fails authorisation checks
    unauthed = MockStorage()
    unauthed.set_authorised(False)
    current_app.logger.warning("Unauthenticated access attempted - no bypass allowed")
    return unauthed


def get_llm_client() -> LLMClient:
    """Return a per-request LLMClient singleton (cheap to construct)."""
    if "llm_client" not in g:
        g.llm_client = LLMClient()
    return cast(LLMClient, g.llm_client)
