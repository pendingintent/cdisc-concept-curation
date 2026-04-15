from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.bc import BiomedicalConcept, DataElementConcept
from models.specialization import DatasetSpecialization
from extensions import db
from services.cdisc_api import CDISCApiClient

bp = Blueprint("specializations", __name__)


def _get_bc_options():
    """Return (library_bcs, local_bcs) for the BC selector.

    library_bcs — list of dicts with bc_id/short_name from the CDISC Library (cached).
    local_bcs   — BiomedicalConcept ORM objects from the local governance pipeline.
    """
    links = CDISCApiClient().get_biomedical_concepts()
    library_bcs = [{"bc_id": lnk["href"].rstrip("/").split("/")[-1], "short_name": lnk.get("title", "")} for lnk in links if "href" in lnk and "error" not in lnk]
    local_bcs = BiomedicalConcept.query.order_by(BiomedicalConcept.short_name).all()
    return library_bcs, local_bcs


@bp.route("/")
def index():
    specs = DatasetSpecialization.query.all()
    library_bcs, local_bcs = _get_bc_options()
    return render_template(
        "specializations.html",
        specs=specs,
        library_bcs=library_bcs,
        local_bcs=local_bcs,
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
        specs=specs,
        library_bcs=library_bcs,
        local_bcs=local_bcs,
        edit_spec=spec,
        page_title="Specializations",
    )


@bp.route("/", methods=["POST"])
def create():
    vlm_group_id = request.form.get("vlm_group_id", "").strip()
    bc_id = request.form.get("bc_id", "").strip()
    if not vlm_group_id or not bc_id:
        flash("VLM Group ID and BC are required", "danger")
        return redirect(url_for("specializations.index"))
    spec = DatasetSpecialization(
        vlm_group_id=vlm_group_id,
        bc_id=bc_id,
        domain=request.form.get("domain", "SDTM"),
        short_name=request.form.get("short_name", ""),
    )
    spec.variables = []
    db.session.add(spec)
    db.session.commit()
    flash(f"Specialization {vlm_group_id} created", "success")
    return redirect(url_for("specializations.index"))


@bp.route("/generate-from-dec", methods=["POST"])
def generate_from_dec():
    """Return DEC-derived variable rows as JSON for the specialization form."""
    data = request.get_json(silent=True) or {}
    bc_id = data.get("bc_id", "").strip()
    if not bc_id:
        return jsonify({"error": "bc_id required"}), 400
    decs = DataElementConcept.query.filter_by(bc_id=bc_id).all()
    variables = [{"name": d.dec_label or "", "label": d.dec_label or "", "data_type": d.data_type or "string", "required": bool(d.required)} for d in decs]
    return jsonify({"variables": variables})


@bp.route("/generate/<bc_id>", methods=["POST"])
def generate(bc_id):
    """Generate a specialization from DEC templates for a BC."""
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    decs = DataElementConcept.query.filter_by(bc_id=bc_id).all()
    domain = request.form.get("domain", "SDTM")
    vlm_group_id = f"{bc_id}.{domain}"
    existing = db.session.get(DatasetSpecialization, vlm_group_id)
    if existing:
        flash(f"Specialization {vlm_group_id} already exists", "warning")
        return redirect(url_for("specializations.index"))
    variables = [{"name": d.dec_label, "data_type": d.data_type, "required": d.required} for d in decs]
    spec = DatasetSpecialization(
        vlm_group_id=vlm_group_id,
        bc_id=bc_id,
        domain=domain,
        short_name=bc.short_name,
    )
    spec.variables = variables
    db.session.add(spec)
    db.session.commit()
    flash(f"Specialization {vlm_group_id} generated", "success")
    return redirect(url_for("specializations.index"))
