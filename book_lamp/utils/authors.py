"""Utilities for handling author names and multi-author strings."""

from typing import List


def split_authors(author_str: str) -> List[str]:
    """Split a string containing one or more authors into a list.

    Handles separators like:
    - Comma (if not used for "Last, First")
    - Semicolon (common for multiple "Last, First" entries)
    - " and "
    - " & "

    Args:
        author_str: The string to split.

    Returns:
        List of clean individual author names.
    """
    if not author_str:
        return []

    # If it contains semicolons, assume that's the primary separator
    # (often used to separate "Last, First" entries)
    if ";" in author_str:
        parts = [p.strip() for p in author_str.split(";") if p.strip()]
        return parts

    # Normalise common separators to a temporary unique token
    # We replace " and " and " & " with something unique
    # We don't replace commas yet because of "Last, First"
    s = author_str.replace(" and ", " || ").replace(" & ", " || ")

    # If there are multiple commas, it might be multiple authors
    # OR it could be "Last, First" with titles etc.
    # A common pattern for multiple authors is "Author A, Author B, and Author C"
    # After our " and " replacement, it becomes "Author A, Author B || Author C"

    # Split by the token first
    parts = s.split(" || ")

    final_authors = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # If a part still contains commas, we need to decide if it's multiple
        # authors or just "Last, First".
        # Heuristic: If there's only one comma, assume "Last, First".
        # If there are multiple, it might be a list.
        if "," in part:
            comma_count = part.count(",")
            if comma_count > 1:
                # Likely a list of authors
                sub_parts = [sp.strip() for sp in part.split(",") if sp.strip()]
                final_authors.extend(sub_parts)
            else:
                # Likely "Last, First"
                final_authors.append(part)
        else:
            final_authors.append(part)

    return [a for a in final_authors if a]
