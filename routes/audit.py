from flask import Blueprint, render_template, request
from models.audit import AuditLog

bp = Blueprint('audit', __name__)


@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    entity_type = request.args.get('entity_type', '')
    action = request.args.get('action', '')
    actor = request.args.get('actor', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = AuditLog.query
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))
    if actor:
        query = query.filter(AuditLog.actor.ilike(f'%{actor}%'))
    if date_from:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to:
        query = query.filter(AuditLog.timestamp <= date_to)

    logs = query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template(
        'audit.html',
        logs=logs,
        entity_type=entity_type,
        action=action,
        actor=actor,
        date_from=date_from,
        date_to=date_to,
        page_title='Audit Trail',
    )
