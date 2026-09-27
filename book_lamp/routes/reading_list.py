"""Reading list queue management routes."""

from flask import Blueprint, jsonify, request

from book_lamp.middleware.auth import authorisation_required
from book_lamp.middleware.csrf import csrf_protect
from book_lamp.services.storage_factory import get_storage

reading_list_bp = Blueprint("reading_list", __name__)


@reading_list_bp.route("/api/reading-list", methods=["GET"])
@authorisation_required
def api_get_reading_list():
    """API endpoint to get reading list."""
    storage = get_storage()
    rl_items = storage.get_reading_list()
    books = []
    for item in rl_items:
        book = {
            "id": item["book_id"],
            "title": item["title"],
            "author": item["author"],
            "thumbnail_url": item.get("thumbnail_url"),
        }
        books.append(book)
    return jsonify({"books": books})


@reading_list_bp.route("/api/reading-list/reorder", methods=["POST"])
@authorisation_required
@csrf_protect
def api_reorder_reading_list():
    """Reorder the reading list from a JSON payload."""
    storage = get_storage()
    data = request.get_json(silent=True) or {}
    book_ids = data.get("book_ids", [])
    storage.update_reading_list_order(book_ids)
    return jsonify({"success": True})


@reading_list_bp.route("/api/reading-list/remove/<int:book_id>", methods=["POST"])
@authorisation_required
@csrf_protect
def api_remove_from_reading_list(book_id: int):
    """Remove a book from the reading list and return JSON."""
    storage = get_storage()
    storage.remove_from_reading_list(book_id)
    return jsonify({"success": True})
