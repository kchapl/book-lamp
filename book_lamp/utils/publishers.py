"""Publisher string normalization utilities."""

import re


def normalize_publisher(name: str) -> str:
    """Normalize publisher names by stripping legal and corporate suffixes."""
    if not name:
        return ""
    suffixes = [
        r"\bbooks\b",
        r"\blimited\b",
        r"\bltd\.?\b",
        r"\binc\.?\b",
        r"\bllc\b",
        r"\bpublishers?\b",
        r"\bpublishing\b",
        r"\bpress\b",
        r"\bgroup\b",
        r"\bcompany\b",
        r"\bco\.?\b",
    ]
    pattern = re.compile("|".join(suffixes), flags=re.IGNORECASE)
    cleaned = pattern.sub("", name)
    cleaned = re.sub(r"[,.;:]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return name.strip()
    return cleaned
