from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from models.bc import BiomedicalConcept, DataElementConcept
from models.audit import AuditLog
from extensions import db
from services.export import export_json, export_xlsx, export_odm_xml
from datetime import datetime

bp = Blueprint('bc', __name__)


@bp.route('/')
def index():
    q = request.args.get('q', '')
    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    query = BiomedicalConcept.query
    if q:
        query = query.filter(
            BiomedicalConcept.short_name.ilike(f'%{q}%') |
            BiomedicalConcept.bc_id.ilike(f'%{q}%') |
            BiomedicalConcept.ncit_code.ilike(f'%{q}%')
        )
    if status:
        query = query.filter_by(status=status)
    bcs = query.order_by(BiomedicalConcept.updated_at.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    return render_template(
        'bc_list.html',
        bcs=bcs,
        q=q,
        status=status,
        page_title='Biomedical Concepts',
    )


@bp.route('/new')
def new_bc():
    bc = BiomedicalConcept()
    return render_template(
        'bc_detail.html',
        bc=bc,
        decs=[],
        is_new=True,
        page_title='New Biomedical Concept',
    )


@bp.route('/export')
def export():
    fmt = request.args.get('format', 'json')
    bcs = [bc.to_dict() for bc in BiomedicalConcept.query.all()]
    if fmt == 'xlsx':
        buf = export_xlsx(bcs)
        return Response(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=bcs.xlsx'},
        )
    elif fmt == 'odm':
        xml = export_odm_xml(bcs)
        return Response(
            xml,
            mimetype='application/xml',
            headers={'Content-Disposition': 'attachment; filename=bcs_odm.xml'},
        )
    else:
        return Response(
            export_json(bcs),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=bcs.json'},
        )


@bp.route('/<bc_id>')
def detail(bc_id):
    bc = BiomedicalConcept.query.get_or_404(bc_id)
    decs = (
        DataElementConcept.query
        .filter_by(bc_id=bc_id)
        .order_by(DataElementConcept.sort_order)
        .all()
    )
    return render_template(
        'bc_detail.html',
        bc=bc,
        decs=decs,
        is_new=False,
        page_title=bc.short_name,
    )


@bp.route('/', methods=['POST'])
def create():
    bc_id = request.form.get('bc_id', '').strip()
    if not bc_id:
        flash('BC ID is required', 'danger')
        return redirect(url_for('bc.new_bc'))
    if BiomedicalConcept.query.get(bc_id):
        flash(f'BC {bc_id} already exists', 'danger')
        return redirect(url_for('bc.new_bc'))
    bc = BiomedicalConcept(
        bc_id=bc_id,
        short_name=request.form.get('short_name', ''),
        definition=request.form.get('definition', ''),
        ncit_code=request.form.get('ncit_code', ''),
        parent_bc_id=request.form.get('parent_bc_id') or None,
        bc_categories=request.form.get('bc_categories', ''),
        synonyms=request.form.get('synonyms', ''),
        result_scales=request.form.get('result_scales', ''),
        system=request.form.get('system', ''),
        system_name=request.form.get('system_name', ''),
        code=request.form.get('code', ''),
        package_date=request.form.get('package_date', ''),
        status='provisional',
        submitter=request.form.get('submitter', 'unknown'),
    )
    db.session.add(bc)
    log = AuditLog(
        entity_type='BiomedicalConcept',
        entity_id=bc_id,
        action='created',
        actor=bc.submitter,
        after_state=bc.to_dict(),
    )
    db.session.add(log)
    db.session.commit()
    _save_decs(bc_id, request.form)
    flash(f'BC {bc_id} created', 'success')
    return redirect(url_for('bc.detail', bc_id=bc_id))


@bp.route('/<bc_id>/edit', methods=['POST'])
def edit(bc_id):
    bc = BiomedicalConcept.query.get_or_404(bc_id)
    before = bc.to_dict()
    bc.short_name = request.form.get('short_name', bc.short_name)
    bc.definition = request.form.get('definition', bc.definition)
    bc.ncit_code = request.form.get('ncit_code', bc.ncit_code)
    bc.parent_bc_id = request.form.get('parent_bc_id') or bc.parent_bc_id
    bc.bc_categories = request.form.get('bc_categories', bc.bc_categories)
    bc.synonyms = request.form.get('synonyms', bc.synonyms)
    bc.result_scales = request.form.get('result_scales', bc.result_scales)
    bc.system = request.form.get('system', bc.system)
    bc.system_name = request.form.get('system_name', bc.system_name)
    bc.code = request.form.get('code', bc.code)
    bc.package_date = request.form.get('package_date', bc.package_date)
    bc.updated_at = datetime.utcnow()
    log = AuditLog(
        entity_type='BiomedicalConcept',
        entity_id=bc_id,
        action='updated',
        actor='user',
        before_state=before,
        after_state=bc.to_dict(),
    )
    db.session.add(log)
    db.session.commit()
    _save_decs(bc_id, request.form)
    flash(f'BC {bc_id} updated', 'success')
    return redirect(url_for('bc.detail', bc_id=bc_id))


@bp.route('/<bc_id>/submit', methods=['POST'])
def submit_for_review(bc_id):
    bc = BiomedicalConcept.query.get_or_404(bc_id)
    before = bc.to_dict()
    bc.status = 'sme_review'
    bc.updated_at = datetime.utcnow()
    log = AuditLog(
        entity_type='BiomedicalConcept',
        entity_id=bc_id,
        action='submitted_for_review',
        actor='user',
        before_state=before,
        after_state=bc.to_dict(),
    )
    db.session.add(log)
    db.session.commit()
    flash(f'BC {bc_id} submitted for SME review', 'success')
    return redirect(url_for('bc.detail', bc_id=bc_id))


@bp.route('/<bc_id>/delete', methods=['POST'])
def delete(bc_id):
    bc = BiomedicalConcept.query.get_or_404(bc_id)
    log = AuditLog(
        entity_type='BiomedicalConcept',
        entity_id=bc_id,
        action='deleted',
        actor='user',
        before_state=bc.to_dict(),
    )
    db.session.add(log)
    db.session.delete(bc)
    db.session.commit()
    flash(f'BC {bc_id} deleted', 'success')
    return redirect(url_for('bc.index'))


def _save_decs(bc_id, form):
    """Persist Data Element Concepts from a submitted form.

    Expects parallel lists posted as dec_label[], dec_data_type[],
    dec_example_set[], dec_id[], dec_ncit_code[]. Any existing DECs for the
    BC are replaced on every call so that deletions are honoured.
    """
    labels = form.getlist('dec_label[]')
    dtypes = form.getlist('dec_data_type[]')
    examples = form.getlist('dec_example_set[]')
    dec_ids = form.getlist('dec_id[]')
    ncit_codes = form.getlist('dec_ncit_code[]')
    if not labels:
        return
    DataElementConcept.query.filter_by(bc_id=bc_id).delete()
    for i, label in enumerate(labels):
        if not label.strip():
            continue
        dec = DataElementConcept(
            dec_id=dec_ids[i] if i < len(dec_ids) and dec_ids[i] else f'{bc_id}.DEC.{i + 1}',
            bc_id=bc_id,
            ncit_dec_code=ncit_codes[i] if i < len(ncit_codes) else '',
            dec_label=label.strip(),
            data_type=dtypes[i] if i < len(dtypes) else 'string',
            example_set=examples[i] if i < len(examples) else '',
            sort_order=i,
        )
        db.session.add(dec)
    db.session.commit()
