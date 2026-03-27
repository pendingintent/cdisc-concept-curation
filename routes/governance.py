from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.bc import BiomedicalConcept
from models.governance import GovernanceRecord
from models.audit import AuditLog
from extensions import db
from datetime import datetime

bp = Blueprint('governance', __name__)

STATUS_ORDER = ['provisional', 'sme_review', 'cdisc_approval', 'published']


@bp.route('/board')
def board():
    bcs_by_status = {}
    for status in STATUS_ORDER:
        bcs_by_status[status] = (
            BiomedicalConcept.query
            .filter_by(status=status)
            .order_by(BiomedicalConcept.updated_at.desc())
            .all()
        )
    return render_template(
        'governance.html',
        bcs_by_status=bcs_by_status,
        status_order=STATUS_ORDER,
        page_title='Governance Board',
    )


@bp.route('/advance/<bc_id>', methods=['POST'])
def advance(bc_id):
    bc = BiomedicalConcept.query.get_or_404(bc_id)
    before_status = bc.status
    current_idx = STATUS_ORDER.index(bc.status) if bc.status in STATUS_ORDER else 0
    if current_idx < len(STATUS_ORDER) - 1:
        bc.status = STATUS_ORDER[current_idx + 1]
        bc.updated_at = datetime.utcnow()
        rec = GovernanceRecord(
            bc_id=bc_id,
            stage=current_idx + 1,
            action='advanced',
            actor='user',
            comment=request.form.get('comment', ''),
        )
        log = AuditLog(
            entity_type='BiomedicalConcept',
            entity_id=bc_id,
            action='status_changed',
            actor='user',
            before_state={'status': before_status},
            after_state={'status': bc.status},
        )
        db.session.add(rec)
        db.session.add(log)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': bc.status, 'bc_id': bc_id})
        flash(f'{bc.short_name} advanced to {bc.status}', 'success')
    else:
        flash(f'{bc.short_name} is already published', 'info')
    return redirect(url_for('governance.board'))


@bp.route('/reject/<bc_id>', methods=['POST'])
def reject_bc(bc_id):
    bc = BiomedicalConcept.query.get_or_404(bc_id)
    before_status = bc.status
    bc.status = 'provisional'
    bc.updated_at = datetime.utcnow()
    rec = GovernanceRecord(
        bc_id=bc_id,
        stage=0,
        action='rejected',
        actor='user',
        comment=request.form.get('comment', ''),
    )
    log = AuditLog(
        entity_type='BiomedicalConcept',
        entity_id=bc_id,
        action='rejected',
        actor='user',
        before_state={'status': before_status},
        after_state={'status': 'provisional'},
    )
    db.session.add(rec)
    db.session.add(log)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'provisional', 'bc_id': bc_id})
    flash(f'{bc.short_name} rejected and returned to provisional', 'warning')
    return redirect(url_for('governance.board'))
