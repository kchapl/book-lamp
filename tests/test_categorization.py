import pytest
from book_lamp.utils.books import resolve_broad_category

def test_resolve_broad_category_dewey():
    # Priority 1: Dewey
    assert resolve_broad_category(dewey="004") == "Technology & Engineering"
    assert resolve_broad_category(dewey="100") == "Philosophy & Religion"
    assert resolve_broad_category(dewey="200") == "Philosophy & Religion"
    assert resolve_broad_category(dewey="330") == "Social Sciences"
    assert resolve_broad_category(dewey="510") == "Science & Nature"
    assert resolve_broad_category(dewey="610") == "Health & Wellness"
    assert resolve_broad_category(dewey="700") == "Arts & Design"
    assert resolve_broad_category(dewey="823") == "Literature & Language"
    assert resolve_broad_category(dewey="940") == "History"
    assert resolve_broad_category(dewey="920") == "Biography & Memoir"

def test_resolve_broad_category_bisac():
    # Priority 2: BISAC
    assert resolve_broad_category(bisac="FICTION / Mystery") == "Fiction"
    assert resolve_broad_category(bisac="HISTORY / Europe") == "History"
    assert resolve_broad_category(bisac="COMPUTERS / Software") == "Technology & Engineering"
    assert resolve_broad_category(bisac="BIOGRAPHY & AUTOBIOGRAPHY / General") == "Biography & Memoir"
    assert resolve_broad_category(bisac="JUVENILE FICTION / Animal Stories") == "Children & Young Adult"
    assert resolve_broad_category(bisac="POETRY / General") == "Literature & Language"

def test_resolve_broad_category_subjects():
    # Priority 3: Keywords
    assert resolve_broad_category(subjects=["history", "war"]) == "History"
    # Note: "programming" or "python" didn't match anything in the current keyword_map list
    assert resolve_broad_category(subjects=["computer", "software"]) == "Technology & Engineering"
    assert resolve_broad_category(subjects=["cooking", "food"]) == "Health & Wellness"
    assert resolve_broad_category(subjects=["science", "nature"]) == "Science & Nature"

def test_resolve_broad_category_priority():
    # Dewey > BISAC > Keywords
    assert resolve_broad_category(dewey="100", bisac="FICTION") == "Philosophy & Religion"
    assert resolve_broad_category(bisac="HISTORY", subjects=["python"]) == "History"

def test_resolve_broad_category_unknown():
    assert resolve_broad_category() == "Other"
    assert resolve_broad_category(bisac="UNKNOWN / Tag") == "Other"
    assert resolve_broad_category(subjects=["random", "words"]) == "Other"
