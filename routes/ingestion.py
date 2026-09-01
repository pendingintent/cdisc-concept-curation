import logging
import uuid

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from extensions import db
from models.audit import AuditLog
from models.bc import BiomedicalConcept, DataElementConcept, partition_result_scales
from models.ingestion import IngestionRecord
from models.specialization import DatasetSpecialization
from services.audit import log_change
from services.ingestion import deduplicate, parse_csv, parse_json, parse_xlsx

logger = logging.getLogger(__name__)

bp = Blueprint("ingestion", __name__)

ALLOWED_EXTENSIONS = {"xlsx", "csv", "json"}


def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS


def _get_session_key():
    if "ingestion_key" not in session:
        session["ingestion_key"] = uuid.uuid4().hex
    return session["ingestion_key"]


def _bc_from_mapped(bc_id, mapped):
    # result_scales is stored as-is, including any value outside
    # RESULT_SCALES — matching the BC edit form's own rule of never
    # silently deleting an unsupported value. It stays visible (flagged in
    # red) on the BC detail/edit page via routes.bc._result_scale_context;
    # callers here use partition_result_scales() only to flash a heads-up
    # at approval time.
    return BiomedicalConcept(
        bc_id=bc_id,
        short_name=mapped.get("short_name", ""),
        definition=mapped.get("definition", ""),
        ncit_code=mapped.get("ncit_code", ""),
        parent_bc_id=mapped.get("parent_bc_id") or None,
        bc_categories=mapped.get("bc_categories", ""),
        synonyms=mapped.get("synonyms", ""),
        result_scales=mapped.get("result_scales", ""),
        system=mapped.get("system", ""),
        system_name=mapped.get("system_name", ""),
        code=mapped.get("code", ""),
        package_date=mapped.get("package_date", ""),
        status="provisional",
        source="ingestion",
    )


def _create_decs(bc_id, decs):
    for i, d in enumerate(decs):
        dec = DataElementConcept(
            dec_id=d.get("dec_id") or f"{bc_id}.DEC.{i + 1}",
            bc_id=bc_id,
            ncit_dec_code=d.get("ncit_dec_code", ""),
            dec_label=d.get("dec_label", ""),
            data_type=d.get("data_type", "string"),
            example_set=d.get("example_set", ""),
            sort_order=i,
        )
        db.session.add(dec)


def _approve_spec_record(ir):
    """Create a DatasetSpecialization from a pending specialization-type
    IngestionRecord. Returns True if the record should be marked approved
    (created, or already existed), False if it must stay pending (its BC
    doesn't exist locally yet)."""
    mapped = ir.mapped
    vlm_group_id = mapped.get("vlm_group_id", "")
    bc_id = mapped.get("bc_id", "")
    if not db.session.get(BiomedicalConcept, bc_id):
        flash(f"Cannot import {vlm_group_id}: BC {bc_id} not found locally — approve/import that BC first", "danger")
        return False
    if db.session.get(DatasetSpecialization, vlm_group_id):
        flash(f"Specialization {vlm_group_id} already exists", "warning")
        return True
    spec = DatasetSpecialization(
        vlm_group_id=vlm_group_id,
        bc_id=bc_id,
        domain=mapped.get("domain", ""),
        short_name=mapped.get("short_name", ""),
    )
    spec.variables = ir.decs
    db.session.add(spec)
    log_change("DatasetSpecialization", vlm_group_id, "created_via_ingestion", actor="system", after=spec.to_dict())
    flash(f"Specialization {vlm_group_id} added", "success")
    return True


@bp.route("/")
def index():
    key = session.get("ingestion_key")
    queue = (IngestionRecord.query.filter_by(session_key=key, status="pending").all()) if key else []
    # Not persisted — computed for this render only, so the review table can
    # highlight an unsupported result_scales value without a schema change.
    for ir in queue:
        if ir.record_type != "specialization":
            _, ir.unsupported_result_scales = partition_result_scales(ir.mapped.get("result_scales"))
    return render_template("ingestion.html", queue=queue, page_title="Ingestion")


@bp.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("No file selected", "danger")
        return redirect(url_for("ingestion.index"))
    f = request.files["file"]
    if not f.filename or not _allowed_file(f.filename):
        flash("Please upload an XLSX, CSV, or JSON file", "danger")
        return redirect(url_for("ingestion.index"))

    ext = f.filename.rsplit(".", 1)[1].lower()
    existing_ids = {bc.bc_id for bc in BiomedicalConcept.query.with_entities(BiomedicalConcept.bc_id).all()}
    existing_spec_ids = {s.vlm_group_id for s in DatasetSpecialization.query.with_entities(DatasetSpecialization.vlm_group_id).all()}

    if ext == "xlsx":
        records = parse_xlsx(f)
    elif ext == "csv":
        records = parse_csv(f)
    else:
        records = parse_json(f)

    records = deduplicate(records, existing_ids, existing_spec_ids=existing_spec_ids)

    key = _get_session_key()
    IngestionRecord.query.filter_by(session_key=key, status="pending").delete()

    for rec in records:
        ir = IngestionRecord(
            session_key=key,
            source_file=f.filename,
            source_sheet=rec.get("source_sheet", ""),
            record_type=rec.get("record_type", "bc"),
            duplicate=rec.get("duplicate", False),
        )
        ir.mapped = rec.get("mapped", {})
        ir.confidences = rec.get("confidences", {})
        ir.errors = rec.get("errors", [])
        ir.decs = rec.get("decs") or rec.get("variables") or []
        db.session.add(ir)

    db.session.commit()
    flash(f"Parsed {len(records)} records from {f.filename}", "success")
    return redirect(url_for("ingestion.index"))


@bp.route("/approve/<int:record_id>", methods=["POST"])
def approve(record_id):
    ir = db.get_or_404(IngestionRecord, record_id)
    if ir.record_type == "specialization":
        if _approve_spec_record(ir):
            ir.status = "approved"
        db.session.commit()
        return redirect(url_for("ingestion.index"))

    mapped = ir.mapped
    bc_id = mapped.get("bc_id") or mapped.get("ncit_code", f"IMPORT_{record_id}")
    if not db.session.get(BiomedicalConcept, bc_id):
        bc = _bc_from_mapped(bc_id, mapped)
        db.session.add(bc)
        _create_decs(bc_id, ir.decs)
        log = AuditLog(
            entity_type="BiomedicalConcept",
            entity_id=bc_id,
            action="created_via_ingestion",
            actor="system",
            after_state=mapped,
        )
        db.session.add(log)
        flash(f"BC {bc_id} added to library", "success")
        _, unsupported_scales = partition_result_scales(mapped.get("result_scales"))
        if unsupported_scales:
            flash(f"BC {bc_id}: result scale value(s) not on the supported list — flagged on the BC page: {', '.join(unsupported_scales)}", "warning")
    else:
        flash(f"BC {bc_id} already exists", "warning")
    ir.status = "approved"
    db.session.commit()
    return redirect(url_for("ingestion.index"))


@bp.route("/reject/<int:record_id>", methods=["POST"])
def reject(record_id):
    ir = db.get_or_404(IngestionRecord, record_id)
    ir.status = "rejected"
    db.session.commit()
    return redirect(url_for("ingestion.index"))


@bp.route("/approve_all", methods=["POST"])
def approve_all():
    key = session.get("ingestion_key")
    if not key:
        return redirect(url_for("ingestion.index"))
    pending = IngestionRecord.query.filter_by(session_key=key, status="pending").all()
    bc_records = [ir for ir in pending if ir.record_type != "specialization"]
    spec_records = [ir for ir in pending if ir.record_type == "specialization"]

    added_bc = 0
    unsupported_scale_notes = []
    for ir in bc_records:
        if ir.errors or ir.duplicate:
            ir.status = "rejected"
            continue
        mapped = ir.mapped
        bc_id = mapped.get("bc_id") or mapped.get("ncit_code", f"IMPORT_{ir.id}")
        if not db.session.get(BiomedicalConcept, bc_id):
            bc = _bc_from_mapped(bc_id, mapped)
            db.session.add(bc)
            _create_decs(bc_id, ir.decs)
            db.session.add(
                AuditLog(
                    entity_type="BiomedicalConcept",
                    entity_id=bc_id,
                    action="created_via_ingestion",
                    actor="system",
                    after_state=mapped,
                )
            )
            ir.status = "approved"
            added_bc += 1
            _, unsupported_scales = partition_result_scales(mapped.get("result_scales"))
            if unsupported_scales:
                unsupported_scale_notes.append(f"{bc_id}: {', '.join(unsupported_scales)}")
        else:
            ir.status = "approved"
    # Flush so newly-created BCs are visible to the bc_id existence check below.
    db.session.flush()

    added_spec = 0
    for ir in spec_records:
        if ir.errors or ir.duplicate:
            ir.status = "rejected"
            continue
        if _approve_spec_record(ir):
            ir.status = "approved"
            added_spec += 1
        # else: leave pending so the user can retry once its BC is approved.

    db.session.commit()
    flash(f"Approved {added_bc} BCs and {added_spec} specializations", "success")
    if unsupported_scale_notes:
        flash("Result scale value(s) not on the supported list — flagged on the BC page: " + "; ".join(unsupported_scale_notes), "warning")
    return redirect(url_for("ingestion.index"))
