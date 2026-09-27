"""URL and safe redirect utilities."""

from urllib.parse import urlparse
from flask import request, url_for


def get_safe_redirect_target(fallback_endpoint: str) -> str:
    """Return a safe redirect target derived from the request referrer.

    If the referrer is an absolute URL, only accept it if it points to the
    same host as the current request. Otherwise, or if no referrer is set,
    fall back to the URL for the given endpoint.
    """
    referrer = request.referrer
    if referrer:
        normalized = referrer.replace("\\", "/")
        parsed = urlparse(normalized)
        if not parsed.scheme and not parsed.netloc:
            return normalized
        if parsed.scheme in ("http", "https") and parsed.netloc == request.host:
            return normalized
    return url_for(fallback_endpoint)
