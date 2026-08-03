import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from extensions import db
from models.bc import BiomedicalConcept
from services import bc_service
from services.ncit_api import NCItApiClient

logger = logging.getLogger(__name__)

bp = Blueprint("ncit", __name__)


@bp.route("/")
def index():
    return redirect(url_for("ncit.mapping"))


@bp.route("/mapping")
def mapping():
    # Surface BCs that have no NCIt code yet — these need manual resolution
    unresolved = BiomedicalConcept.query.filter((BiomedicalConcept.ncit_code == None) | (BiomedicalConcept.ncit_code == "")).limit(50).all()
    return render_template(
        "ncit_mapping.html",
        unresolved=unresolved,
        results=[],
        search_term="",
        page_title="NCIt Mapping",
    )


@bp.route("/search")
def search_ncit():
    term = request.args.get("term", "").strip()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.args.get("format") == "json" or "application/json" in request.headers.get("Accept", "")
    if not term:
        if is_ajax:
            return jsonify([])
        return render_template(
            "ncit_mapping.html",
            results=[],
            search_term="",
            unresolved=[],
            page_title="NCIt Mapping",
        )

    client = NCItApiClient()
    results = client.search_concept(term, size=10)

    if is_ajax:
        return jsonify(results)

    unresolved = BiomedicalConcept.query.filter((BiomedicalConcept.ncit_code == None) | (BiomedicalConcept.ncit_code == "")).limit(50).all()
    return render_template(
        "ncit_mapping.html",
        results=results,
        search_term=term,
        unresolved=unresolved,
        page_title="NCIt Mapping",
    )


@bp.route("/concept/<ncit_code>")
def concept_detail(ncit_code):
    """Return full NCIt concept details as JSON."""
    client = NCItApiClient()
    result = client.get_concept(ncit_code)
    if "error" in result:
        from flask import abort

        abort(404)
    return jsonify(result)


@bp.route("/resolve/<bc_id>", methods=["POST"])
def resolve(bc_id):
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    ncit_code = request.form.get("ncit_code", "").strip()
    if ncit_code:
        bc = bc_service.map_ncit_to_bc(bc_id, ncit_code, actor="user")
        flash(f"NCIt mapping updated for {bc.short_name}", "success")
    return redirect(url_for("ncit.mapping"))
