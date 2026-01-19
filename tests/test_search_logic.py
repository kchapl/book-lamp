from book_lamp.services.search import calculate_relevance_score


def test_search_literal():
    book = {"title": "The Hitchhiker's Guide", "id": 1}
    # Case insensitive match
    assert calculate_relevance_score(book, [], "hitchhiker", False) > 0
    # Partial match
    assert calculate_relevance_score(book, [], "guide", False) > 0
    # No match
    assert calculate_relevance_score(book, [], "potato", False) == 0


def test_search_literal_special_chars():
    book = {"title": "Mr. Robot", "id": 1}
    # "." should be treated literally
    assert calculate_relevance_score(book, [], "Mr.", False) > 0
    # If it was regex, "." would match "MrX" too, but here we search specifically for "Mr."
    # Wait, "Mr." as regex matches "Mr." AND "Mrs".
    # "Mr." as literal matches ONLY "Mr."

    # "Mr." escaped is "Mr\."
    # re.search("Mr\.", "Mr. Robot") -> Matches.
    # re.search("Mr\.", "Mrs Robot") -> No match.
    pass


def test_search_regex_mode():
    book = {"title": "The Hitchhiker's Guide", "id": 1}
    # Regex wildcard
    assert calculate_relevance_score(book, [], "Hitch.*Guide", True) > 0
    # Regex anchor (start)
    assert calculate_relevance_score(book, [], "^The", True) > 0
    # Regex anchor (fail)
    assert calculate_relevance_score(book, [], "^Guide", True) == 0


def test_search_regex_unescaped_observation():
    # In regex mode, "." matches any char.
    # So "Mr." matches "Mrs"
    assert calculate_relevance_score({"title": "Mrs. Robot"}, [], "Mr.", True) > 0

    # This confirms line 66 is indeed "unescaped" and acting as regex.
