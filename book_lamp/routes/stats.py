"""Statistics, reading history, and user settings routes."""

from flask import Blueprint, jsonify, redirect, request, session, url_for

from book_lamp.middleware.auth import authorisation_required
from book_lamp.middleware.csrf import csrf_protect
from book_lamp.routes.books import _background_fetch_missing_data
from book_lamp.services.job_queue import get_job_queue
from book_lamp.services.stats_calculator import calculate_collection_stats
from book_lamp.services.storage_factory import get_storage

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/history", methods=["GET"])
@authorisation_required
def api_reading_history():
    """API endpoint for reading history data."""
    storage = get_storage()

    history = storage.get_reading_history()
    all_statuses = sorted(
        list(set(r.get("status") for r in history if r.get("status")))
    )

    status_filter = request.args.get("status")
    if status_filter:
        history = [r for r in history if r.get("status") == status_filter]

    min_rating = request.args.get("min_rating")
    if min_rating and min_rating.isdigit():
        min_rating_val = int(min_rating)
        history = [r for r in history if r.get("rating", 0) >= min_rating_val]
    else:
        min_rating_val = None

    year_filter = request.args.get("year")
    if year_filter and year_filter.isdigit():
        history = [
            r
            for r in history
            if (r.get("end_date") and r.get("end_date")[:4] == year_filter)
            or (
                not r.get("end_date")
                and r.get("start_date")
                and r.get("start_date")[:4] == year_filter
            )
        ]

    sort_by = request.args.get("sort", "date_desc")

    if sort_by == "date_desc":
        history.sort(
            key=lambda r: r.get("end_date") or r.get("start_date") or "", reverse=True
        )
    elif sort_by == "date_asc":
        history.sort(key=lambda r: r.get("end_date") or r.get("start_date") or "")
    elif sort_by == "rating_desc":
        history.sort(key=lambda r: r.get("rating", 0), reverse=True)
    elif sort_by == "title":
        history.sort(key=lambda r: (r.get("book_title") or "").lower())

    return jsonify(
        {
            "history": history,
            "statuses": all_statuses,
            "filters": {
                "status": status_filter,
                "rating": min_rating_val,
                "year": year_filter,
                "sort": sort_by,
            },
        }
    )


@stats_bp.route("/api/stats", methods=["GET"])
def redirect_api_stats():
    """Redirect legacy /api/stats route to /api/dashboard."""
    return redirect(url_for("stats.api_collection_stats"), code=301)


@stats_bp.route("/api/dashboard", methods=["GET"])
@authorisation_required
def api_collection_stats():
    """API endpoint for collection statistics."""
    storage = get_storage()
    books = storage.get_all_books()
    all_records = storage.get_reading_records()
    settings = storage.get_settings() if hasattr(storage, "get_settings") else None

    stats_data = calculate_collection_stats(books, all_records, settings=settings)
    return jsonify(stats_data)


@stats_bp.route("/stats/backfill-categories", methods=["GET"])
@authorisation_required
def fetch_missing_categories():
    """Trigger backfill of BISAC categories from the stats page."""
    job_queue = get_job_queue()
    job_id = job_queue.submit_job(
        "backfill_bisac",
        _background_fetch_missing_data,
        session["user_id"],
    )
    return redirect(url_for("spa.spa_page", fallback="dashboard", job_id=job_id))


@stats_bp.route("/api/settings", methods=["POST"])
@authorisation_required
@csrf_protect
def update_settings():
    """Update user settings."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    storage = get_storage()
    for key, value in data.items():
        if key == "theme" and value not in ["light", "dark", "system"]:
            continue
        storage.update_setting(key, str(value))

    return jsonify({"success": True})


@stats_bp.route("/api/sync/diagnostics", methods=["GET"])
@authorisation_required
def sync_diagnostics():
    """Return storage connectivity diagnostics."""
    storage = get_storage()
    is_healthy = storage.health_check() if hasattr(storage, "health_check") else True
    return jsonify({
        "status": "ok" if is_healthy else "error",
        "storage": "postgres",
    })
