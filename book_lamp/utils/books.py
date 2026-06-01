import re
from typing import Optional

UNKNOWN_CATEGORY = "Unknown"


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
    for token in (
        publish_date.replace("-", " ").replace("/", " ").replace(",", " ").split()
    ):
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


def is_dewey_category(value: object) -> bool:
    """Return True for Dewey-like numeric category values."""
    if value is None:
        return False

    text = str(value).strip()
    if not text:
        return False

    # Dewey values are mostly digits with dots/slashes/spaces.
    if not any(char.isdigit() for char in text):
        return False
    return all(char.isdigit() or char in "./ " for char in text)


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


def is_language_code(value: object) -> bool:
    """Return True for short language codes that are not book categories."""
    if value is None:
        return False

    text = str(value).strip()
    if not text:
        return False

    return bool(re.fullmatch(r"[a-zA-Z]{2,3}(?:[-_][a-zA-Z]{2})?", text))


def normalise_major_bisac(value: object) -> Optional[str]:
    """Extract a valid, displayable major book category."""
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

    # Reject Dewey-like numeric category values first
    if is_dewey_category(main_cat):
        return None

    # Reject page-count-like values (digits only)
    if main_cat.isdigit():
        return None

    # Reject physical-format-like values
    if lower_main in {
        "book",
        "books",
        "ebook",
        "e-book",
        "print",
        "audio",
        "unknown",
        "paperback",
        "hardcover",
    }:
        return None

    # Normalize accepted labels to stable display categories BEFORE language code check
    # so short valid categories like "ART", "DRAMA", "POETRY" are not rejected.
    if lower_main in STABLE_CATEGORIES:
        return STABLE_CATEGORIES[lower_main]

    # Reject language codes (e.g. "en", "fr", "eng") only if not a known category
    if is_language_code(main_cat):
        return None

    # Fallback to uppercase for other valid categories to keep consistent standard
    return main_cat.upper()


def normalise_bisac_category(
    category: object,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (full_category, major_category, sub_category) when valid."""
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
    if sub_category and (
        is_dewey_category(sub_category)
        or is_language_code(sub_category)
        or sub_category.isdigit()
    ):
        sub_category = None

    full_category = f"{major} / {sub_category}" if sub_category else major
    return full_category, major, sub_category


def category_label(value: object) -> str:
    """Return the normalized chart/filter label for a category value."""
    major = normalise_major_bisac(value)
    if not major:
        return UNKNOWN_CATEGORY
    return major.title() if len(major) > 3 else major.upper()
