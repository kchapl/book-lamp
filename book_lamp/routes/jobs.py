"""Background jobs and book import routes."""

import logging
from typing import Union

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from book_lamp.middleware.auth import authorisation_required
from book_lamp.middleware.csrf import csrf_protect
from book_lamp.services.job_queue import get_job_queue
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.pg_storage import PostgresStorage
from book_lamp.services.storage_factory import _mock_storage_singleton, is_test_mode
from book_lamp.utils.libib_import import parse_libib_csv

logger = logging.getLogger("book_lamp")
jobs_bp = Blueprint("jobs", __name__)


def _background_import_books(
    job_id: str, content: str, fetch_metadata: bool, user_id: int
):
    """Background task: import books from Libib CSV."""
    logger.info(f"Background job {job_id}: parsing CSV content...")

    try:
        storage: Union[MockStorage, PostgresStorage]
        if is_test_mode():
            storage = _mock_storage_singleton
        else:
            storage = PostgresStorage(user_id=user_id)

        items = parse_libib_csv(content)
        logger.info(f"Background job {job_id}: parsed {len(items)} items from CSV")

        enhanced_count = 0
        if fetch_metadata and items:
            from book_lamp.services.book_lookup import enhance_books_batch

            logger.info(
                f"Background job {job_id}: enhancing {len(items)} items with metadata..."
            )
            books = [item["book"] for item in items]
            enhanced_count = enhance_books_batch(books)

        import_count = storage.bulk_import(items)
        msg = f"Successfully imported {import_count} entries"
        if enhanced_count > 0:
            msg += f" and found missing data/covers for {enhanced_count} books"
        logger.info(f"Background job {job_id}: completed - {msg}")
        return msg
    except Exception:
        logger.exception(f"Background job {job_id} failed")
        raise


@jobs_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Get the status of a background job."""
    job_queue = get_job_queue()
    job = job_queue.get_job(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(job.to_dict())


@jobs_bp.route("/books/import", methods=["POST"])
@authorisation_required
@csrf_protect
def import_books():
    """Queue background job to import books from Libib CSV."""
    job_queue = get_job_queue()

    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Please upload a valid CSV file."}), 400

    try:
        content = file.read().decode("utf-8")
        fetch_metadata = (
            request.form.get("fetch_metadata") in ["on", "true", "1"]
        )

        user_id = session.get("user_id") or 1
        job_id = job_queue.submit_job(
            "import_books",
            _background_import_books,
            content,
            fetch_metadata,
            user_id,
        )

        # Support both JSON clients (React SPA) and browser redirects
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({"job_id": job_id}), 202
        return redirect(url_for("spa.spa_page", fallback="books", job_id=job_id))
    except Exception:
        current_app.logger.exception("Failed to queue import job")
        return jsonify({"error": "Error starting import."}), 500
