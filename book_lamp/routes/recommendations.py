from flask import Blueprint, jsonify

from book_lamp.web.common import authorisation_required, get_llm_client, get_storage

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.route("/api/recommendations", methods=["GET"])
@authorisation_required
def api_recommendations():
    """Return (possibly cached) AI book recommendations as JSON."""
    from book_lamp.services.recommendations import get_or_refresh_recommendations

    storage = get_storage()
    llm = get_llm_client()

    if not llm.client:
        return (
            jsonify({"recommendations": [], "error": "LLM_API_KEY not configured"}),
            200,
        )

    try:
        recs = get_or_refresh_recommendations(storage, llm)
        return jsonify({"recommendations": recs})
    except Exception:
        from flask import current_app

        current_app.logger.exception("Failed to generate recommendations")
        return (
            jsonify(
                {"recommendations": [], "error": "Failed to generate recommendations"}
            ),
            200,
        )
