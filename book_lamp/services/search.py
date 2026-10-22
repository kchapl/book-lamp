"""Search service for book data.

This module provides search functionality across book and reading fields.
Supports free text search, matched word by word: a query finds a Book when every
word in it appears in some searched field, and a single well-spelled word is not
defeated by one mistyped one.
"""

import re
from typing import Any, Dict, List, Set, Tuple

# How well a query word matched a field. The better the match, the more of the
# field's weight it earns — and a corrected match has to score below a literal
# one, or a mistyped query could outrank the Book the reader can spell.
LITERAL = 1.0
PREFIX = 0.6
CORRECTED = 0.3

# A field that carries only some of the query's words still counts, at a
# discount: a Book is found by its words, not by half of one field.
PARTIAL_FIELD = 0.5

# Correction is only attempted on words, and a three-letter word is too little
# to tell a typo from a different word: ``dan`` is not ``dune``.
MIN_CORRECTABLE_LENGTH = 4

_WORD = re.compile(r"\w+", re.UNICODE)


def _words(text: str) -> List[str]:
    """The words in a field value, lower-cased, for prefix and typo matching."""
    return _WORD.findall(text.lower())


def _typo_budget(word: str) -> int:
    """How many edits a word of this length is allowed to carry.

    An edit is a missing, extra or substituted character, or two adjacent
    characters the wrong way round. The budget is three characters or fewer:
    none; four to seven: one; eight or more: two. Shorter words get less room
    because a near-miss between short words is usually a different word, and
    longer words can carry a typo without colliding with anything else.
    """
    if len(word) < MIN_CORRECTABLE_LENGTH:
        return 0
    return 1 if len(word) <= 7 else 2


def _within_one_edit(a: str, b: str) -> bool:
    """Whether ``a`` is one edit from ``b``, checked in one pass.

    Edits are a character missing, extra or changed, or two adjacent characters
    the wrong way round. This is the common case by far, and the direct check
    costs a scan rather than the matrix the general form builds.
    """
    first = 0
    while first < len(a) and first < len(b) and a[first] == b[first]:
        first += 1

    if len(a) == len(b):
        # Either one character changed, or two adjacent ones were swapped.
        if a[first + 1 :] == b[first + 1 :]:
            return True
        return (
            first + 1 < len(a)
            and a[first] == b[first + 1]
            and a[first + 1] == b[first]
            and a[first + 2 :] == b[first + 2 :]
        )

    if abs(len(a) - len(b)) != 1:
        return False

    # One character inserted or removed: skipping it must leave the rest equal.
    # The extra character sits at the first place the two strings disagree, so
    # skipping that position on the longer string is the only place to look.
    longer, shorter = (a, b) if len(a) > len(b) else (b, a)
    return longer[first + 1 :] == shorter[first:]


def _within_edits(a: str, b: str, limit: int) -> bool:
    """Whether ``a`` is at most ``limit`` edits from ``b``.

    Optimal string alignment rather than plain Levenshtein: swapping two
    adjacent characters is the most common typo of all, and counting it as two
    edits would put ``wier`` out of reach of ``weir``.
    """
    if a == b:
        return True
    if limit == 1:
        return _within_one_edit(a, b)
    if abs(len(a) - len(b)) > limit:
        return False

    # dist[i][j] is the distance between a[:i] and b[:j]. The two previous rows
    # are kept because a transposition reaches back two of them.
    previous_previous: List[int] = []
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i] + [0] * len(b)
        for j, char_b in enumerate(b, 1):
            current[j] = min(
                previous[j] + 1,  # a character removed from the query word
                current[j - 1] + 1,  # a character added to it
                previous[j - 1] + (char_a != char_b),  # a character changed
            )
            if i > 1 and j > 1 and char_a == b[j - 2] and a[i - 2] == char_b:
                current[j] = min(current[j], previous_previous[j - 2] + 1)
        previous_previous, previous = previous, current

    return previous[-1] <= limit


def _starts_a_word(token: str, text: str) -> bool:
    """Whether the query word begins a word in ``text``.

    Run as a regex so a long description is scanned in C rather than in a Python
    loop, and only for tokens that are themselves word-like: a token carrying
    punctuation is literal-only by design.
    """
    if not token[0].isalnum():
        return False
    return re.search(rf"\b{re.escape(token)}", text) is not None


def _field_score(
    tokens: List[str],
    text: str,
    weight: float,
    query: str,
    correct: bool = True,
) -> Tuple[float, Set[int]]:
    """Score one field against the query, and report which words it matched.

    A query word matches in one of three tiers: literally (checked first, since
    it is both the commonest and the strongest), at the start of a word, or as a
    bounded correction of a word. ``text`` and ``query`` are already lower-cased
    by the caller, and a token carrying punctuation is never corrected: ``^The``
    asks for a literal caret, not a fix of ``The``, and must keep matching
    nothing.

    The second half of the return value is what makes coverage explicit: a Book
    only counts once every query word has been matched *somewhere*, and a field
    on its own can only vouch for the words it carries.

    Set ``correct=False`` for prose. A description is long enough that a word one
    edit from the query is far likelier a different word than a typo of the one
    being looked for, and correcting against it turns tolerance into noise.
    """
    factors: List[float] = []
    words: List[str] | None = None

    for token in tokens:
        if not token or not text:
            factors.append(0.0)
            continue
        if token in text:
            factors.append(LITERAL)
            continue
        if _starts_a_word(token, text):
            factors.append(PREFIX)
            continue

        budget = _typo_budget(token) if correct and token.isalpha() else 0
        if not budget:
            factors.append(0.0)
            continue
        if words is None:
            words = _words(text)
        corrected = any(_within_edits(token, word, budget) for word in words)
        factors.append(CORRECTED if corrected else 0.0)

    matched = {index for index, factor in enumerate(factors) if factor}
    if not matched:
        return 0.0, matched

    score = weight * (sum(factors) / len(tokens))
    if len(matched) < len(tokens):
        score *= PARTIAL_FIELD
    elif text == query:
        # A field that is exactly the query is a stronger hit than one that
        # merely contains it, which is what puts "Python" above "Python
        # Programming" for the query "python".
        score += weight * 0.5
    return score, matched


def calculate_relevance_score(
    book: Dict[str, Any],
    readings: List[Dict[str, Any]],
    query: str,
) -> float:
    """Calculate relevance score for a book based on search query.

    Args:
        book: Book dictionary with fields to search.
        readings: List of readings for this book.
        query: Search query string.

    Returns:
        Relevance score (higher = more relevant), or 0.0 when the query does
        not match the book. Every word in the query must be found in some field
        before a book scores at all.
    """
    lowered_query = query.lower()
    # Field values are lower-cased for matching, so the query's words have to be
    # too — otherwise a capitalised query would only ever match as a "typo".
    tokens = lowered_query.split()
    if not tokens:
        return 0.0
    score = 0.0
    matched_anywhere: Set[int] = set()

    # Field weights (higher weight = more important match)
    weights = {
        "title": 10.0,
        "author": 8.0,
        "isbn13": 7.0,
        "series": 6.0,
        "publisher": 4.0,
        "description": 2.0,
        "bisac_category": 7.0,
        "publication_year": 3.0,
        "id": 10.0,  # strong match if user searches for specific ID
        "created_at": 1.0,
        # Reading record fields
        "status": 5.0,
        "rating": 4.0,
        "dates": 3.0,  # start_date and end_date
    }

    for field, weight in weights.items():
        if field in ("status", "rating", "dates"):
            continue  # These are in readings

        if field == "author":
            # Search both the legacy display name and the individual authors.
            author_values = [book.get("author")] + list(book.get("authors") or [])
            for author in author_values:
                if not author:
                    continue
                author_score, matched = _field_score(tokens, str(author).lower(), weight, lowered_query)
                score += author_score
                matched_anywhere |= matched
            continue

        value = book.get(field)
        if not value:
            continue
        field_score, matched = _field_score(
            tokens,
            str(value).lower(),
            weight,
            lowered_query,
            # Prose is matched literally or by prefix; a correction inside a
            # description is a different word far more often than a typo.
            correct=field != "description",
        )
        score += field_score
        matched_anywhere |= matched

    for record in readings:
        reading_values = (
            ("status", record.get("status")),
            ("rating", record.get("rating")),
            ("dates", record.get("start_date")),
            ("dates", record.get("end_date")),
        )
        for field, value in reading_values:
            if not value:
                continue
            field_score, matched = _field_score(tokens, str(value).lower(), weights[field], lowered_query)
            score += field_score
            matched_anywhere |= matched

    # Every word in the query has to land somewhere. Without this a single
    # matching word would scoop up every Book that carries it, which is the
    # false-positive half of tolerance.
    if len(matched_anywhere) < len(tokens):
        return 0.0

    return score


def search_books(
    all_books: List[Dict[str, Any]],
    all_records: List[Dict[str, Any]],
    query: str,
) -> List[Dict[str, Any]]:
    """Search across all book data fields.

    Args:
        all_books: List of all books.
        all_records: List of all readings.
        query: Search query (free text).

    Returns:
        List of matching books with readings attached, sorted by relevance.
    """
    if not query or not query.strip():
        return []

    query = query.strip()

    # Attach readings to books and calculate scores
    results = []
    for book in all_books:
        book_records = [r for r in all_records if r["book_id"] == book["id"]]
        score = calculate_relevance_score(book, book_records, query)

        if score > 0:
            # Create a copy to avoid mutating the original
            book_copy = book.copy()
            book_copy["readings"] = book_records
            book_copy["_relevance_score"] = score
            results.append(book_copy)

    # Sort by relevance score (descending)
    results.sort(key=lambda b: b["_relevance_score"], reverse=True)

    return results
