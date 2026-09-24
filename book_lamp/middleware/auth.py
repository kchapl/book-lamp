"""Authentication and authorisation middleware."""

from functools import wraps

from flask import current_app, jsonify, redirect, request, session, url_for

from book_lamp.services.storage_factory import get_storage, is_test_mode


def authorisation_required(f):
    """Decorator to require authenticated user session."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_app.logger.info(f"AUTHORISATION_CHECK for route: {f.__name__}")

        user_id = session.get("user_id")
        if not user_id and not is_test_mode():
            current_app.logger.warning(
                f"Authorisation failed for {f.__name__}: no user_id in session"
            )
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("spa.spa_page", fallback="unauthorised"))

        if not get_storage().is_authorised():
            current_app.logger.warning(
                f"Authorisation failed for {f.__name__}: storage not authorised"
            )
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("spa.spa_page", fallback="unauthorised"))
        return f(*args, **kwargs)

    return decorated_function
