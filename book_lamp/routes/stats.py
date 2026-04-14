import calendar
from collections import Counter

from flask import Blueprint, redirect, render_template, session, url_for

from book_lamp.services.job_queue import get_job_queue
from book_lamp.utils import parse_bisac_category
from book_lamp.web.common import (
    _background_fetch_missing_data,
    _normalize_publisher,
    authorisation_required,
    get_storage,
)

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats", methods=["GET"])
@authorisation_required
def collection_stats():
    storage = get_storage()
    storage.prefetch()
    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

    books = storage.get_all_books()
    all_records = storage.get_reading_records()
    latest_records = {}
    for r in all_records:
        bid = r.get("book_id")
        if bid:
            if bid not in latest_records or r.get("start_date", "") > latest_records[
                bid
            ].get("start_date", ""):
                latest_records[bid] = r

    completed_books = []
    for b in books:
        bid = b.get("id")
        if latest_records.get(bid, {}).get("status") == "Completed":
            completed_books.append(b)

    total_books = len(completed_books)
    total_records = len(all_records)

    valid_ratings = []
    for r in all_records:
        rating_val = r.get("rating")
        try:
            if rating_val and int(rating_val) > 0:
                valid_ratings.append(int(rating_val))
        except (ValueError, TypeError):
            continue
    avg_rating = sum(valid_ratings) / len(valid_ratings) if valid_ratings else 0.0

    allowed_statuses = {"In Progress", "Completed", "Abandoned"}
    statuses = []
    for b in books:
        bid = b.get("id")
        if bid in latest_records:
            status = latest_records[bid].get("status")
            if status in allowed_statuses:
                statuses.append(status)
    status_counts = Counter(statuses)

    rating_counts = Counter()
    for r in all_records:
        if r.get("status") == "Completed":
            try:
                r_val = int(r.get("rating", 0))
                if 1 <= r_val <= 5:
                    rating_counts[r_val] += 1
            except (ValueError, TypeError):
                continue
    rating_distribution = [(stars, rating_counts[stars]) for stars in range(5, 0, -1)]

    all_authors = []
    for b in completed_books:
        if b.get("authors"):
            all_authors.extend(b["authors"])
        elif b.get("author"):
            all_authors.append(b["author"])
    total_authors = len(set(all_authors))
    top_authors = sorted(Counter(all_authors).items(), key=lambda x: (-x[1], x[0]))[:5]

    all_publishers = []
    for b in completed_books:
        if b.get("publisher"):
            norm_pub = _normalize_publisher(b["publisher"])
            if norm_pub:
                all_publishers.append(norm_pub)
    top_publishers = sorted(
        Counter(all_publishers).items(), key=lambda x: (-x[1], x[0])
    )[:5]

    completed_records = [
        r for r in all_records if r.get("status") == "Completed" and r.get("end_date")
    ]

    yearly_counts = Counter()
    for r in completed_records:
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 4:
            year = date_str[:4]
            if year.isdigit():
                yearly_counts[year] += 1
    sorted_years = sorted(yearly_counts.items())
    max_year_count = max(yearly_counts.values()) if yearly_counts else 1
    avg_year_count = (
        sum(yearly_counts.values()) / len(yearly_counts) if yearly_counts else 0
    )

    monthly_counts = Counter()
    for r in completed_records:
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 7:
            month_idx = date_str[5:7]
            if month_idx.isdigit():
                monthly_counts[month_idx] += 1

    ordered_months = []
    for i in range(1, 13):
        idx_str = f"{i:02d}"
        name = calendar.month_name[i][:3]
        ordered_months.append((i, name, monthly_counts[idx_str]))

    max_month_count = max(monthly_counts.values()) if monthly_counts else 1
    avg_month_count = sum(monthly_counts.values()) / 12

    category_bins = Counter()
    for b in books:
        bid = b.get("id")
        latest = latest_records.get(bid)
        if latest and latest.get("status") == "Completed":
            bisac = b.get("bisac_category")
            if bisac:
                main_cat, _ = parse_bisac_category(bisac)
                if main_cat:
                    norm_cat = (
                        main_cat.title() if len(main_cat) > 3 else main_cat.upper()
                    )
                    category_bins[norm_cat] += 1

    all_categories_sorted = sorted(category_bins.items(), key=lambda x: (-x[1], x[0]))
    category_distribution = all_categories_sorted[:15]
    if len(all_categories_sorted) > 15:
        other_total = sum(count for label, count in all_categories_sorted[15:])
        category_distribution.append(("Other", other_total))

    max_category_count = (
        max(count for label, count in category_distribution)
        if category_distribution
        else 1
    )

    return render_template(
        "stats.html",
        total_books=total_books,
        total_authors=total_authors,
        total_records=total_records,
        avg_rating=avg_rating,
        status_counts=status_counts,
        rating_distribution=rating_distribution,
        top_authors=top_authors,
        top_publishers=top_publishers,
        category_distribution=category_distribution,
        max_category_count=max_category_count,
        yearly_counts=sorted_years,
        max_year_count=max_year_count,
        avg_year_count=avg_year_count,
        monthly_counts=ordered_months,
        max_month_count=max_month_count,
        avg_month_count=avg_month_count,
    )


@stats_bp.route("/stats/backfill-categories")
@authorisation_required
def fetch_missing_categories():
    """Trigger backfill of BISAC categories from the stats page."""
    job_queue = get_job_queue()
    credentials_dict = session.get("credentials")
    import os

    is_prod = os.environ.get("FLASK_ENV") == "production"
    sheet_name = "BookLampData" if is_prod else "DevBookLampData"

    job_id = job_queue.submit_job(
        "backfill_bisac",
        _background_fetch_missing_data,
        credentials_dict,
        sheet_name,
    )

    from flask import flash

    flash(
        "Book categorisation started in the background. Your charts will update as data is found.",
        "info",
    )
    return redirect(url_for("stats.collection_stats", job_id=job_id))
