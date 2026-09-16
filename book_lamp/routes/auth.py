"""Authentication and CSRF routes."""

import secrets
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from book_lamp.middleware.csrf import generate_csrf_token
from book_lamp.services.pg_storage import PostgresStorage
from book_lamp.services.storage_factory import is_test_mode

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/csrf-token", methods=["GET"])
def get_csrf_token():
    """Return CSRF token for client API requests."""
    token = generate_csrf_token()
    response = jsonify({"csrf_token": token})
    response.set_cookie("csrf_token", token, samesite="Lax")
    return response


@auth_bp.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Return current session authentication status and configuration."""
    user_id = session.get("user_id")
    is_authenticated = bool(user_id) or is_test_mode()
    google_client_id = current_app.config.get("GOOGLE_CLIENT_ID") or ""

    user_info = None
    if user_id:
        user_info = {
            "id": user_id,
            "email": session.get("user_email", ""),
            "name": session.get("user_name", ""),
        }

    return jsonify(
        {
            "is_authenticated": is_authenticated,
            "user": user_info,
            "google_client_id": google_client_id,
        }
    )


@auth_bp.route("/api/auth/google", methods=["POST"])
def google_one_tap_login():
    """Verify a Google One Tap credential JWT and create a session."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential:
        return jsonify({"error": "Missing credential"}), 400

    try:
        id_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            current_app.config["GOOGLE_CLIENT_ID"],
        )
        email = id_info["email"]
        name = id_info.get("name", "")

        user_id = PostgresStorage.upsert_user(email=email, name=name)

        session.clear()
        session["user_id"] = user_id
        session["user_email"] = email
        session["user_name"] = name
        session["csrf_token"] = secrets.token_hex(32)

        current_app.logger.info(f"Authentication successful for user: {email}")
        return jsonify({"ok": True})
    except ValueError as e:
        current_app.logger.exception(f"One Tap credential verification failed: {e}")
        current_app.logger.warning(f"Authentication failure: {e}")
        return jsonify({"error": "Invalid credential"}), 401


@auth_bp.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """Sign out the current user and clear session."""
    session.clear()
    session.permanent = False
    return jsonify({"ok": True})


@auth_bp.route("/logout", methods=["GET"])
def logout():
    """Sign out the user and redirect to homepage."""
    session.clear()
    session.permanent = False
    return redirect(url_for("spa.spa_index"))
