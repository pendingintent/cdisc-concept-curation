from flask import Blueprint, render_template
from models.bc import BiomedicalConcept
from models.audit import AuditLog

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    total_bcs = BiomedicalConcept.query.count()
    pending = BiomedicalConcept.query.filter(
        BiomedicalConcept.status.in_(['provisional', 'sme_review', 'cdisc_approval'])
    ).count()
    published = BiomedicalConcept.query.filter_by(status='published').count()
    recent = BiomedicalConcept.query.order_by(BiomedicalConcept.created_at.desc()).limit(10).all()
    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    pipeline = BiomedicalConcept.query.filter(
        BiomedicalConcept.status != 'published'
    ).order_by(BiomedicalConcept.updated_at.desc()).limit(10).all()
    from datetime import datetime, timedelta
    recent_additions = BiomedicalConcept.query.filter(
        BiomedicalConcept.created_at >= datetime.utcnow() - timedelta(days=30)
    ).count()
    stats = {
        'total_bcs': total_bcs,
        'pending_review': pending,
        'published': published,
        'recent_additions': recent_additions,
    }
    return render_template(
        'dashboard.html',
        stats=stats,
        recent_bcs=recent,
        recent_audits=recent_audits,
        pipeline=pipeline,
        page_title='Dashboard',
    )
