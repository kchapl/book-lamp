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
