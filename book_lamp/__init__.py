"""Book Lamp application factory."""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from flask import Flask

from book_lamp.middleware.csrf import add_csrf_token_header
from book_lamp.routes import register_blueprints
from book_lamp.services.storage_factory import is_test_mode

load_dotenv()

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")


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

    # Register all modular Blueprints
    register_blueprints(app)

    return app
