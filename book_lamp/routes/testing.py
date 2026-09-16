"""Test harness utility routes, enabled only when TEST_MODE=1."""

from flask import Blueprint, current_app, redirect, url_for

from book_lamp.services.storage_factory import get_storage, is_test_mode

testing_bp = Blueprint("testing", __name__)


@testing_bp.route("/test/reset", methods=["POST"])
def test_reset():
    """Reset test storage."""
    storage = get_storage()
    try:
        if hasattr(storage, "books"):
            storage.books = []
            storage.reading_records = []
            if hasattr(storage, "reading_list"):
                storage.reading_list = []
            storage.next_book_id = 1
            storage.next_record_id = 1
            if hasattr(storage, "set_authorised"):
                storage.set_authorised(False)
        return {"status": "ok"}
    except Exception as e:
        current_app.logger.exception("Failed to reset test storage: %s", e)
        return {"status": "error", "message": str(e)}, 500


@testing_bp.route("/test/connect")
def test_connect():
    """Authorise as a test user automatically."""
    if not is_test_mode():
        return "Not available", 404
    storage = get_storage()
    if hasattr(storage, "set_authorised"):
        storage.set_authorised(True)
    return redirect(url_for("spa.spa_index"))


@testing_bp.route("/test/disconnect")
def test_disconnect():
    """Disconnect as a test user automatically."""
    if not is_test_mode():
        return "Not available", 404
    storage = get_storage()
    if hasattr(storage, "set_authorised"):
        storage.set_authorised(False)
    return redirect(url_for("spa.spa_index"))
