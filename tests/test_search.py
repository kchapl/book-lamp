"""Tests for the search service and route."""

from book_lamp.app import get_storage
from book_lamp.services.search import calculate_relevance_score, search_books


def test_search_books_by_title():
    """Test searching books by title."""
    books = [
        {"id": 1, "isbn13": "1", "title": "The Great Gatsby", "author": "Fitzgerald"},
        {"id": 2, "isbn13": "2", "title": "To Kill a Mockingbird", "author": "Lee"},
    ]
    results = search_books(books, [], "gatsby")
    assert len(results) == 1
    assert results[0]["title"] == "The Great Gatsby"


def test_search_books_by_author():
    """Test searching books by author."""
    books = [
        {"id": 1, "isbn13": "1", "title": "Gatsby", "author": "F. Scott Fitzgerald"},
        {"id": 2, "isbn13": "2", "title": "Mockingbird", "author": "Harper Lee"},
    ]
    results = search_books(books, [], "harper")
    assert len(results) == 1
    assert results[0]["author"] == "Harper Lee"


def test_search_books_by_isbn():
    """Test searching books by ISBN."""
    books = [{"id": 1, "isbn13": "9780000000001", "title": "Gatsby", "author": "A"}]
    results = search_books(books, [], "9780000000001")
    assert len(results) == 1
    assert results[0]["isbn13"] == "9780000000001"


def test_search_special_characters_treated_literally():
    """Test that special regex characters are treated as literals."""
    books = [
        {"id": 1, "isbn13": "1", "title": "The Great. Gatsby", "author": "A"},
        {
            "id": 2,
            "isbn13": "2",
            "title": "Catcher in the Rye",
            "author": "J.D. Salinger",
        },
    ]
    # Search for literal dot
    results = search_books(books, [], ".")
    assert len(results) == 2


def test_regex_ignored():
    """Verify that regex syntax is treated literally and doesn't match patterns."""
    book = {"id": 1, "title": "The Hitchhiker's Guide"}
    # Regex wildcard should NOT work anymore (treated as literal "Hitch.*Guide")
    assert calculate_relevance_score(book, [], "Hitch.*Guide") == 0
    # Regex anchor (start) should NOT work (treated as literal "^The")
    assert calculate_relevance_score(book, [], "^The") == 0


def test_search_books_by_reading_status():
    """Test searching books by reading status."""
    books = [{"id": 1, "title": "Gatsby", "author": "A"}]
    records = [{"id": 1, "book_id": 1, "status": "Completed"}]
    results = search_books(books, records, "completed")
    assert len(results) == 1
    assert results[0]["title"] == "Gatsby"


def test_search_relevance_scoring():
    """Test that results are sorted by relevance."""
    books = [
        {"id": 1, "title": "Python Programming", "description": "A book"},
        {"id": 2, "title": "Learn Code", "description": "Python mentioned here"},
    ]
    results = search_books(books, [], "python")
    assert len(results) == 2
    # Title match should rank higher than description match
    assert results[0]["title"] == "Python Programming"


def test_search_empty_query():
    """Test that empty query returns no results."""
    books = [{"id": 1, "title": "Gatsby"}]
    assert len(search_books(books, [], "")) == 0
    assert len(search_books(books, [], "   ")) == 0


def test_calculate_relevance_score_exact_match_bonus():
    """Test that exact matches get bonus points."""
    book1 = {"id": 1, "title": "Python"}
    book2 = {"id": 2, "title": "Python Programming"}

    score1 = calculate_relevance_score(book1, [], "python")
    score2 = calculate_relevance_score(book2, [], "python")
    assert score1 > score2


def test_search_with_series():
    """Test searching books by series."""
    books = [{"id": 1, "title": "HP 1", "series": "Harry Potter"}]
    results = search_books(books, [], "harry potter")
    assert len(results) == 1
    assert results[0]["series"] == "Harry Potter"


# --- Tolerance for mistyped words ---


def test_search_ignores_case():
    """A capitalised query is the same query, not a corrected one."""
    books = [{"id": 1, "title": "Project Hail Mary", "author": "Andy Weir"}]
    assert [b["title"] for b in search_books(books, [], "HAIL MARY")] == ["Project Hail Mary"]
    assert calculate_relevance_score(books[0], [], "HAIL MARY") == calculate_relevance_score(books[0], [], "hail mary")


def test_search_tolerates_a_typo_in_a_title():
    """One mistyped word should not hide a Book the other words name."""
    books = [{"id": 1, "title": "Project Hail Mary", "author": "Andy Weir"}]
    results = search_books(books, [], "hail mairy")
    assert [b["title"] for b in results] == ["Project Hail Mary"]


def test_search_tolerates_a_transposed_letter_in_an_author_name():
    """Two swapped characters are one typo, not two."""
    books = [{"id": 1, "title": "Project Hail Mary", "author": "Andy Weir"}]
    results = search_books(books, [], "andy wier")
    assert [b["title"] for b in results] == ["Project Hail Mary"]


def test_search_tolerates_a_typo_and_matches_the_rest_of_a_word():
    """A corrected word still only has to reach the beginning of a word."""
    books = [{"id": 1, "title": "Project Hail Mary", "author": "Andy Weir"}]
    results = search_books(books, [], "projet hail mar")
    assert [b["title"] for b in results] == ["Project Hail Mary"]


def test_an_exact_word_outranks_a_corrected_one():
    """A typo may find a Book, but it must not displace the one spelled right."""
    books = [{"id": 1, "title": "Mery"}, {"id": 2, "title": "Mary"}]
    results = search_books(books, [], "mary")

    assert [b["title"] for b in results] == ["Mary", "Mery"]
    assert calculate_relevance_score(books[1], [], "mary") > calculate_relevance_score(books[0], [], "mary")


def test_short_words_are_not_corrected():
    """Three letters are too little to tell a typo from a different word."""
    book = {"id": 1, "title": "Dune", "author": "Frank Herbert"}
    assert calculate_relevance_score(book, [], "dan") == 0.0


def test_search_returns_nothing_when_no_word_is_close():
    """Tolerance is bounded: a query that resembles nothing still finds nothing."""
    books = [{"id": 1, "title": "Dune", "author": "Frank Herbert"}]
    assert search_books(books, [], "zzzz") == []


def test_every_query_word_has_to_match_somewhere():
    """One matched word does not carry a query whose other words match nothing."""
    books = [{"id": 1, "title": "Hail Caesar", "author": "A"}]
    assert search_books(books, [], "hail mary") == []


def test_query_words_may_land_in_different_fields():
    """The words of a query are matched independently, not as one phrase."""
    books = [{"id": 1, "title": "Project Hail Mary", "author": "Andy Weir"}]
    results = search_books(books, [], "hail weir")
    assert [b["title"] for b in results] == ["Project Hail Mary"]


# --- Route Tests ---


def test_search_route_with_query(authenticated_client):
    """Test search API with a valid query."""
    # Add a test book
    storage = get_storage()
    book = storage.add_book(isbn13="9780000000000", title="A Test Book", authors=["A1"])
    storage.add_reading(book["id"], "Completed", "2024-01-01", "2024-01-15")

    response = authenticated_client.get("/api/books/search?q=test")
    assert response.status_code == 200
    body = response.get_json()
    assert body["search_query"] == "test"
    assert any(b["title"] == "A Test Book" for b in body["books"])


def test_search_route_tolerates_a_typo(authenticated_client):
    """The route returns the Book for a mistyped query, not an empty set.

    The route narrows results to Books that have a Reading Status, so the Book
    needs a Reading to be reachable this way at all.
    """
    storage = get_storage()
    book = storage.add_book(isbn13="9780000000003", title="Project Hail Mary", authors=["Andy Weir"])
    storage.add_reading(book["id"], "Completed", "2026-09-01", "2026-10-11")

    response = authenticated_client.get("/api/books/search?q=hail+mairy")

    assert response.status_code == 200
    assert [b["title"] for b in response.get_json()["books"]] == ["Project Hail Mary"]


def test_search_route_with_empty_query(authenticated_client):
    """Test that empty query returns an empty result set rather than an error."""
    response = authenticated_client.get("/api/books/search?q=")
    assert response.status_code == 200
    assert response.get_json() == {"books": [], "search_query": ""}
