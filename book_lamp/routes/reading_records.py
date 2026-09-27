"""Reading records management routes."""

from flask import Blueprint, current_app, jsonify, request

from book_lamp.middleware.auth import authorisation_required
from book_lamp.middleware.csrf import csrf_protect
from book_lamp.services.storage_factory import get_storage

reading_records_bp = Blueprint("reading_records", __name__)


@reading_records_bp.route("/api/books/<int:book_id>/reading-records", methods=["POST"])
@authorisation_required
@csrf_protect
def api_create_reading_record(book_id: int):
    """Create a reading record for a book from a JSON payload."""
    storage = get_storage()
    data = request.get_json(silent=True) or {}

    status = str(data.get("status", "") or "").strip()
    start_date = str(data.get("start_date", "") or "").strip()
    end_date = str(data.get("end_date", "") or "").strip() or None
    rating_raw = data.get("rating", 0)
    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        rating = 0

    if not status or not start_date:
        return jsonify({"error": "status and start_date are required"}), 400

    try:
        record = storage.add_reading_record(
            book_id=book_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        current_app.logger.info(f"RECORD_CREATED (API): book_id={book_id}, status='{status}'")
        return jsonify(record), 201
    except Exception:
        current_app.logger.exception(f"api_create_reading_record: failed for book_id={book_id}")
        return jsonify({"error": "Failed to create reading record"}), 500


@reading_records_bp.route("/api/reading-records/<int:record_id>/edit", methods=["POST"])
@authorisation_required
@csrf_protect
def api_update_reading_record(record_id: int):
    """Update a reading record from a JSON payload."""
    storage = get_storage()
    data = request.get_json(silent=True) or {}

    status = str(data.get("status", "") or "").strip()
    start_date = str(data.get("start_date", "") or "").strip()
    end_date = str(data.get("end_date", "") or "").strip() or None
    rating_raw = data.get("rating", 0)
    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        rating = 0

    if not status or not start_date:
        return jsonify({"error": "status and start_date are required"}), 400

    try:
        storage.update_reading_record(
            record_id=record_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        current_app.logger.info(
            f"RECORD_UPDATED (API): record_id={record_id}, status='{status}'"
        )
        return jsonify({"success": True})
    except Exception:
        current_app.logger.exception(
            f"api_update_reading_record: failed for record_id={record_id}"
        )
        return jsonify({"error": "Failed to update reading record"}), 500


@reading_records_bp.route("/api/reading-records/<int:record_id>/delete", methods=["POST"])
@authorisation_required
@csrf_protect
def api_delete_reading_record(record_id: int):
    """Delete a reading record by ID."""
    storage = get_storage()
    try:
        success = storage.delete_reading_record(record_id)
        if not success:
            return jsonify({"error": "Reading record not found"}), 404
        current_app.logger.info(f"RECORD_DELETED (API): record_id={record_id}")
        return jsonify({"success": True})
    except Exception as exc:
        current_app.logger.error(
            f"api_delete_reading_record: failed for record_id={record_id}: {exc}",
            exc_info=True,
        )
        return jsonify({"error": "Failed to delete reading record"}), 500


@reading_records_bp.route("/api/books/<int:book_id>/start-reading", methods=["POST"])
@authorisation_required
@csrf_protect
def api_start_reading(book_id: int):
    """Move a book from the reading list to the reading log."""
    storage = get_storage()
    try:
        storage.start_reading(book_id)
        current_app.logger.info(
            f"START_READING (API): book_id={book_id}, new_status='In Progress'"
        )
        return jsonify({"success": True})
    except Exception:
        current_app.logger.exception(f"api_start_reading: failed for book_id={book_id}")
        return jsonify({"error": "Failed to start reading."}), 500


@reading_records_bp.route("/api/books/<int:book_id>/add-to-reading-list", methods=["POST"])
@authorisation_required
@csrf_protect
def api_add_to_reading_list(book_id: int):
    """Add an existing book to the reading list and return JSON."""
    storage = get_storage()
    try:
        storage.add_to_reading_list(book_id)
        current_app.logger.info(f"READING_LIST_ADD (API): book_id={book_id}")
        return jsonify({"success": True})
    except Exception:
        current_app.logger.exception(f"api_add_to_reading_list: failed for book_id={book_id}")
        return jsonify({"error": "Failed to add to reading list."}), 500
