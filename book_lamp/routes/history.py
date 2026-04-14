from flask import Blueprint, flash, redirect, render_template, request, url_for

from book_lamp.web.common import (
    _get_safe_redirect_target,
    authorisation_required,
    get_storage,
)

history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
@authorisation_required
def reading_history():
    """Show detailed reading history as a chronological list of individual events."""
    storage = get_storage()
    storage.prefetch()
    from flask import session

    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

    history = storage.get_reading_history()
    all_statuses = sorted(
        list(set(r.get("status") for r in history if r.get("status")))
    )

    status_filter = request.args.get("status")
    if status_filter:
        history = [r for r in history if r.get("status") == status_filter]

    min_rating = request.args.get("min_rating")
    if min_rating and min_rating.isdigit():
        min_rating = int(min_rating)
        history = [r for r in history if r.get("rating", 0) >= min_rating]

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

    return render_template(
        "history.html",
        history=history,
        statuses=all_statuses,
        current_status=status_filter,
        current_rating=min_rating,
        current_year=year_filter,
        current_sort=sort_by,
    )


@history_bp.route(
    "/books/<int:book_id>/reading-records",
    methods=["POST"],
)
@authorisation_required
def create_reading_record(book_id: int):
    storage = get_storage()
    status = request.form.get("status")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    rating = int(request.form.get("rating", 0))

    if not status or not start_date:
        flash("Status and start date are required.", "error")
        return redirect(url_for("book_detail", book_id=book_id))

    try:
        storage.add_reading_record(
            book_id=book_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        flash("Reading record added.", "success")
    except Exception as e:
        flash(f"Error adding reading record: {str(e)}", "error")

    return redirect(url_for("book_detail", book_id=book_id))


@history_bp.route(
    "/reading-records/<int:record_id>/edit",
    methods=["POST"],
)
@authorisation_required
def update_reading_record(record_id: int):
    storage = get_storage()
    status = request.form.get("status")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    rating = int(request.form.get("rating", 0))

    if not status or not start_date:
        flash("Status and start date are required.", "error")
        safe_target = _get_safe_redirect_target(request.referrer)
        return redirect(safe_target or url_for("history.reading_history"))

    try:
        storage.update_reading_record(
            record_id=record_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        flash("Reading record updated.", "success")
    except Exception as e:
        flash(f"Error updating record: {str(e)}", "error")

    safe_target = _get_safe_redirect_target(request.referrer)
    return redirect(safe_target or url_for("history.reading_history"))


@history_bp.route(
    "/reading-records/<int:record_id>/delete",
    methods=["POST"],
)
@authorisation_required
def delete_reading_record(record_id: int):
    storage = get_storage()
    try:
        success = storage.delete_reading_record(record_id)
        if success:
            flash("Reading record deleted.", "success")
        else:
            flash("Reading record not found.", "error")
    except Exception as e:
        flash(f"Error deleting record: {str(e)}", "error")

    safe_target = _get_safe_redirect_target(request.referrer)
    return redirect(safe_target or url_for("history.reading_history"))
