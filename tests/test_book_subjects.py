"""A Book keeps every subject it carries, not just the first (#407)."""

import book_lamp.services.book_lookup as lookup_module
from book_lamp.app import get_storage
from book_lamp.utils.books import (
    Category,
    category_labels_for_book,
    normalise_subjects,
    resolve_subjects,
    subjects_for_book,
)


def test_every_subject_is_normalised_and_duplicates_collapse_by_label():
    subjects = normalise_subjects(
        [
            "Fiction / Mystery",
            "Murder",
            "FICTION / Mystery",
            "823.914",
            "en",
            "BOOK",
        ]
    )

    assert [subject["main"] for subject in subjects] == ["FICTION", "MURDER"]
    assert subjects[0] == {
        "category": "FICTION / Mystery",
        "main": "FICTION",
        "sub": "Mystery",
    }


def test_a_legacy_row_reads_as_one_subject_and_nothing_reads_as_none():
    assert subjects_for_book({"bisac_category": "HISTORY / Europe"}) == [
        {"category": "HISTORY / Europe", "main": "HISTORY", "sub": "Europe"}
    ]
    # The validated main survives when the full value is junk.
    assert subjects_for_book({"bisac_category": "en", "bisac_main_category": "FICTION"}) == [
        {"category": "FICTION", "main": "FICTION", "sub": None}
    ]
    assert subjects_for_book({}) == []


def test_a_book_can_be_counted_and_filtered_under_each_subject(authenticated_client):
    response = authenticated_client.post(
        "/api/books",
        json={
            "isbn": "9780000002204",
            "title": "A Mystery",
            "authors": ["An Author"],
            "subjects": ["Fiction / Mystery", "Murder", "Murder"],
        },
    )
    assert response.status_code == 201
    book_id = response.get_json()["id"]

    detail = authenticated_client.get(f"/api/books/{book_id}").get_json()
    assert [subject["label"] for subject in detail["subjects"]] == ["Fiction", "Murder"]
    # The first subject remains the legacy label, so older surfaces agree.
    assert detail["bisac_category_label"] == "Fiction"

    # A Book is in My Books once it has a Reading Status.
    storage = get_storage()
    storage.add_reading(book_id, "Completed", "2026-01-01", "2026-01-02", rating=4)

    by_murder = authenticated_client.get("/api/books?category=Murder").get_json()
    assert [book["id"] for book in by_murder["books"]] == [book_id]
    assert {"Fiction", "Murder"} <= set(by_murder["categories"])

    dashboard = authenticated_client.get("/api/dashboard").get_json()
    counts = {entry["label"]: entry["count"] for entry in dashboard["category_distribution"]}
    assert counts["Fiction"] == 1
    assert counts["Murder"] == 1


def test_the_google_parser_reads_the_whole_categories_list():
    parsed = lookup_module._parse_google_books_item(
        {"volumeInfo": {"title": "A Book", "categories": ["Fiction", "Murder"]}}
    )

    assert [subject["main"] for subject in parsed["subjects"]] == ["FICTION", "MURDER"]
    # A second category is a subject, not a subdivision of the first.
    assert parsed["bisac_category"] == "FICTION"
    assert parsed["bisac_sub_category"] is None


def test_the_open_library_parser_reads_the_whole_subjects_list():
    parsed = lookup_module._parse_open_library_data(
        {
            "title": "A Book",
            "subjects": [{"name": "Fiction"}, {"name": "Murder"}],
        }
    )

    assert [subject["main"] for subject in parsed["subjects"]] == ["FICTION", "MURDER"]
    assert parsed["bisac_category"] == "FICTION"


def test_the_open_library_parser_drops_catalogue_tags():
    """A tag that says how a Book is held is not a subject it carries."""
    parsed = lookup_module._parse_open_library_data(
        {
            "title": "A Book",
            "subjects": [
                {"name": "Fiction"},
                {"name": "Accessible book"},
                {"name": "Protected DAISY"},
                {"name": "In library"},
                {"name": "nyt:hardcover-fiction=2020-01-01"},
                {"name": "Murder"},
            ],
        }
    )

    assert [subject["main"] for subject in parsed["subjects"]] == ["FICTION", "MURDER"]
    assert parsed["bisac_category"] == "FICTION"


def test_a_category_that_arrives_without_a_list_joins_the_merge():
    """An upsert naming only a category adds it; the stored list still leads."""
    subject_list, legacy = resolve_subjects(
        {"subjects": [{"category": "FICTION", "main": "FICTION", "sub": None}]},
        None,
        Category("HISTORY", "HISTORY", None),
        merge=True,
    )

    assert [subject["main"] for subject in subject_list] == ["FICTION", "HISTORY"]
    assert legacy.category == "FICTION"


def test_a_stored_subject_list_wins_over_the_legacy_pair():
    book = {
        "bisac_category": "Fiction",
        "subjects": [
            {"category": "FICTION / Mystery", "main": "FICTION", "sub": "Mystery"},
            {"category": "MURDER", "main": "MURDER", "sub": None},
        ],
    }

    assert category_labels_for_book(book) == ["Fiction", "Murder"]


def test_a_book_with_no_subject_is_filtered_and_offered_as_unknown(authenticated_client):
    """The Unknown bucket the chart counts is one the filter can actually open."""
    response = authenticated_client.post(
        "/api/books",
        json={"isbn": "9780000002242", "title": "An Unclassified Book", "authors": ["An Author"]},
    )
    assert response.status_code == 201
    book_id = response.get_json()["id"]

    storage = get_storage()
    storage.add_reading(book_id, "Completed", "2026-01-01", "2026-01-02", rating=4)

    unknown = authenticated_client.get("/api/books?category=Unknown").get_json()
    assert [book["id"] for book in unknown["books"]] == [book_id]
    assert "Unknown" in unknown["categories"]
