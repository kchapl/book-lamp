"""Tests for the search service and route."""

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


# --- Route Tests ---


def test_search_route_with_query(authenticated_client):
    """Test search route with a valid query."""
    # Add a test book
    authenticated_client.post("/books", data={"isbn": "9780000000000"})
    response = authenticated_client.get("/books/search?q=test", follow_redirects=True)
    assert response.status_code == 200
    assert b"Search results" in response.data


def test_search_route_with_empty_query(authenticated_client):
    """Test that empty query redirects back to books list."""
    response = authenticated_client.get("/books/search?q=", follow_redirects=False)
    assert response.status_code == 302
    assert "/books" in response.location
