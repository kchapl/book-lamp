from book_lamp.services.search import calculate_relevance_score


def test_search_literal():
    book = {"title": "The Hitchhiker's Guide", "id": 1}
    # Case insensitive match
    assert calculate_relevance_score(book, [], "hitchhiker") > 0
    # Partial match
    assert calculate_relevance_score(book, [], "guide") > 0
    # No match
    assert calculate_relevance_score(book, [], "potato") == 0


def test_search_literal_special_chars():
    book = {"title": "Mr. Robot", "id": 1}
    # "." should be treated literally
    assert calculate_relevance_score(book, [], "Mr.") > 0
    # If it was regex, "." would match "MrX" too, but here we search specifically for "Mr."
    # "Mr." as literal matches ONLY "Mr."


def test_regex_ignored():
    book = {"title": "The Hitchhiker's Guide", "id": 1}
    # Regex wildcard should NOT work anymore (treated as literal "Hitch.*Guide")
    assert calculate_relevance_score(book, [], "Hitch.*Guide") == 0
    # Regex anchor (start) should NOT work (treated as literal "^The")
    assert calculate_relevance_score(book, [], "^The") == 0
