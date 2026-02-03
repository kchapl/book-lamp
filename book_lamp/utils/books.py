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
