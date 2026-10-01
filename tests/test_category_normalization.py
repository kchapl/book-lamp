"""Category normalisation for the dashboard chart and books filter (issue #160).

Raw ``bisac_category`` values in this catalogue are a mix of real BISAC codes,
Dewey decimals, language codes, page counts and format strings. The chart used
to display them verbatim, so junk like ``823.914`` or ``en`` became a "top-level"
bar and clicking a bar did not match the count shown. These tests pin the
normalisation contract and the chart/filter agreement.
"""

from book_lamp.app import get_storage
from book_lamp.utils import category_label_for_book
from book_lamp.utils.books import (
    UNKNOWN_CATEGORY,
    normalise_bisac_category,
    normalise_major_bisac,
)


def test_normalise_major_bisac_rejects_non_categories():
    reject = [
        "823.92",
        "823/.914",
        "623.45119",
        "en",
        "EN",
        "eng",
        "book",
        "books",
        "ebook",
        "e-book",
        "print",
        "audio",
        "paperback",
        "hardcover",
        "416",
        "123",
        "Unknown",
        "",
        None,
    ]
    for value in reject:
        assert normalise_major_bisac(value) is None, f"should have rejected {value!r}"


def test_normalise_major_bisac_canonicalises_known_categories():
    assert normalise_major_bisac("fiction") == "FICTION"
    assert normalise_major_bisac("Fiction") == "FICTION"
    assert normalise_major_bisac("HISTORY") == "HISTORY"
    assert normalise_major_bisac("Biography") == "BIOGRAPHY & AUTOBIOGRAPHY"
    assert normalise_major_bisac("Political Science") == "POLITICAL SCIENCE"
    # Short valid categories must survive the language-code filter.
    assert normalise_major_bisac("art") == "ART"
    assert normalise_major_bisac("poetry") == "POETRY"
    assert normalise_major_bisac("drama") == "DRAMA"
    # Unlisted but plausible categories fall back to uppercase.
    assert normalise_major_bisac("random valid category") == "RANDOM VALID CATEGORY"


def test_normalise_bisac_category_filters_invalid_subcategories():
    assert normalise_bisac_category("FICTION / Literary") == ("FICTION / Literary", "FICTION", "Literary")
    assert normalise_bisac_category("History / Europe") == ("HISTORY / Europe", "HISTORY", "Europe")
    assert normalise_bisac_category("FICTION / 416") == ("FICTION", "FICTION", None)
    assert normalise_bisac_category("HISTORY / en") == ("HISTORY", "HISTORY", None)
    assert normalise_bisac_category("823.92 / Literary") == (None, None, None)
    assert normalise_bisac_category("en") == (None, None, None)


def test_category_label_for_book_prefers_major_and_falls_back():
    assert category_label_for_book({"bisac_main_category": "FICTION"}) == "Fiction"
    assert category_label_for_book({"bisac_category": "HISTORY / Europe"}) == "History"
    assert category_label_for_book({"bisac_category": "823.914"}) == UNKNOWN_CATEGORY
    assert category_label_for_book({}) == UNKNOWN_CATEGORY


def _add_completed_book(storage, isbn, title, bisac_category):
    book = storage.add_book(isbn13=isbn, title=title, author="Author", bisac_category=bisac_category)
    storage.add_reading_record(book["id"], "Completed", "2024-01-01", "2024-01-02", rating=5)
    return book


def test_dashboard_maps_invalid_categories_to_unknown(authenticated_client):
    storage = get_storage()
    _add_completed_book(storage, "9780000000010", "Dewey Book", "823.914")
    _add_completed_book(storage, "9780000000011", "Language Book", "en")
    _add_completed_book(storage, "9780000000012", "Page Count Book", "416")
    _add_completed_book(storage, "9780000000013", "Fiction Book", "FICTION / General")

    resp = authenticated_client.get("/api/dashboard")
    assert resp.status_code == 200
    cats = {c["label"]: c["count"] for c in resp.get_json()["category_distribution"]}

    assert cats[UNKNOWN_CATEGORY] == 3
    assert cats["Fiction"] == 1
    assert "823.914" not in cats
    assert "en" not in cats
    assert "416" not in cats


def test_books_filter_matches_dashboard_category_counts(authenticated_client):
    storage = get_storage()
    _add_completed_book(storage, "9780000000020", "F1", "FICTION / General")
    _add_completed_book(storage, "9780000000021", "F2", "FICTION / Literary")
    _add_completed_book(storage, "9780000000022", "H1", "HISTORY / Europe")

    dashboard = authenticated_client.get("/api/dashboard").get_json()
    chart = {c["label"]: c["count"] for c in dashboard["category_distribution"]}

    resp = authenticated_client.get("/api/books?category=Fiction")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert len(payload["books"]) == chart["Fiction"] == 2
    assert {b["title"] for b in payload["books"]} == {"F1", "F2"}
    # The filter dropdown is built from the same normalised labels.
    assert {"Fiction", "History"} <= set(payload["categories"])
