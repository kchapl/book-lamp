"""CSRF protection middleware and helpers."""

import secrets
from functools import wraps

from flask import current_app, g, jsonify, request, session

from book_lamp.services.storage_factory import is_test_mode


def generate_csrf_token() -> str:
    """Generate or retrieve a CSRF token for the current session."""
    if "csrf_token" not in session:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    else:
        token = session["csrf_token"]
    g.csrf_token = token
    return token


def csrf_protect(f):
    """Decorator to protect routes from CSRF attacks."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if is_test_mode() or not session.get("user_id"):
                return f(*args, **kwargs)

            submitted_token = request.headers.get("X-CSRF-Token") or request.form.get(
                "csrf_token"
            )
            session_token = session.get("csrf_token")
            if not session_token or submitted_token != session_token:
                current_app.logger.warning(
                    f"CSRF validation failed for {request.endpoint}: "
                    f"submitted={submitted_token[:8] if submitted_token else 'None'}, "
                    f"session={session_token[:8] if session_token else 'None'}"
                )
                return jsonify({"error": "CSRF token validation failed"}), 403
        return f(*args, **kwargs)

    return decorated_function


def add_csrf_token_header(response):
    """Add CSRF token to response headers if generated during request."""
    if hasattr(g, "csrf_token"):
        response.headers["X-CSRF-Token"] = g.csrf_token
    elif "csrf_token" in session:
        response.headers["X-CSRF-Token"] = session["csrf_token"]
    return response
