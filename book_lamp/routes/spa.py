"""SPA routing and static assets serving."""

import os
from flask import Blueprint, Response, current_app, redirect, request, send_from_directory, url_for

spa_bp = Blueprint("spa", __name__)

SPA_SHELL_MESSAGE = "SPA build missing: run 'npm run build' and retry."


def _serve_spa():
    """Serve the React SPA entry point."""
    static_folder = current_app.static_folder or "static"
    react_index = os.path.join(static_folder, "react", "index.html")
    if os.path.exists(react_index):
        return send_from_directory(os.path.join(static_folder, "react"), "index.html")
    return Response(SPA_SHELL_MESSAGE, status=503, mimetype="text/plain")


@spa_bp.route("/", methods=["GET"])
def spa_index():
    """Root route - serves the React SPA."""
    return _serve_spa()


@spa_bp.route("/connect", methods=["GET"])
def connect():
    """Redirect connect requests to the home SPA view."""
    return redirect(url_for("spa.spa_index"))


@spa_bp.route("/favicon.ico", methods=["GET"])
def favicon():
    """Serve favicon from static folder."""
    static_folder = current_app.static_folder or "static"
    return send_from_directory(
        static_folder, "favicon.png", mimetype="image/png"
    )


@spa_bp.route("/<path:fallback>", methods=["GET"])
def spa_page(fallback: str):
    """Catch-all for SPA client routing."""
    if request.path.startswith("/api/"):
        return {"error": "Not found"}, 404
    return _serve_spa()
