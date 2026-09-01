import csv
import io
import json
import logging

from flask import Blueprint, Response, render_template, request

from models.audit import AuditLog

logger = logging.getLogger(__name__)

bp = Blueprint("audit", __name__)

EXPORT_COLUMNS = ["id", "timestamp", "entity_type", "entity_id", "action", "actor", "before_state", "after_state"]


def _filtered_query():
    entity_type = request.args.get("entity_type", "")
    action = request.args.get("action", "")
    actor = request.args.get("actor", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = AuditLog.query
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if actor:
        query = query.filter(AuditLog.actor.ilike(f"%{actor}%"))
    if date_from:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to:
        query = query.filter(AuditLog.timestamp <= date_to)
    return query


def _log_to_dict(log):
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "action": log.action,
        "actor": log.actor,
        "before_state": log.before_state,
        "after_state": log.after_state,
    }


def _export_csv(logs):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    for log in logs:
        row = _log_to_dict(log)
        row["before_state"] = json.dumps(row["before_state"]) if row["before_state"] is not None else ""
        row["after_state"] = json.dumps(row["after_state"]) if row["after_state"] is not None else ""
        writer.writerow(row)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )


def _export_json(logs):
    return Response(
        json.dumps([_log_to_dict(log) for log in logs], indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_log.json"},
    )


@bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    entity_type = request.args.get("entity_type", "")
    action = request.args.get("action", "")
    actor = request.args.get("actor", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    export_format = request.args.get("export", "")
    if export_format in ("csv", "json"):
        logs = _filtered_query().order_by(AuditLog.timestamp.desc()).all()
        return _export_csv(logs) if export_format == "csv" else _export_json(logs)

    logs = _filtered_query().order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template(
        "audit.html",
        audit_logs=logs,
        pagination=logs,
        entity_type=entity_type,
        action=action,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
        page_title="Audit Trail",
    )
