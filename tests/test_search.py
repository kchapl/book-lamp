"""Tests for the search service."""

from book_lamp.services.search import calculate_relevance_score, search_books


def test_search_books_by_title():
    """Test searching books by title."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
        {
            "id": 2,
            "isbn13": "9780000000002",
            "title": "To Kill a Mockingbird",
            "author": "Harper Lee",
            "publication_year": 1960,
        },
    ]
    records = []

    results = search_books(books, records, "gatsby")
    assert len(results) == 1
    assert results[0]["title"] == "The Great Gatsby"


def test_search_books_by_author():
    """Test searching books by author."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
        {
            "id": 2,
            "isbn13": "9780000000002",
            "title": "To Kill a Mockingbird",
            "author": "Harper Lee",
            "publication_year": 1960,
        },
    ]
    records = []

    results = search_books(books, records, "harper")
    assert len(results) == 1
    assert results[0]["author"] == "Harper Lee"


def test_search_books_by_isbn():
    """Test searching books by ISBN."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
    ]
    records = []

    results = search_books(books, records, "9780000000001")
    assert len(results) == 1
    assert results[0]["isbn13"] == "9780000000001"


def test_search_special_characters_treated_literally():
    """Test that special regex characters are treated as literals."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great. Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
        {
            "id": 2,
            "isbn13": "9780000000002",
            "title": "The Catcher in the Rye",
            "author": "J.D. Salinger",
            "publication_year": 1951,
        },
    ]
    records = []

    # Search for "Great." (literal dot)
    # If regex was active, "Great." might match "Great " or "GreatX" depending on engine/input
    # But as literal, it should only match "The Great. Gatsby"

    results = search_books(books, records, "Great.")
    assert len(results) == 1
    assert results[0]["title"] == "The Great. Gatsby"

    # Search for literal "."
    # "The Catcher in the Rye" doesn't have a dot. "J.D." does. "The Great. Gatsby" has a dot.
    # Should find 2 books.
    results = search_books(books, records, ".")
    assert len(results) == 2


def test_search_books_by_reading_status():
    """Test searching books by reading status."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
        {
            "id": 2,
            "isbn13": "9780000000002",
            "title": "To Kill a Mockingbird",
            "author": "Harper Lee",
            "publication_year": 1960,
        },
    ]
    records = [
        {
            "id": 1,
            "book_id": 1,
            "status": "Completed",
            "start_date": "2024-01-01",
            "end_date": "2024-01-15",
            "rating": 5,
        },
        {
            "id": 2,
            "book_id": 2,
            "status": "In Progress",
            "start_date": "2024-02-01",
            "end_date": None,
            "rating": 0,
        },
    ]

    results = search_books(books, records, "completed")
    assert len(results) == 1
    assert results[0]["title"] == "The Great Gatsby"


def test_search_relevance_scoring():
    """Test that results are sorted by relevance."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "Python Programming",
            "author": "John Doe",
            "publication_year": 2020,
            "description": "A book about programming",
        },
        {
            "id": 2,
            "isbn13": "9780000000002",
            "title": "Learning to Code",
            "author": "Jane Smith",
            "publication_year": 2021,
            "description": "Python is mentioned here",
        },
    ]
    records = []

    results = search_books(books, records, "python")
    assert len(results) == 2
    # Title match should rank higher than description match
    assert results[0]["title"] == "Python Programming"
    assert results[1]["title"] == "Learning to Code"


def test_search_empty_query():
    """Test that empty query returns no results."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
    ]
    records = []

    results = search_books(books, records, "")
    assert len(results) == 0

    results = search_books(books, records, "   ")
    assert len(results) == 0


def test_search_no_matches():
    """Test that no matches returns empty list."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
    ]
    records = []

    results = search_books(books, records, "nonexistent")
    assert len(results) == 0


def test_search_case_insensitive():
    """Test that search is case insensitive."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "publication_year": 1925,
        },
    ]
    records = []

    results = search_books(books, records, "GATSBY")
    assert len(results) == 1
    assert results[0]["title"] == "The Great Gatsby"


def test_calculate_relevance_score_title_match():
    """Test relevance scoring for title match."""
    book = {
        "id": 1,
        "isbn13": "9780000000001",
        "title": "Python Programming",
        "author": "John Doe",
    }
    records = []

    score = calculate_relevance_score(book, records, "python")
    assert score > 0


def test_calculate_relevance_score_exact_match_bonus():
    """Test that exact matches get bonus points."""
    book1 = {
        "id": 1,
        "isbn13": "9780000000001",
        "title": "Python",
        "author": "John Doe",
    }
    book2 = {
        "id": 2,
        "isbn13": "9780000000002",
        "title": "Python Programming",
        "author": "Jane Smith",
    }
    records = []

    score1 = calculate_relevance_score(book1, records, "python")
    score2 = calculate_relevance_score(book2, records, "python")

    # Exact match should score higher
    assert score1 > score2


def test_search_with_series():
    """Test searching books by series."""
    books = [
        {
            "id": 1,
            "isbn13": "9780000000001",
            "title": "Harry Potter and the Philosopher's Stone",
            "author": "J.K. Rowling",
            "series": "Harry Potter",
            "publication_year": 1997,
        },
        {
            "id": 2,
            "isbn13": "9780000000002",
            "title": "The Hobbit",
            "author": "J.R.R. Tolkien",
            "series": "Middle-earth",
            "publication_year": 1937,
        },
    ]
    records = []

    results = search_books(books, records, "middle-earth")
    assert len(results) == 1
    assert results[0]["series"] == "Middle-earth"
