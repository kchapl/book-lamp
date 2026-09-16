"""Pure calculations for reading log statistics and dashboard metrics."""

import calendar
import datetime
from collections import Counter
from typing import Any, Dict, List, Optional

from book_lamp.utils import parse_bisac_category
from book_lamp.utils.publishers import normalize_publisher


def calculate_collection_stats(
    books: List[Dict[str, Any]],
    all_records: List[Dict[str, Any]],
    settings: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Compute collection statistics from book and reading record lists (pure)."""
    completed_records = [r for r in all_records if r.get("status") == "Completed"]
    completed_book_ids = {r.get("book_id") for r in completed_records}
    completed_books = [b for b in books if b.get("id") in completed_book_ids]

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

    latest_records = {}
    for r in all_records:
        bid = r.get("book_id")
        if bid:
            if bid not in latest_records or r.get("start_date", "") > latest_records[
                bid
            ].get("start_date", ""):
                latest_records[bid] = r

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
            norm_pub = normalize_publisher(b["publisher"])
            if norm_pub:
                all_publishers.append(norm_pub)
    top_publishers = sorted(
        Counter(all_publishers).items(), key=lambda x: (-x[1], x[0])
    )[:5]

    completed_records_for_dates = [
        r for r in all_records if r.get("status") == "Completed" and r.get("end_date")
    ]

    yearly_counts = Counter()
    for r in completed_records_for_dates:
        date_val = r.get("end_date")
        if date_val:
            if isinstance(date_val, datetime.date):
                year = str(date_val.year)
            elif isinstance(date_val, str) and len(date_val) >= 4:
                year = date_val[:4]
            else:
                continue
            if year.isdigit():
                yearly_counts[year] += 1

    sorted_years = sorted(yearly_counts.items())
    max_year_count = max(yearly_counts.values()) if yearly_counts else 1

    monthly_counts = Counter()
    for r in completed_records_for_dates:
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 7:
            month_idx = date_str[5:7]
            if month_idx.isdigit():
                monthly_counts[month_idx] += 1

    ordered_months = []
    for i in range(1, 13):
        idx_str = f"{i:02d}"
        name = calendar.month_name[i][:3]
        ordered_months.append(
            {"index": i, "name": name, "count": monthly_counts[idx_str]}
        )

    max_month_count = max(monthly_counts.values()) if monthly_counts else 1

    category_bins = Counter()
    for b in completed_books:
        bisac = b.get("bisac_category")
        if bisac:
            main_cat, _ = parse_bisac_category(bisac)
            if main_cat:
                norm_cat = main_cat.title() if len(main_cat) > 3 else main_cat.upper()
                category_bins[norm_cat] += 1

    all_categories_sorted = sorted(category_bins.items(), key=lambda x: (-x[1], x[0]))
    category_distribution = all_categories_sorted[:10]
    if len(all_categories_sorted) > 10:
        other_total = sum(count for label, count in all_categories_sorted[10:])
        category_distribution.append(("Other", other_total))

    max_category_count = (
        max(count for label, count in category_distribution)
        if category_distribution
        else 1
    )

    total_pages_read = 0
    for b in completed_books:
        page_count = b.get("page_count")
        if page_count:
            try:
                total_pages_read += int(page_count)
            except (ValueError, TypeError):
                pass

    avg_pages_per_book = total_pages_read / total_books if total_books > 0 else 0

    total_reading_days = 0
    for r in completed_records_for_dates:
        start = r.get("start_date")
        end = r.get("end_date")
        if start and end:
            try:
                if isinstance(start, datetime.date):
                    start_dt = start
                elif isinstance(start, str):
                    start_dt = datetime.date.fromisoformat(start[:10])
                else:
                    continue
                if isinstance(end, datetime.date):
                    end_dt = end
                elif isinstance(end, str):
                    end_dt = datetime.date.fromisoformat(end[:10])
                else:
                    continue
                days = (end_dt - start_dt).days
                if days >= 0:
                    total_reading_days += days
            except (ValueError, TypeError):
                pass

    avg_reading_time_days = (
        total_reading_days / len(completed_records_for_dates)
        if completed_records_for_dates
        else 0
    )

    current_year = datetime.datetime.now().year
    current_streak = 0
    longest_streak = 0

    completions_by_month: Dict[str, int] = {}
    for r in completed_records_for_dates:
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 7:
            year_month = date_str[:7]
            completions_by_month[year_month] = (
                completions_by_month.get(year_month, 0) + 1
            )

    if completions_by_month:
        check_date = datetime.date(current_year, datetime.datetime.now().month, 1)
        while True:
            key = check_date.strftime("%Y-%m")
            if key in completions_by_month:
                current_streak += 1
                if check_date.month == 1:
                    check_date = datetime.date(check_date.year - 1, 12, 1)
                else:
                    check_date = datetime.date(check_date.year, check_date.month - 1, 1)
            else:
                break

        sorted_months = sorted(completions_by_month.keys())
        if sorted_months:
            streak = 1
            for i in range(1, len(sorted_months)):
                prev = datetime.date.fromisoformat(sorted_months[i - 1] + "-01")
                curr = datetime.date.fromisoformat(sorted_months[i] + "-01")
                expected = (
                    prev.replace(month=prev.month + 1)
                    if prev.month < 12
                    else datetime.date(prev.year + 1, 1, 1)
                )
                if curr == expected:
                    streak += 1
                else:
                    longest_streak = max(longest_streak, streak)
                    streak = 1
            longest_streak = max(longest_streak, streak)

    current_year_str = str(current_year)
    previous_year_str = str(current_year - 1)
    books_this_year = yearly_counts.get(current_year_str, 0)
    books_last_year = yearly_counts.get(previous_year_str, 0)

    if books_last_year > 0:
        percentage_change = round(
            ((books_this_year - books_last_year) / books_last_year) * 100, 1
        )
    else:
        percentage_change = 100.0 if books_this_year > 0 else 0.0

    year_comparison = {
        "current_year": books_this_year,
        "previous_year": books_last_year,
        "percentage_change": percentage_change,
    }

    months_with_data = len(completions_by_month) if completions_by_month else 1
    reading_pace_monthly = (
        round(total_books / months_with_data, 2) if months_with_data > 0 else 0
    )
    reading_pace_annualised = round(reading_pace_monthly * 12, 1)

    format_bins = Counter()
    for b in completed_books:
        fmt = b.get("physical_format")
        if fmt:
            format_bins[fmt] += 1
    format_distribution = [
        {"label": label, "count": count}
        for label, count in sorted(format_bins.items(), key=lambda x: -x[1])
    ]

    language_bins = Counter()
    for b in completed_books:
        lang = b.get("language")
        if lang:
            language_bins[lang] += 1
    language_distribution = [
        {"label": label, "count": count}
        for label, count in sorted(language_bins.items(), key=lambda x: -x[1])
    ]

    series_bins: Dict[str, List[str]] = {}
    for b in completed_books:
        series = b.get("series")
        if series:
            if series not in series_bins:
                series_bins[series] = []
            title = b.get("title", "Unknown")
            if title not in series_bins[series]:
                series_bins[series].append(title)

    top_series = [
        {"name": name, "count": len(series_books), "books": series_books[:5]}
        for name, series_books in sorted(series_bins.items(), key=lambda x: -len(x[1]))[:5]
    ]

    category_details_list = []
    for b in completed_books:
        bisac = b.get("bisac_category")
        if bisac:
            main_cat, sub_cat = parse_bisac_category(bisac)
            if main_cat:
                norm_cat = main_cat.title() if len(main_cat) > 3 else main_cat.upper()
                existing = next(
                    (c for c in category_details_list if c["label"] == norm_cat), None
                )
                if not existing:
                    existing = {
                        "label": norm_cat,
                        "count": 0,
                        "subcategories": Counter(),
                    }
                    category_details_list.append(existing)
                existing["count"] += 1
                if sub_cat:
                    existing["subcategories"][sub_cat] += 1

    category_details_list.sort(key=lambda x: -x["count"])
    category_details = [
        {
            "label": c["label"],
            "count": c["count"],
            "subcategories": [
                {"name": name, "count": count}
                for name, count in c["subcategories"].most_common(5)
            ],
        }
        for c in category_details_list[:10]
    ]

    yearly_goal = None
    if settings:
        goal_str = settings.get("yearly_goal")
        if goal_str:
            try:
                yearly_goal = int(goal_str)
            except (ValueError, TypeError):
                pass

    goal_progress_percent = 0.0
    if yearly_goal and yearly_goal > 0:
        goal_progress_percent = min(
            round((books_this_year / yearly_goal) * 100, 1), 100.0
        )

    return {
        "total_books": total_books,
        "total_authors": total_authors,
        "total_records": total_records,
        "avg_rating": avg_rating,
        "status_counts": dict(status_counts),
        "rating_distribution": rating_distribution,
        "top_authors": [
            {"name": name, "count": count} for name, count in top_authors
        ],
        "top_publishers": [
            {"name": name, "count": count} for name, count in top_publishers
        ],
        "category_distribution": [
            {"label": label, "count": count}
            for label, count in category_distribution
        ],
        "max_category_count": max_category_count,
        "yearly_counts": sorted_years,
        "max_year_count": max_year_count,
        "monthly_counts": ordered_months,
        "max_month_count": max_month_count,
        "total_pages_read": total_pages_read,
        "avg_pages_per_book": round(avg_pages_per_book, 1),
        "avg_reading_time_days": round(avg_reading_time_days, 1),
        "total_reading_days": total_reading_days,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "yearly_goal": yearly_goal,
        "books_this_year": books_this_year,
        "goal_progress_percent": goal_progress_percent,
        "format_distribution": format_distribution,
        "language_distribution": language_distribution,
        "top_series": top_series,
        "category_details": category_details,
        "year_comparison": year_comparison,
        "reading_pace_monthly": reading_pace_monthly,
        "reading_pace_annualised": reading_pace_annualised,
    }
