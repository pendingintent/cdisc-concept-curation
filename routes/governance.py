from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for

from extensions import db
from models.bc import BiomedicalConcept
from services import governance_service
from services.export import export_governance_xlsx
from services.governance_service import STATUS_ORDER

bp = Blueprint("governance", __name__)


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
    import re

    raw = request.args.get("filename", "governance_export")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (raw or "").strip()) or "governance_export"
    base = base.rsplit(".", 1)[0] if "." in base else base
    safe_filename = f"{base}.xlsx"

    bcs = BiomedicalConcept.query.filter_by(status="published").all()

    buf = export_governance_xlsx(bcs)
    return Response(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@bp.route("/advance/<bc_id>", methods=["POST"])
def advance(bc_id):
    db.get_or_404(BiomedicalConcept, bc_id)
    result = governance_service.advance_governance(bc_id, actor="user", comment=request.form.get("comment", ""))
    if result["advanced"]:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": result["status"], "bc_id": bc_id})
        flash(f'{result["short_name"]} advanced to {result["status"]}', "success")
    else:
        flash(f'{result["short_name"]} is already published', "info")
    return redirect(url_for("governance.board"))


@bp.route("/reject/<bc_id>", methods=["POST"])
def reject_bc(bc_id):
    db.get_or_404(BiomedicalConcept, bc_id)
    result = governance_service.reject_bc(bc_id, actor="user", comment=request.form.get("comment", ""))
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "provisional", "bc_id": bc_id})
    flash(f'{result["short_name"]} rejected and returned to provisional', "warning")
    return redirect(url_for("governance.board"))
