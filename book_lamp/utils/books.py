import re
from typing import Optional


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


def resolve_broad_category(
    bisac: Optional[str] = None,
    dewey: Optional[str] = None,
    subjects: Optional[list[str]] = None,
) -> str:
    """
    Resolve a standardized broad category from various metadata inputs.
    Prioritizes: 1. DDC (most objective), 2. BISAC, 3. Subject keywords.
    """

    def clean(s: Optional[str]) -> str:
        return s.strip().upper() if s else ""

    # 1. Handle Dewey Decimal Classification (DDC)
    if dewey:
        # Extract the first 3 digits
        match = re.search(r"(\d{3})", dewey)
        if match:
            code = int(match.group(1))
            if dewey.startswith(("004", "005", "006")):
                return "Technology & Engineering"
            if 0 <= code <= 99:
                return "Reference & General"
            if 100 <= code <= 299:
                return "Philosophy & Religion"
            if 300 <= code <= 399:
                return "Social Sciences"
            if 400 <= code <= 499:
                return "Literature & Language"
            if 500 <= code <= 599:
                return "Science & Nature"
            if 600 <= code <= 699:
                if 610 <= code <= 619:
                    return "Health & Wellness"
                return "Technology & Engineering"
            if 700 <= code <= 799:
                return "Arts & Design"
            if 800 <= code <= 899:
                return "Literature & Language"
            if code == 920:
                return "Biography & Memoir"
            if 910 <= code <= 919:
                return "Travel & Geography"
            if 900 <= code <= 999:
                return "History"

    # 2. Handle BISAC
    from book_lamp.utils.books import parse_bisac_category

    main_bisac, _ = parse_bisac_category(bisac)
    main_bisac = clean(main_bisac)

    bisac_map = {
        "FICTION": "Fiction",
        "BIOGRAPHY & AUTOBIOGRAPHY": "Biography & Memoir",
        "HISTORY": "History",
        "PHILOSOPHY": "Philosophy & Religion",
        "RELIGION": "Philosophy & Religion",
        "SCIENCE": "Science & Nature",
        "NATURE": "Science & Nature",
        "COMPUTERS": "Technology & Engineering",
        "TECHNOLOGY & ENGINEERING": "Technology & Engineering",
        "SOCIAL SCIENCE": "Social Sciences",
        "POLITICAL SCIENCE": "Social Sciences",
        "ECONOMICS": "Social Sciences",  # Could be Business & Finance, but often academic
        "ART": "Arts & Design",
        "DESIGN": "Arts & Design",
        "MUSIC": "Arts & Design",
        "ARCHITECTURE": "Arts & Design",
        "POETRY": "Literature & Language",
        "LITERARY CRITICISM": "Literature & Language",
        "DRAMA": "Literature & Language",
        "LANGUAGE ARTS & DISCIPLINES": "Literature & Language",
        "COOKING": "Health & Wellness",
        "HEALTH & FITNESS": "Health & Wellness",
        "SELF-HELP": "Health & Wellness",
        "PSYCHOLOGY": "Philosophy & Religion",
        "TRAVEL": "Travel & Geography",
        "BUSINESS & ECONOMICS": "Business & Finance",
        "JUVENILE FICTION": "Children & Young Adult",
        "JUVENILE NONFICTION": "Children & Young Adult",
        "YOUNG ADULT FICTION": "Children & Young Adult",
        "YOUNG ADULT NONFICTION": "Children & Young Adult",
        "REFERENCE": "Reference & General",
    }

    if main_bisac in bisac_map:
        return bisac_map[main_bisac]

    # 3. Handle Subject Keywords
    all_subjects = [clean(s) for s in (subjects or [])]
    if bisac:
        all_subjects.append(clean(bisac))

    keyword_map = {
        "FICTION": "Fiction",
        "BIOGRAPHY": "Biography & Memoir",
        "MEMOIR": "Biography & Memoir",
        "AUTOBIOGRAPHY": "Biography & Memoir",
        "HISTORY": "History",
        "PHILOSOPHY": "Philosophy & Religion",
        "RELIGION": "Philosophy & Religion",
        "SCIENCE": "Science & Nature",
        "NATURE": "Science & Nature",
        "TECHNOLOGY": "Technology & Engineering",
        "ENGINEERING": "Technology & Engineering",
        "COMPUTER": "Technology & Engineering",
        "SOCIAL SCIENCE": "Social Sciences",
        "POLITICS": "Social Sciences",
        "SOCIOLOGY": "Social Sciences",
        "ART": "Arts & Design",
        "MUSIC": "Arts & Design",
        "DESIGN": "Arts & Design",
        "POETRY": "Literature & Language",
        "LITERATURE": "Literature & Language",
        "CLASSICS": "Literature & Language",
        "COOKING": "Health & Wellness",
        "HEALTH": "Health & Wellness",
        "SELF-HELP": "Health & Wellness",
        "TRAVEL": "Travel & Geography",
        "GEOGRAPHY": "Travel & Geography",
        "BUSINESS": "Business & Finance",
        "FINANCE": "Business & Finance",
        "ECONOMY": "Business & Finance",
        "CHILDREN": "Children & Young Adult",
        "YOUNG ADULT": "Children & Young Adult",
        "JUVENILE": "Children & Young Adult",
    }

    for subject in all_subjects:
        for kw, cat in keyword_map.items():
            if kw in subject:
                return cat

    return "Other"
