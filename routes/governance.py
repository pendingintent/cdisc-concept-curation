from datetime import datetime, timezone

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for

from extensions import db
from models.bc import BiomedicalConcept
from models.governance import GovernanceRecord
from services.audit import log_change
from services.export import export_governance_xlsx

bp = Blueprint("governance", __name__)

STATUS_ORDER = ["provisional", "sme_review", "cdisc_approval", "published"]


@bp.route("/board")
def board():
    bcs_by_status = {}
    for status in STATUS_ORDER:
        bcs_by_status[status] = BiomedicalConcept.query.filter_by(status=status).order_by(BiomedicalConcept.updated_at.desc()).all()
    return render_template(
        "governance.html",
        columns=bcs_by_status,
        status_order=STATUS_ORDER,
        page_title="Governance Board",
    )


@bp.route("/export")
def export():
    filename = request.args.get("filename", "governance_export").strip() or "governance_export"
    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    safe_filename = f"{base}.xlsx"

    stage3_bc_ids = db.session.query(GovernanceRecord.bc_id).filter(GovernanceRecord.stage == 3).distinct()
    bcs = BiomedicalConcept.query.filter(BiomedicalConcept.bc_id.in_(stage3_bc_ids)).all()

    buf = export_governance_xlsx(bcs)
    return Response(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@bp.route("/advance/<bc_id>", methods=["POST"])
def advance(bc_id):
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    before_status = bc.status
    current_idx = STATUS_ORDER.index(bc.status) if bc.status in STATUS_ORDER else 0
    if current_idx < len(STATUS_ORDER) - 1:
        bc.status = STATUS_ORDER[current_idx + 1]
        bc.updated_at = datetime.now(timezone.utc)
        rec = GovernanceRecord(
            bc_id=bc_id,
            stage=current_idx + 1,
            action="advanced",
            actor="user",
            comment=request.form.get("comment", ""),
        )
        db.session.add(rec)
        log_change("BiomedicalConcept", bc_id, "status_changed", actor="user", before={"status": before_status}, after={"status": bc.status})
        db.session.commit()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": bc.status, "bc_id": bc_id})
        flash(f"{bc.short_name} advanced to {bc.status}", "success")
    else:
        flash(f"{bc.short_name} is already published", "info")
    return redirect(url_for("governance.board"))


@bp.route("/reject/<bc_id>", methods=["POST"])
def reject_bc(bc_id):
    bc = db.get_or_404(BiomedicalConcept, bc_id)
    before_status = bc.status
    bc.status = "provisional"
    bc.updated_at = datetime.now(timezone.utc)
    rec = GovernanceRecord(
        bc_id=bc_id,
        stage=0,
        action="rejected",
        actor="user",
        comment=request.form.get("comment", ""),
    )
    db.session.add(rec)
    log_change("BiomedicalConcept", bc_id, "rejected", actor="user", before={"status": before_status}, after={"status": "provisional"})
    db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "provisional", "bc_id": bc_id})
    flash(f"{bc.short_name} rejected and returned to provisional", "warning")
    return redirect(url_for("governance.board"))
