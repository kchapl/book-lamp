"""Covers a provider serves in place of a missing one (#379).

A provider can answer with an image even when it has no cover for an edition:
the Penguin Random House cover service replies ``200 image/jpeg`` with the same
"Cover Coming Soon" card for every ISBN it has no art for. The URL has the same
shape as a real cover, so the placeholder is recognised by its bytes.

An entry in :data:`PLACEHOLDER_DIGESTS` names a host and the SHA-256 digests of
the images it serves as placeholders. Only hosts named there are ever fetched
for fingerprinting: a cover anywhere else is an answer without a download.

Nothing is stored between runs. A verdict belongs to the run that asked for it,
and a later run asks again.
"""

import hashlib
import logging
import threading
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger("book_lamp")

#: The SHA-256 of each image a host serves as a placeholder. A digest is the
#: only reliable identity: the URL cannot tell a placeholder from a cover.
PLACEHOLDER_DIGESTS = {
    "images.penguinrandomhouse.com": frozenset(
        {
            "90feff7dbf2b0c3fc09013279aecb50156183ab074a2f8ba99fe0021a4ab8459",
        }
    ),
}

#: The hosts whose images may be placeholders, in a stable order.
PLACEHOLDER_HOSTS = tuple(PLACEHOLDER_DIGESTS)

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Get or create the session the fingerprint downloads use."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(
            {
                "User-Agent": "BookLamp/1.0 (personal reading tracker; https://github.com/book-lamp)",
            }
        )
    return _session


def _host_of(url: str) -> Optional[str]:
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


class CoverFingerprints:
    """Whether cover URLs serve a registered placeholder, memoised per URL.

    One instance belongs to one run: a URL needed twice is downloaded once, and
    a failed download is remembered as "not known to be a placeholder" rather
    than retried for every Book that shares the URL.
    """

    def __init__(self, session_factory: Callable[[], Any] = _get_session) -> None:
        self._session_factory = session_factory
        self._verdicts: dict[str, bool] = {}
        self._url_locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def is_placeholder(self, url: object) -> bool:
        """Whether the bytes at ``url`` are a registered placeholder.

        A host outside the registry is answered without a request: nothing else
        in the collection costs an extra fetch.
        """
        if not isinstance(url, str) or not url.strip():
            return False
        url = url.strip()
        host = _host_of(url)
        if host not in PLACEHOLDER_DIGESTS:
            return False

        with self._guard:
            if url in self._verdicts:
                return self._verdicts[url]
            url_lock = self._url_locks.setdefault(url, threading.Lock())

        with url_lock:
            with self._guard:
                if url in self._verdicts:
                    return self._verdicts[url]
            verdict = self._download_and_check(url, host)
            with self._guard:
                self._verdicts[url] = verdict
            return verdict

    def is_placeholder_bytes(self, url: str, content: bytes) -> bool:
        """Record and answer a verdict from bytes already downloaded.

        The cover lookup has the image in hand, so it must not download it a
        second time to fingerprint it.
        """
        url = url.strip()
        host = _host_of(url)
        if host not in PLACEHOLDER_DIGESTS:
            return False
        verdict = hashlib.sha256(content).hexdigest() in PLACEHOLDER_DIGESTS[host]
        with self._guard:
            self._verdicts[url] = verdict
        return verdict

    def _download_and_check(self, url: str, host: str) -> bool:
        try:
            response = self._session_factory().get(url, timeout=10)
            response.raise_for_status()
            content = response.content
        except Exception as exc:
            logger.debug(f"Cover fingerprint failed for {url}: {exc}")
            return False
        return hashlib.sha256(content).hexdigest() in PLACEHOLDER_DIGESTS[host]
