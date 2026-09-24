"""Book Lamp application factory."""

import gzip
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, request

from book_lamp.middleware.csrf import add_csrf_token_header
from book_lamp.routes import register_blueprints
from book_lamp.services.storage_factory import is_test_mode

load_dotenv()

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")

COMPRESSIBLE_MIMETYPES = {
    "application/javascript",
    "application/json",
    "image/svg+xml",
    "text/css",
    "text/html",
}


def configure_compression(app: Flask) -> None:
    """Gzip-compress compressible responses when the client supports it.

    The Flask dev/test server does not compress on its own, which left the
    SPA bundle (~240KB) and stylesheets uncompressed for Lighthouse CI.
    """

    @app.after_request
    def compress_response(response):
        if response.status_code != 200 or response.direct_passthrough:
            return response
        if response.mimetype not in COMPRESSIBLE_MIMETYPES:
            return response
        if response.headers.get("Content-Encoding"):
            return response
        if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
            return response
        response.direct_passthrough = False
        data = response.get_data()
        if len(data) < 1024:
            return response
        compressed = gzip.compress(data, compresslevel=6)
        if len(compressed) >= len(data):
            return response
        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers.add("Vary", "Accept-Encoding")
        return response


def configure_logging() -> None:
    """Initialise structured application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    logging.getLogger("book_lamp").setLevel(logging.INFO)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def create_app(test_config: Optional[dict] = None) -> Flask:
    """Flask application factory."""
    configure_logging()

    app = Flask(
        __name__,
        static_folder="static",
    )

    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key and not is_test_mode():
        raise ValueError(
            "SECRET_KEY environment variable is required. "
            "Please set it in your .env file."
        )
    elif not secret_key:
        secret_key = "test-only-insecure-key-do-not-use-in-production"

    app.config["SECRET_KEY"] = secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = not is_test_mode()
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID")
    app.config["APP_VERSION"] = APP_VERSION

    if test_config:
        app.config.update(test_config)

    # Middleware
    app.after_request(add_csrf_token_header)
    configure_compression(app)

    # Register all modular Blueprints
    register_blueprints(app)

    return app
