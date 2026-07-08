import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from extensions import db
from models.bc import BiomedicalConcept, DataElementConcept
from models.governance import GovernanceRecord
from services import bc_service
from services.audit import log_change
from services.cdisc_api import CDISCApiClient
from services.export import export_json, export_odm_xml, export_xlsx
from services.loinc_api import LoincApiClient
from services.ncit_api import NCItApiClient

logger = logging.getLogger(__name__)

bp = Blueprint("bc", __name__)


@bp.route("/")
def index():
    q = request.args.get("q", "")
    status = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    query = BiomedicalConcept.query
    if q:
        query = query.filter(BiomedicalConcept.short_name.ilike(f"%{q}%") | BiomedicalConcept.bc_id.ilike(f"%{q}%") | BiomedicalConcept.ncit_code.ilike(f"%{q}%"))
    if status:
        query = query.filter_by(status=status)
    bcs = query.order_by(BiomedicalConcept.updated_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template(
        "bc_list.html",
        bcs=bcs,
        q=q,
        status=status,
        page_title="Biomedical Concepts",
    )


@bp.route("/new")
def new_bc():
    bc = BiomedicalConcept()
    ncit_code = request.args.get("ncit_code", "").strip()
    if ncit_code:
        bc.bc_id = ncit_code
        bc.ncit_code = ncit_code
        bc.short_name = request.args.get("ncit_name", "").strip()
        bc.definition = request.args.get("ncit_definition", "").strip()
    return render_template(
        "bc_detail.html",
        bc=bc,
        decs=[],
        is_new=True,
        loinc_data={},
        ncit_data={},
        page_title="New Biomedical Concept",
    )


@bp.route("/export")
def export():
    fmt = request.args.get("format", "json")
    bcs = [bc.to_dict() for bc in BiomedicalConcept.query.all()]
    if fmt == "xlsx":
        buf = export_xlsx(bcs)
        return Response(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=bcs.xlsx"},
        )
    elif fmt == "odm":
        xml = export_odm_xml(bcs)
        return Response(
            xml,
            mimetype="application/xml",
            headers={"Content-Disposition": "attachment; filename=bcs_odm.xml"},
        )
    else:
        return Response(
            export_json(bcs),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=bcs.json"},
        )


@bp.route("/library/<concept_id>")
def library_detail(concept_id):
    client = CDISCApiClient()
    bc = client.get_bc(concept_id)
    if "error" in bc:
        flash(f'Could not load concept {concept_id}: {bc["error"]}', "danger")
        return redirect(url_for("dashboard.index"))

    # Look for a LOINC coding entry in the CDISC API response
    loinc_code = None
    for c in bc.get("coding", []):
        if (c.get("systemName") or "").upper() == "LOINC" and c.get("code"):
            loinc_code = c["code"]
            break

    loinc_data = {}
    if loinc_code:
        results = LoincApiClient().search(loinc_code, size=1)
        if results and not results[0].get("error"):
            loinc_data = results[0]

    return render_template(
        "library_bc_detail.html",
        bc=bc,
        loinc_data=loinc_data,
        page_title=bc.get("shortName") or bc.get("name") or concept_id,
    )


@bp.route("/<bc_id>")
def detail(bc_id):
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    decs = DataElementConcept.query.filter_by(bc_id=bc_id).order_by(DataElementConcept.sort_order).all()
    loinc_data = {}
    if bc.loinc_metadata:
        try:
            loinc_data = json.loads(bc.loinc_metadata)
        except (ValueError, TypeError):
            pass
    elif bc.loinc_code:
        results = LoincApiClient().search(bc.loinc_code, size=1)
        if results and not results[0].get("error"):
            loinc_data = results[0]
            bc.loinc_metadata = json.dumps(loinc_data)
            db.session.commit()

    ncit_data = {}
    if bc.ncit_metadata:
        try:
            ncit_data = json.loads(bc.ncit_metadata)
        except (ValueError, TypeError):
            pass

    return render_template(
        "bc_detail.html",
        bc=bc,
        decs=decs,
        is_new=False,
        loinc_data=loinc_data,
        ncit_data=ncit_data,
        needs_ncit_fetch=not ncit_data and bool(bc.ncit_code),
        needs_loinc_fetch=not loinc_data and bool(bc.loinc_code),
        page_title=bc.short_name,
    )


@bp.route("/<bc_id>/fetch-metadata")
def fetch_metadata(bc_id):
    """Fetch LOINC and NCIt data concurrently for a BC that has no stored metadata yet.
    Saves results to the DB so subsequent visits use the fast stored-metadata path."""
    from flask import jsonify

    bc = db.get_or_404(BiomedicalConcept, bc_id)

    def _fetch_ncit():
        result = NCItApiClient().get_concept(bc.ncit_code)
        return result if not result.get("error") else {}

    ncit_data = {}
    if bc.ncit_code:
        ncit_data = _fetch_ncit()

    if ncit_data and not bc.ncit_metadata:
        bc.ncit_metadata = json.dumps(ncit_data)
        db.session.commit()

    loinc_data = {}
    if bc.loinc_code and not bc.loinc_metadata:
        results = LoincApiClient().search(bc.loinc_code, size=1)
        if results and not results[0].get("error"):
            loinc_data = results[0]
            bc.loinc_metadata = json.dumps(loinc_data)
            db.session.commit()

    return jsonify(ncit=ncit_data, loinc=loinc_data)


@bp.route("/", methods=["POST"])
def create():
    try:
        bc = bc_service.create_bc(request.form)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("bc.new_bc"))
    bc_service.save_decs(bc.bc_id, _decs_from_form(request.form))
    flash(f"BC {bc.bc_id} created", "success")
    return redirect(url_for("bc.detail", bc_id=bc.bc_id))


@bp.route("/<bc_id>/edit", methods=["POST"])
def edit(bc_id):
    db.get_or_404(BiomedicalConcept, bc_id)
    bc_service.update_bc(bc_id, request.form, actor="user")
    bc_service.save_decs(bc_id, _decs_from_form(request.form))
    flash(f"BC {bc_id} updated", "success")
    return redirect(url_for("bc.detail", bc_id=bc_id))


@bp.route("/<bc_id>/clear-ncit", methods=["POST"])
def clear_ncit(bc_id):
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    before = bc.to_dict()
    bc.ncit_code = None
    bc.ncit_metadata = None
    bc.parent_bc_id = None
    bc.updated_at = datetime.now(timezone.utc)
    log_change("BiomedicalConcept", bc_id, "ncit_cleared", actor="user", before=before, after=bc.to_dict())
    db.session.commit()
    flash(f"NCIt code cleared from {bc_id}", "success")
    return redirect(url_for("bc.detail", bc_id=bc_id))


@bp.route("/<bc_id>/clear-loinc", methods=["POST"])
def clear_loinc(bc_id):
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    before = bc.to_dict()
    bc.loinc_code = None
    bc.loinc_metadata = None
    bc.system = ""
    bc.system_name = ""
    bc.updated_at = datetime.now(timezone.utc)
    log_change("BiomedicalConcept", bc_id, "loinc_cleared", actor="user", before=before, after=bc.to_dict())
    db.session.commit()
    flash(f"LOINC code cleared from {bc_id}", "success")
    return redirect(url_for("bc.detail", bc_id=bc_id))


@bp.route("/<bc_id>/submit", methods=["POST"])
def submit_for_review(bc_id):
    db.get_or_404(BiomedicalConcept, bc_id)
    bc_service.submit_bc_for_review(bc_id, actor="user")
    flash(f"BC {bc_id} submitted for SME review", "success")
    return redirect(url_for("bc.detail", bc_id=bc_id))


@bp.route("/<bc_id>/delete", methods=["POST"])
def delete(bc_id):
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    # Nullify self-referential parent FK on child BCs; without this SQLAlchemy
    # raises CircularDependencyError when flushing the delete.
    BiomedicalConcept.query.filter_by(parent_bc_id=bc_id).update({"parent_bc_id": None}, synchronize_session="fetch")
    # GovernanceRecord.bc_id is NOT NULL with no ORM cascade, so delete explicitly.
    GovernanceRecord.query.filter_by(bc_id=bc_id).delete(synchronize_session="fetch")
    log_change("BiomedicalConcept", bc_id, "deleted", actor="user", before=bc.to_dict())
    db.session.delete(bc)
    db.session.commit()
    flash(f"BC {bc_id} deleted", "success")
    return redirect(url_for("bc.index"))


def _decs_from_form(form):
    """Convert the parallel dec_*[] form lists into a list of dicts for
    bc_service.save_decs, preserving row positions (blank labels keep
    their slot so default dec_id numbering matches the form rows)."""
    labels = form.getlist("dec_label[]")
    dtypes = form.getlist("dec_data_type[]")
    examples = form.getlist("dec_example_set[]")
    dec_ids = form.getlist("dec_id[]")
    ncit_codes = form.getlist("dec_ncit_code[]")
    return [
        {
            "dec_id": dec_ids[i] if i < len(dec_ids) else "",
            "ncit_dec_code": ncit_codes[i] if i < len(ncit_codes) else "",
            "dec_label": label,
            "data_type": dtypes[i] if i < len(dtypes) else "string",
            "example_set": examples[i] if i < len(examples) else "",
        }
        for i, label in enumerate(labels)
    ]
