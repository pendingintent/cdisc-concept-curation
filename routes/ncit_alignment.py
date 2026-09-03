import logging
import os

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for

from extensions import db
from models.alignment import AlignmentJob
from services import alignment_runner

logger = logging.getLogger(__name__)

bp = Blueprint("ncit_alignment", __name__)


def _latest_job():
    return AlignmentJob.query.order_by(AlignmentJob.created_at.desc()).first()


@bp.route("/")
def index():
    return render_template("ncit_alignment.html", job=_latest_job(), page_title="NCIt/BC Alignment")


@bp.route("/start", methods=["POST"])
def start():
    try:
        job = alignment_runner.start_job(actor="user")
    except RuntimeError as exc:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": str(exc)}), 409
        flash(str(exc), "warning")
        return redirect(url_for("ncit_alignment.index"))

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"job_id": job.id})
    return redirect(url_for("ncit_alignment.index"))


@bp.route("/status")
def status():
    job = _latest_job()
    if job is None:
        return jsonify({"status": "none"})

    data = job.to_dict()
    data["xlsx_ready"] = job.status == "completed" and bool(job.xlsx_path) and os.path.exists(job.xlsx_path)
    data["json_ready"] = job.status == "completed" and bool(job.json_path) and os.path.exists(job.json_path)
    del data["xlsx_path"]
    del data["json_path"]
    return jsonify(data)


@bp.route("/download/xlsx/<int:job_id>")
def download_xlsx(job_id):
    job = db.get_or_404(AlignmentJob, job_id)
    if job.status != "completed" or not job.xlsx_path or not os.path.exists(job.xlsx_path):
        abort(404)
    return send_file(job.xlsx_path, as_attachment=True, download_name=f"ncit_bc_alignment_{job_id}.xlsx")


@bp.route("/download/json/<int:job_id>")
def download_json(job_id):
    job = db.get_or_404(AlignmentJob, job_id)
    if job.status != "completed" or not job.json_path or not os.path.exists(job.json_path):
        abort(404)
    return send_file(
        job.json_path,
        as_attachment=True,
        download_name=f"ncit_bc_alignment_{job_id}.json",
        mimetype="application/json",
    )
