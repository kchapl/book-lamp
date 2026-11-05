"""Deployment information the About page reports."""

import os

from flask import Blueprint, jsonify

app_info_bp = Blueprint("app_info", __name__)

# Hosts name the deployed commit under their own variable. The short hash is
# what a reader can compare against a release.
VERSION_ENV_VARS = ("RENDER_GIT_COMMIT", "GIT_COMMIT", "HEROKU_SLUG_COMMIT")


def deployed_version() -> str:
    """The version of the code answering this request.

    Read per request rather than at import, so a host that sets the commit only
    once the process starts still reports it.
    """
    for env_var in VERSION_ENV_VARS:
        commit = os.environ.get(env_var)
        if commit:
            return commit[:7]
    return os.environ.get("APP_VERSION", "dev")


@app_info_bp.route("/api/app-info", methods=["GET"])
def app_info():
    """Return the version serving this request.

    The About page is reachable without a session, like the legal pages, so
    this reads nothing from the session.
    """
    return jsonify({"version": deployed_version()})
