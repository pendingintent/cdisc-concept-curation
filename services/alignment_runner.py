"""Runs the cdisc-bc-ncit-alignment submodule's two-stage pipeline in a
background thread and tracks progress on an AlignmentJob row.

Stage 1 (populate_complete_list) and stage 2 (augment_cdisc) are each
launched as a subprocess (not imported directly — the submodule is a
separate git repo, not part of this app's import path) via the parent
process's own interpreter, with cwd set to the submodule root so
`-m src.xxx` resolves. subprocess.Popen (not subprocess.run) is required
because stderr must be read incrementally, while the process is still
running, to update progress — subprocess.run only returns output after
the process exits.
"""

import json
import logging
import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone

import openpyxl
from flask import current_app

from extensions import db
from models.alignment import AlignmentJob

logger = logging.getLogger(__name__)

JOB_OUTPUT_SUBDIR = "alignment_jobs"

_BATCH_RE = re.compile(r"batches\s+(\d+)/(\d+)")
_SUMMARY_RE = re.compile(r"Wrote\s+([\d,]+)\s+rows\s+\(([\d,]+)\s+CDISC hits\)")

_NON_TERMINAL_STATUSES = ("completed", "failed")


def start_job(actor="user"):
    """Guard against a concurrent run, create the AlignmentJob row, and spawn
    a daemon background thread running the pipeline. Raises RuntimeError if
    another job is already in flight.

    This is a soft, request-time check (not a DB constraint) — acceptable
    for a single human clicking a button on an internal admin-style page,
    matching the level of rigor used elsewhere in this app (e.g. governance
    stage advances have no locking either).
    """
    in_flight = AlignmentJob.query.filter(~AlignmentJob.status.in_(_NON_TERMINAL_STATUSES)).first()
    if in_flight:
        raise RuntimeError("An alignment job is already running")

    job = AlignmentJob(created_by=actor)
    db.session.add(job)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=_run_pipeline, args=(app, job.id), daemon=True)
    thread.start()
    return job


def _run_pipeline(app, job_id, output_dir=None):
    """Background-thread target. Must push its own app context — a thread
    has none of its own. Re-queries the job by id rather than sharing the
    ORM object created in the request thread."""
    with app.app_context():
        job = db.session.get(AlignmentJob, job_id)
        job.status = "running_populate"
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()

        out_dir = output_dir if output_dir is not None else os.path.join(app.instance_path, JOB_OUTPUT_SUBDIR, str(job.id))
        os.makedirs(out_dir, exist_ok=True)
        xlsx_path = os.path.join(out_dir, "report.xlsx")
        json_path = os.path.join(out_dir, "report.json")

        try:
            _run_populate(app, job, xlsx_path)

            job.status = "running_augment"
            db.session.commit()
            _run_augment(app, job, xlsx_path)

            job.status = "generating_json"
            db.session.commit()
            _write_json_export(xlsx_path, json_path)

            job.xlsx_path = xlsx_path
            job.json_path = json_path
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 - background job must never crash silently
            logger.exception("Alignment job %s failed", job_id)
            job.status = "failed"
            job.error_message = str(exc)
            db.session.commit()


def _run_populate(app, job, xlsx_path):
    """Run stage 1 and update job.populate_batches_done/total as batches complete."""
    cmd = [sys.executable, "-m", "src.populate_complete_list", "--output", xlsx_path]
    proc = subprocess.Popen(
        cmd,
        cwd=app.config["ALIGNMENT_SUBMODULE_DIR"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    last_done = None
    for line in proc.stderr:
        match = _BATCH_RE.search(line)
        if not match:
            continue
        done, total = int(match.group(1)), int(match.group(2))
        if done != last_done:
            job.populate_batches_done = done
            job.populate_batches_total = total
            db.session.commit()
            last_done = done
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"populate_complete_list failed (exit code {proc.returncode})")


def _run_augment(app, job, xlsx_path):
    """Run stage 2 (in place on xlsx_path) and record the final hit/row counts.

    CDISC_API_KEY is passed explicitly rather than relying on inherited
    process env — this app prefers CDISC_SUBSCRIPTION_KEY over
    CDISC_API_KEY for its own client (see config.py), but the submodule's
    client only reads CDISC_API_KEY with no fallback.
    """
    cmd = [sys.executable, "-m", "src.augment_cdisc", "--input", xlsx_path]
    env = os.environ.copy()
    env["CDISC_API_KEY"] = app.config.get("CDISC_API_KEY", "")
    proc = subprocess.Popen(
        cmd,
        cwd=app.config["ALIGNMENT_SUBMODULE_DIR"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    for line in proc.stderr:
        match = _SUMMARY_RE.search(line)
        if match:
            job.augment_rows_total = int(match.group(1).replace(",", ""))
            job.augment_cdisc_hits = int(match.group(2).replace(",", ""))
            db.session.commit()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"augment_cdisc failed (exit code {proc.returncode})")


def _write_json_export(xlsx_path, json_path):
    """Derive a self-describing JSON export (list of row-dicts keyed by the
    xlsx header row) from the final report, matching
    services/export.py::export_json()'s existing philosophy."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    try:
        rows = wb.active.iter_rows(values_only=True)
        headers = list(next(rows))
        records = [dict(zip(headers, row)) for row in rows]
    finally:
        wb.close()
    with open(json_path, "w") as f:
        json.dump(records, f, indent=2, default=str)
