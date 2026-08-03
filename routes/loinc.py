import logging

from flask import Blueprint, jsonify, request

from services.loinc_api import LoincApiClient

logger = logging.getLogger(__name__)

bp = Blueprint("loinc", __name__)


@bp.route("/search")
def search():
    term = request.args.get("term", "").strip()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.args.get("format") == "json" or "application/json" in request.headers.get("Accept", "")
    if not term:
        if is_ajax:
            return jsonify([])
        return jsonify([])

    client = LoincApiClient()
    results = client.search(term, size=10)
    return jsonify(results)
