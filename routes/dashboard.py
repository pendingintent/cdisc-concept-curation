from datetime import datetime, timedelta
from flask import Blueprint, render_template
from models.bc import BiomedicalConcept
from models.specialization import DatasetSpecialization
from models.audit import AuditLog
from services.cdisc_api import CDISCApiClient

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    # --- CDISC Library API data ---
    client = CDISCApiClient()
    api_bcs = client.get_biomedical_concepts()
    api_specs = client.get_dataset_specializations()

    api_bc_error = api_bcs[0].get('error') if api_bcs and 'error' in api_bcs[0] else None
    api_spec_error = api_specs[0].get('error') if api_specs and 'error' in api_specs[0] else None
    api_bc_count = len(api_bcs) if not api_bc_error else 0
    api_spec_count = len(api_specs) if not api_spec_error else 0

    # --- Local DB stats ---
    local_total_bcs = BiomedicalConcept.query.count()
    local_pending = BiomedicalConcept.query.filter(
        BiomedicalConcept.status.in_(['provisional', 'sme_review', 'cdisc_approval'])
    ).count()
    recent_additions = BiomedicalConcept.query.filter(
        BiomedicalConcept.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()

    governance_items = (
        BiomedicalConcept.query
        .filter(BiomedicalConcept.status != 'published')
        .order_by(BiomedicalConcept.updated_at.desc())
        .limit(10).all()
    )
    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()

    stats = {
        'api_total_bcs': api_bc_count,
        'api_total_specializations': api_spec_count,
        'local_total_bcs': local_total_bcs,
        'pending_review': local_pending,
        'recent_additions': recent_additions,
    }

    return render_template(
        'dashboard.html',
        stats=stats,
        api_bcs=api_bcs[:50] if not api_bc_error else [],
        api_specs=api_specs[:50] if not api_spec_error else [],
        api_bc_error=api_bc_error,
        api_spec_error=api_spec_error,
        api_bc_count=api_bc_count,
        api_spec_count=api_spec_count,
        recent_submissions=BiomedicalConcept.query.order_by(
            BiomedicalConcept.created_at.desc()
        ).limit(10).all(),
        governance_items=governance_items,
        recent_audits=recent_audits,
        page_title='Dashboard',
    )
