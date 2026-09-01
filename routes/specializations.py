import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from extensions import db
from models.bc import BiomedicalConcept, DataElementConcept
from models.specialization import DatasetSpecialization
from services import notes_service
from services.audit import log_change
from services.bc_service import get_or_create_bc_stub
from services.cdisc_api import CDISCApiClient
from services.ingestion import VARIABLE_FIELD_DEFS, VARIABLE_FIELDS

logger = logging.getLogger(__name__)

bp = Blueprint("specializations", __name__)


def _get_bc_options():
    """Return (library_bcs, local_bcs) for the BC selector.

    library_bcs — list of dicts with bc_id/short_name from the CDISC Library (cached).
    local_bcs   — BiomedicalConcept ORM objects from the local governance pipeline.
    """
    links = CDISCApiClient().get_biomedical_concepts()
    library_bcs = [{"bc_id": lnk["href"].rstrip("/").split("/")[-1], "short_name": lnk.get("title", "")} for lnk in links if "href" in lnk and "error" not in lnk]
    library_bcs.sort(key=lambda bc: bc["short_name"].lower())
    local_bcs = BiomedicalConcept.query.order_by(BiomedicalConcept.short_name).all()
    return library_bcs, local_bcs


def _get_domain_codes():
    """Return the SDTM Domain Abbreviation codelist (C66734) as [{code, label}, ...]
    from the most recent SDTM CT package, for the domain selector."""
    codes = CDISCApiClient().get_sdtm_domain_codes()
    return [c for c in codes if c.get("code")]


def _variable_from_dec(dec):
    """Best-effort variable row seeded from a BC's Data Element Concept.
    A DEC doesn't carry most VLM columns (codelist, role, subject, ...), so
    only sdtm_variable/dec_id/data_type are populated — the rest are left
    blank for the user to fill in."""
    row = dict.fromkeys(VARIABLE_FIELDS, "")
    row["sdtm_variable"] = dec.dec_label or ""
    row["dec_id"] = dec.dec_id or ""
    row["data_type"] = dec.data_type or "string"
    return row


@bp.route("/")
def index():
    specs = DatasetSpecialization.query.all()
    library_bcs, local_bcs = _get_bc_options()
    return render_template(
        "specializations.html",
        specializations=specs,
        library_bcs=library_bcs,
        local_bcs=local_bcs,
        domain_codes=_get_domain_codes(),
        variable_field_defs=VARIABLE_FIELD_DEFS,
        page_title="Specializations",
    )


@bp.route("/library/<path:spec_path>")
def library_detail(spec_path):
    client = CDISCApiClient()
    spec = client.get_specialization("/" + spec_path)
    if "error" in spec:
        flash(f'Could not load specialization: {spec["error"]}', "danger")
        return redirect(url_for("dashboard.index"))
    return render_template(
        "library_spec_detail.html",
        spec=spec,
        page_title=spec.get("shortName") or spec.get("datasetSpecializationId") or spec_path.split("/")[-1],
    )


@bp.route("/<vlm_group_id>")
def detail(vlm_group_id):
    spec = db.get_or_404(DatasetSpecialization, vlm_group_id)
    specs = DatasetSpecialization.query.all()
    library_bcs, local_bcs = _get_bc_options()
    return render_template(
        "specializations.html",
        specializations=specs,
        library_bcs=library_bcs,
        local_bcs=local_bcs,
        domain_codes=_get_domain_codes(),
        variable_field_defs=VARIABLE_FIELD_DEFS,
        edit_spec=spec,
        notes=notes_service.list_spec_notes(vlm_group_id),
        page_title="Specializations",
    )


def _variables_from_form(form):
    """Convert the bracketed variables[i][field] form inputs into a list of
    dicts, one per VARIABLE_FIELDS column (the same worksheet columns
    services.ingestion imports from SDTM_/CDASH_ sheets)."""
    variables = []
    i = 0
    while f"variables[{i}][sdtm_variable]" in form:
        row = {field: (form.get(f"variables[{i}][{field}]") or "").strip() for field in VARIABLE_FIELDS}
        if row["sdtm_variable"]:
            variables.append(row)
        i += 1
    return variables


@bp.route("/", methods=["POST"])
def create():
    vlm_group_id = request.form.get("vlm_group_id", "").strip()
    bc_id = request.form.get("bc_id", "").strip()
    domain = request.form.get("domain", "").strip()
    if not vlm_group_id or not bc_id or not domain:
        flash("VLM Group ID, BC, and Domain are required", "danger")
        return redirect(url_for("specializations.index"))
    short_name = request.form.get("short_name", "")
    variables = _variables_from_form(request.form)

    get_or_create_bc_stub(bc_id, short_name=short_name, actor="user")

    spec = db.session.get(DatasetSpecialization, vlm_group_id)
    if spec:
        if spec.status == "published":
            flash(f"Specialization {vlm_group_id} has reached Ready to Publish status and cannot be edited", "danger")
            return redirect(url_for("specializations.index"))
        before = spec.to_dict()
        spec.bc_id = bc_id
        spec.domain = domain
        spec.short_name = short_name
        spec.variables = variables
        log_change("DatasetSpecialization", vlm_group_id, "updated", actor="user", before=before, after=spec.to_dict())
        db.session.commit()
        flash(f"Specialization {vlm_group_id} updated", "success")
        return redirect(url_for("specializations.index"))

    spec = DatasetSpecialization(
        vlm_group_id=vlm_group_id,
        bc_id=bc_id,
        domain=domain,
        short_name=short_name,
    )
    spec.variables = variables
    db.session.add(spec)
    log_change("DatasetSpecialization", vlm_group_id, "created", actor="user", after=spec.to_dict())
    db.session.commit()
    flash(f"Specialization {vlm_group_id} created", "success")
    return redirect(url_for("specializations.index"))


@bp.route("/<vlm_group_id>/delete", methods=["POST"])
def delete(vlm_group_id):
    spec = db.get_or_404(DatasetSpecialization, vlm_group_id)
    if spec.status == "published":
        flash(f"Specialization {vlm_group_id} has reached Ready to Publish status and cannot be deleted", "danger")
        return redirect(url_for("specializations.index"))
    log_change("DatasetSpecialization", vlm_group_id, "deleted", actor="user", before=spec.to_dict())
    db.session.delete(spec)
    db.session.commit()
    flash(f"Specialization {vlm_group_id} deleted", "success")
    return redirect(url_for("specializations.index"))


@bp.route("/generate-from-dec", methods=["POST"])
def generate_from_dec():
    """Return DEC-derived variable rows as JSON for the specialization form."""
    data = request.get_json(silent=True) or {}
    bc_id = data.get("bc_id", "").strip()
    if not bc_id:
        return jsonify({"error": "bc_id required"}), 400
    decs = DataElementConcept.query.filter_by(bc_id=bc_id).all()
    variables = [_variable_from_dec(d) for d in decs]
    return jsonify({"variables": variables})


@bp.route("/generate/<bc_id>", methods=["POST"])
def generate(bc_id):
    """Generate a specialization from DEC templates for a BC."""
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    decs = DataElementConcept.query.filter_by(bc_id=bc_id).all()
    domain = request.form.get("domain", "").strip()
    if not domain:
        flash("Domain is required", "danger")
        return redirect(url_for("specializations.index"))
    vlm_group_id = f"{bc_id}.{domain}"
    existing = db.session.get(DatasetSpecialization, vlm_group_id)
    if existing:
        flash(f"Specialization {vlm_group_id} already exists", "warning")
        return redirect(url_for("specializations.index"))
    variables = [_variable_from_dec(d) for d in decs]
    spec = DatasetSpecialization(
        vlm_group_id=vlm_group_id,
        bc_id=bc_id,
        domain=domain,
        short_name=bc.short_name,
    )
    spec.variables = variables
    db.session.add(spec)
    log_change("DatasetSpecialization", vlm_group_id, "created", actor="user", after=spec.to_dict())
    db.session.commit()
    flash(f"Specialization {vlm_group_id} generated", "success")
    return redirect(url_for("specializations.index"))
