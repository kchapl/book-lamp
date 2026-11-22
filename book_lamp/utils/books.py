import html
import re
from collections.abc import Mapping
from typing import Any, NamedTuple, Optional


def cover_is_blank(value: object) -> bool:
    """Whether a stored cover value counts as no cover at all."""
    return value is None or (isinstance(value, str) and not value.strip())


#: A dash that separates a subtitle, with the spaces on both sides that make
#: it a separator. A bare hyphen stays in the word it belongs to ("Spider-Man").
_SPACED_DASHES = (" - ", " \u2013 ", " \u2014 ")


def _separator_span(text: str) -> Optional[tuple[int, int]]:
    """Where a subtitle separator starts and ends in ``text``, or None.

    Scanned rather than matched, so a reader-supplied run of spaces cannot make
    the check quadratic. Whether what precedes a separator can stand as a title
    is the caller's decision.
    """
    colon = text.find(":")
    dash = min((index for index in (text.find(d) for d in _SPACED_DASHES) if index != -1), default=-1)

    if colon == -1 and dash == -1:
        return None
    if dash == -1 or (colon != -1 and colon < dash):
        return colon, colon + 1
    return dash, dash + 3


def split_title_parts(
    title: Optional[str],
    subtitle: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Split a title into the main title and an optional subtitle.

    A subtitle the provider supplied is used as given: it is what the edition
    (or the reader) says the second half is. Only when there is none does the
    combined title get split, by the rule that has always decided how a Book is
    presented: a colon or a spaced dash separates the parts, the main title must
    be longer than three characters, and the remainder must say something.
    """
    main = re.sub(r"\s+", " ", str(title or "")).strip()
    given = re.sub(r"\s+", " ", str(subtitle or "")).strip()
    if given:
        return main, given

    span = _separator_span(main)
    if span is None:
        return main, None

    start, end = span
    head = main[:start].strip()
    tail = main[end:].strip()
    if len(head) <= 3 or not tail:
        # "Re: Zero", "10:04" and "Colon:" are titles, not a heading with a
        # subtitle: a prefix that short does not stand on its own.
        return main, None
    return head, tail


def _drop_repeated_subtitle(main: str, second: Optional[str]) -> tuple[str, Optional[str]]:
    """Reduce a main title that still ends with the subtitle beside it."""
    if main and second:
        head, tail = split_title_parts(main)
        if tail and tail.casefold() == second.casefold():
            main = head
    return main, second


def normalise_title_pair(
    title: Optional[str],
    subtitle: Optional[str] = None,
    *,
    infer_subtitle: bool = True,
) -> tuple[str, Optional[str]]:
    """A title and its subtitle as the pair a Book stores, the subtitle once.

    ``infer_subtitle`` reads a combined title as provider text: a provider may
    leave the subtitle inside the title ("Piranesi: A Novel") and also supply
    it beside ("A Novel"), so the title is split and a tail that is that
    subtitle is dropped. A title the rule cannot divide is left as it arrived.

    An edit states both fields itself, so it passes ``infer_subtitle=False``: a
    whole title such as ``Foo Bar: Baz`` stays whole, which is how a wrong split
    is undone. Either way only a title that still ends with the subtitle beside
    it is reduced.
    """
    if infer_subtitle:
        main, second = split_title_parts(title, subtitle)
    else:
        main = re.sub(r"\s+", " ", str(title or "")).strip()
        second = re.sub(r"\s+", " ", str(subtitle or "")).strip() or None
    return _drop_repeated_subtitle(main, second)


def full_title(title: Optional[str], subtitle: Optional[str] = None) -> str:
    """A Book's whole title, as one string: the form exports and the log use."""
    main = str(title or "").strip()
    second = str(subtitle or "").strip()
    return f"{main}: {second}" if main and second else main


def normalize_isbn(isbn: str) -> str:
    """Remove hyphens and other non-digit characters from ISBN, preserving final 'X'."""
    if not isbn:
        return ""
    # Remove hyphens and spaces
    clean = re.sub(r"[\s-]", "", str(isbn))
    # Preserve final X/x, remove all other non-digits
    has_x = clean.lower().endswith("x")
    digits = re.sub(r"\D", "", clean)
    if has_x:
        return digits + "X"
    return digits


def is_valid_isbn13(isbn: str) -> bool:
    """
    Validate ISBN-13 using checksum algorithm and format constraints.
    Reference: https://en.wikipedia.org/wiki/ISBN#ISBN-13_check_digit_calculation
    """
    if len(isbn) != 13 or not isbn.isdigit():
        return False

    checksum = 0
    for index, char in enumerate(isbn[:12]):
        digit = int(char)
        weight = 1 if index % 2 == 0 else 3
        checksum += digit * weight

    check_digit = (10 - (checksum % 10)) % 10
    return check_digit == int(isbn[12])


def parse_publication_year(publish_date: Optional[str]) -> Optional[int]:
    """
    Extract a 4-digit year from various date string formats.
    Examples: '2023', 'May 2023', '2023-05-01'
    """
    if not publish_date:
        return None

    # Split by common delimiters and look for a 4-digit number
    for token in publish_date.replace("-", " ").replace("/", " ").replace(",", " ").split():
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None


def isbn10_to_isbn13(isbn10: str) -> Optional[str]:
    """Convert ISBN-10 to ISBN-13.

    Calculates the checksum for the 978 prefix.
    """
    clean = normalize_isbn(isbn10)
    if len(clean) != 10:
        return None

    # Prefix with 978
    core = "978" + clean[:9]

    # Calculate ISBN-13 checksum
    checksum = 0
    for index, char in enumerate(core):
        digit = int(char)
        weight = 1 if index % 2 == 0 else 3
        checksum += digit * weight

    check_digit = (10 - (checksum % 10)) % 10
    return core + str(check_digit)


def isbn13_to_isbn10(isbn13: str) -> Optional[str]:
    """Convert ISBN-13 to ISBN-10 if possible.

    Only works for ISBN-13s starting with 978.
    For 9798 prefix, returns a 10-digit candidate that Amazon often recognizes.
    """
    clean = normalize_isbn(isbn13)
    if len(clean) != 13:
        return None

    if clean.startswith("978"):
        # Take middle 9 digits
        core = clean[3:12]

        # Calculate ISBN-10 checksum
        total = 0
        for i, digit in enumerate(core):
            total += int(digit) * (10 - i)

        remainder = total % 11
        check_digit = 11 - remainder
        if check_digit == 10:
            check_char = "X"
        elif check_digit == 11:
            check_char = "0"
        else:
            check_char = str(check_digit)

        return core + check_char

    if clean.startswith("9798"):
        # Amazon often uses the middle 10 digits (skipping 979) as an ASIN/ISBN10-like key
        return clean[3:13]

    return None


def parse_bisac_category(bisac: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Split a BISAC category string into (main_category, sub_category).

    Handles formats like:
    - 'FICTION / Science Fiction / General' -> ('FICTION', 'Science Fiction / General')
    - 'Fiction, History' -> ('Fiction', 'History')
    - '823.914' (Dewey) -> ('823.914', None)
    """
    if not bisac:
        return None, None

    bisac_str = str(bisac).strip()
    if not bisac_str:
        return None, None

    # Standard BISAC uses ' / ' or '/'
    if " / " in bisac_str:
        parts = bisac_str.split(" / ", 1)
        return parts[0].strip(), parts[1].strip()
    if "/" in bisac_str:
        parts = bisac_str.split("/", 1)
        return parts[0].strip(), parts[1].strip()

    # Google Books often uses comma separation for multiple categories
    if "," in bisac_str:
        parts = bisac_str.split(",", 1)
        return parts[0].strip(), parts[1].strip()

    return bisac_str, None


UNKNOWN_CATEGORY = "Unknown"

# Category names that should reach the chart with a stable, canonical spelling
# rather than being title-cased ad hoc (and so short ones like "ART" survive the
# language-code filter below).
STABLE_CATEGORIES = {
    "fiction": "FICTION",
    "history": "HISTORY",
    "biography & autobiography": "BIOGRAPHY & AUTOBIOGRAPHY",
    "biography": "BIOGRAPHY & AUTOBIOGRAPHY",
    "autobiography": "BIOGRAPHY & AUTOBIOGRAPHY",
    "science": "SCIENCE",
    "political science": "POLITICAL SCIENCE",
    "literary criticism": "LITERARY CRITICISM",
    "social science": "SOCIAL SCIENCE",
    "computers": "COMPUTERS",
    "philosophy": "PHILOSOPHY",
    "religion": "RELIGION",
    "art": "ART",
    "poetry": "POETRY",
    "drama": "DRAMA",
    "business & economics": "BUSINESS & ECONOMICS",
    "business": "BUSINESS & ECONOMICS",
    "economics": "BUSINESS & ECONOMICS",
    "self-help": "SELF-HELP",
    "psychology": "PSYCHOLOGY",
    "education": "EDUCATION",
    "juvenile fiction": "JUVENILE FICTION",
    "juvenile nonfiction": "JUVENILE NONFICTION",
}

# Values that are not categories at all, whatever field they arrived in.
_NON_CATEGORY_VALUES = {
    "book",
    "books",
    "ebook",
    "e-book",
    "print",
    "audio",
    "unknown",
    "paperback",
    "hardcover",
}


def is_dewey_category(value: object) -> bool:
    """Return True for Dewey-like numeric category values such as '823.914'."""
    if value is None:
        return False

    text = str(value).strip()
    if not text or not any(char.isdigit() for char in text):
        return False
    return all(char.isdigit() or char in "./ " for char in text)


def is_language_code(value: object) -> bool:
    """Return True for short language codes (e.g. 'en', 'eng', 'pt-BR')."""
    if value is None:
        return False

    text = str(value).strip()
    if not text:
        return False
    return bool(re.fullmatch(r"[a-zA-Z]{2,3}(?:[-_][a-zA-Z]{2})?", text))


def normalise_major_bisac(value: object) -> Optional[str]:
    """Extract a valid, canonical major book category, or None when the value
    is not a real category (Dewey numbers, language codes, formats, page counts).
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    main_cat, _ = parse_bisac_category(text)
    if not main_cat:
        return None

    main_cat = main_cat.strip()
    lower_main = main_cat.lower()

    # Reject values that are not categories at all.
    if is_dewey_category(main_cat) or main_cat.isdigit():
        return None
    if lower_main in _NON_CATEGORY_VALUES:
        return None

    # Map known categories to a stable spelling BEFORE the language-code check so
    # short valid names like "ART", "DRAMA" and "POETRY" are not rejected.
    if lower_main in STABLE_CATEGORIES:
        return STABLE_CATEGORIES[lower_main]

    if is_language_code(main_cat):
        return None

    return main_cat.upper()


#: Words a title carries as glue rather than meaning. Title case leaves them
#: lower unless they open or close the title, or follow a colon, dash or
#: opening bracket.
_TITLE_SMALL_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "but",
        "or",
        "nor",
        "for",
        "so",
        "yet",
        "as",
        "at",
        "by",
        "from",
        "in",
        "into",
        "of",
        "off",
        "on",
        "onto",
        "out",
        "over",
        "per",
        "to",
        "up",
        "via",
        "with",
        "vs",
    }
)

#: A dotted form such as "U.S.A." names something, so it is neither re-cased
#: nor stripped of its final full stop.
_DOTTED_ABBREVIATION = re.compile(r"^(?:[A-Za-z]\.){2,}[A-Za-z]?\.?$")

#: A title may end with an abbreviation whose full stop is part of the word, so
#: "Martin Luther King Jr." keeps it. The set is the abbreviations a title
#: carries; a plain word ending the title has its stop removed.
_TITLE_ABBREVIATIONS = frozenset(
    {
        "al",
        "approx",
        "co",
        "corp",
        "dr",
        "ed",
        "eds",
        "etc",
        "fig",
        "figs",
        "inc",
        "jr",
        "ltd",
        "mr",
        "mrs",
        "ms",
        "no",
        "p",
        "pp",
        "prof",
        "rev",
        "sr",
        "st",
        "vol",
        "vs",
    }
)

#: Initials a title carries as initials. Structure cannot tell "CIA" from
#: "WAR", so the ones a Book title uses are named; everything else is read as a
#: shouted word and title-cased.
_TITLE_INITIALISMS = frozenset(
    {
        "AI",
        "API",
        "BBC",
        "CIA",
        "DNA",
        "FBI",
        "HTML",
        "ISBN",
        "NASA",
        "NATO",
        "NHS",
        "TV",
        "UK",
        "USA",
    }
)

#: Roman numerals, which a title writes as numerals rather than as words.
_ROMAN_NUMERALS = frozenset(
    {
        "I",
        "II",
        "III",
        "IV",
        "V",
        "VI",
        "VII",
        "VIII",
        "IX",
        "X",
        "XI",
        "XII",
        "XIII",
        "XIV",
        "XV",
        "XVI",
        "XVII",
        "XVIII",
        "XIX",
        "XX",
        "XXI",
    }
)

#: Characters that end or open a title's part, so the word after them starts a
#: new one and is capitalised even when it is a small word.
_TITLE_BREAK_AFTER = re.compile(r"[:\u2014\u2013(\[]$")
_TITLE_BREAK_BEFORE = re.compile(r"^[\u201c\"'(\[]")


def normalise_provider_title(title: Optional[str]) -> Optional[str]:
    """Tidy a title exactly as a metadata provider supplied it.

    Providers are inconsistent in mechanical ways: an escaped entity, a run of
    spaces, a full stop that only ends the title, an all-caps record beside a
    sentence-cased one. The repair is mechanical and adds no word: a title
    missing a leading "The" is left as it is, because guessing one would name a
    work the provider never described.

    Title case is applied only to a title that carries no case of its own: all
    upper, all lower, or sentence case with nothing capitalised after the first
    letter. A title already cased mixed — "The Lord of the Rings", "iPhone" — is
    the provider's choice and is left exactly as it arrived.

    Call this where a provider's answer is parsed, never on what the reader
    typed: a reader's own title is theirs.
    """
    if title is None:
        return None

    text = re.sub(r"\s+", " ", html.unescape(str(title))).strip()
    if not text:
        return text

    text = _drop_trailing_full_stop(text)
    if _needs_title_case(text):
        text = _title_case(text)
    return text


def _drop_trailing_full_stop(text: str) -> str:
    """Remove a full stop that only terminates the title.

    Other terminal punctuation stands, an ellipsis stands, and an abbreviation
    keeps the full stop that belongs to it: "Martin Luther King Jr." ends in a
    word, not in a stop.
    """
    if not text.endswith(".") or text.endswith(".."):
        return text
    # Check the final token as the provider wrote it: "U.S." is a dotted
    # abbreviation, and testing the token after cutting the dot would leave
    # "U.S", which no longer looks like one.
    if _DOTTED_ABBREVIATION.match(text.split()[-1]):
        return text
    head = text[:-1].rstrip()
    if not head:
        return text
    if re.sub(r"[^A-Za-z]", "", head.split()[-1]).lower() in _TITLE_ABBREVIATIONS:
        return text
    return head


def _needs_title_case(text: str) -> bool:
    """Whether the title carries no casing worth keeping."""
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 2:
        return False
    if all(char.isupper() for char in letters):
        return True
    return all(char.islower() for char in letters[1:])


def _title_case(text: str) -> str:
    words = text.split(" ")
    cased = []
    # A word is capitalised when it opens the title, when the word before it
    # ended with a break, when it opens with a bracket or quote of its own, and
    # when it closes the title.
    after_break = True
    for index, word in enumerate(words):
        last = index == len(words) - 1
        opens_part = after_break or bool(_TITLE_BREAK_BEFORE.match(word))
        cased.append(_case_word(word, force=opens_part or last))
        after_break = bool(_TITLE_BREAK_AFTER.search(word))
    return " ".join(cased)


def _case_word(word: str, force: bool) -> str:
    if not word or _DOTTED_ABBREVIATION.match(word):
        return word
    if "-" in word:
        # Both halves of a hyphenated word are capitalised: "Spider-Man".
        return "-".join(_case_word(part, force=True) for part in word.split("-"))
    if not any(char.isalpha() for char in word):
        return word
    if not force and re.sub(r"[^A-Za-z']", "", word).lower() in _TITLE_SMALL_WORDS:
        return re.sub(r"[A-Za-z]", lambda match: match.group(0).lower(), word)
    if _reads_as_acronym(word):
        return word

    cased = []
    seen_letter = False
    for char in word:
        if not char.isalpha():
            cased.append(char)
            continue
        cased.append(char.upper() if not seen_letter else char.lower())
        seen_letter = True
    return "".join(cased)


def _reads_as_acronym(word: str) -> bool:
    """Whether an all-caps token is written as initials rather than as a word.

    Only a title the provider shouted gives a token caps to preserve, so a
    lower-case "spy" is never mistaken for one. Structure cannot separate an
    initialism from a shouted word — "CIA" and "WAR" differ in nothing a rule
    can see — so the initialisms a title carries are named, along with the
    roman numerals a title writes as numerals ("World War III"). Everything
    else is read as a word: "AN", "IT", "US" and "WE" become "An", "It", "Us"
    and "We".
    """
    if not word.isupper():
        return False
    bare = re.sub(r"[^A-Za-z]", "", word)
    return bare in _TITLE_INITIALISMS or bare in _ROMAN_NUMERALS


def normalise_bisac_category(
    category: object,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return ``(full_category, major_category, sub_category)`` when valid.

    Anything that fails validation collapses to ``(None, None, None)`` so callers
    can fall back to an "Unknown" bucket rather than displaying junk.
    """
    if category is None:
        return None, None, None

    text = str(category).strip()
    if not text:
        return None, None, None

    major, sub_category = parse_bisac_category(text)
    major = normalise_major_bisac(major)
    if not major:
        return None, None, None

    sub_category = sub_category.strip() if sub_category else None
    if sub_category and (is_dewey_category(sub_category) or is_language_code(sub_category) or sub_category.isdigit()):
        sub_category = None

    full_category = f"{major} / {sub_category}" if sub_category else major
    return full_category, major, sub_category


def category_label(value: object) -> str:
    """Return the display label for a category, or "Unknown" when invalid."""
    major = normalise_major_bisac(value)
    if not major:
        return UNKNOWN_CATEGORY
    return major.title() if len(major) > 3 else major.upper()


def category_label_for_book(book: dict) -> str:
    """Return the chart/filter label for a book.

    Prefers the validated ``bisac_main_category`` and falls back to the raw
    ``bisac_category`` so rows written before normalisation still classify.
    """
    major = normalise_major_bisac(book.get("bisac_main_category"))
    if major is None:
        major = normalise_major_bisac(book.get("bisac_category"))
    return category_label(major)


class Category(NamedTuple):
    """A Book's category as it is stored: the full value, and the major category
    and sub-category it is made of.

    The three columns are one fact about a Book, so they travel together. A
    caller that knows only the full value leaves the other two as ``None``;
    :func:`resolve_category` derives them.
    """

    category: Optional[str] = None
    main: Optional[str] = None
    sub: Optional[str] = None

    @classmethod
    def from_fields(
        cls,
        category: Optional[str],
        main: Optional[str] = None,
        sub: Optional[str] = None,
    ) -> "Category":
        """Build the triple from the separate values a write carries."""
        return cls(category, main, sub)

    @classmethod
    def from_mapping(cls, book: Mapping[str, Any]) -> "Category":
        """Read the triple from a stored Book row or an incoming payload."""
        return cls(
            book.get("bisac_category"),
            book.get("bisac_main_category"),
            book.get("bisac_sub_category"),
        )


def resolve_category(incoming: Category, existing: Category) -> Category:
    """Return the category to store when ``incoming`` is written over ``existing``.

    The rule is one sentence long: a Dewey code never displaces a stored
    category, and anything else incoming wins outright. A Dewey code — or
    nothing at all — may only fill a gap, which is what stops the enrichment
    backfill from undoing a real category with a raw classification number.

    The winner's main and sub come from ``incoming`` where it supplies them, and
    are otherwise derived from the winning value, so the three columns cannot
    disagree about what the Book is. The derivation never rewrites the winning
    value itself; it only fills the pair beside it.
    """
    winner = (incoming.category or "").strip()

    if not winner:
        # Nothing incoming: the stored triple stands.
        return Category(existing.category, existing.main or incoming.main, existing.sub or incoming.sub)

    if is_dewey_category(winner) and existing.category:
        # A classification number, with a real category there to protect.
        return existing

    _, derived_main, derived_sub = normalise_bisac_category(winner)
    return Category(winner, incoming.main or derived_main, incoming.sub or derived_sub)
