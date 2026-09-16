"""Blueprint registration for Book Lamp."""

from flask import Flask

from book_lamp.routes.auth import auth_bp
from book_lamp.routes.authors import authors_bp
from book_lamp.routes.books import books_bp
from book_lamp.routes.jobs import jobs_bp
from book_lamp.routes.reading_list import reading_list_bp
from book_lamp.routes.reading_records import reading_records_bp
from book_lamp.routes.recommendations import recommendations_bp
from book_lamp.routes.spa import spa_bp
from book_lamp.routes.stats import stats_bp
from book_lamp.routes.testing import testing_bp
from book_lamp.services.storage_factory import is_test_mode


def register_blueprints(app: Flask) -> None:
    """Register all application blueprints with the Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(reading_records_bp)
    app.register_blueprint(reading_list_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(authors_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(recommendations_bp)

    if is_test_mode():
        app.register_blueprint(testing_bp)

    # Register SPA fallback last so specific routes take precedence
    app.register_blueprint(spa_bp)
