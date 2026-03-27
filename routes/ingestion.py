import uuid
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session,
)
from models.bc import BiomedicalConcept, DataElementConcept
from models.ingestion import IngestionRecord
from models.audit import AuditLog
from extensions import db
from services.ingestion import parse_xlsx, parse_csv, parse_json, deduplicate

bp = Blueprint('ingestion', __name__)

ALLOWED_EXTENSIONS = {'xlsx', 'csv', 'json'}


def _allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXTENSIONS


def _get_session_key():
    if 'ingestion_key' not in session:
        session['ingestion_key'] = uuid.uuid4().hex
    return session['ingestion_key']


def _bc_from_mapped(bc_id, mapped):
    return BiomedicalConcept(
        bc_id=bc_id,
        short_name=mapped.get('short_name', ''),
        definition=mapped.get('definition', ''),
        ncit_code=mapped.get('ncit_code', ''),
        parent_bc_id=mapped.get('parent_bc_id') or None,
        bc_categories=mapped.get('bc_categories', ''),
        synonyms=mapped.get('synonyms', ''),
        result_scales=mapped.get('result_scales', ''),
        system=mapped.get('system', ''),
        system_name=mapped.get('system_name', ''),
        code=mapped.get('code', ''),
        package_date=mapped.get('package_date', ''),
        status='provisional',
        source='ingestion',
    )


def _create_decs(bc_id, decs):
    for i, d in enumerate(decs):
        dec = DataElementConcept(
            dec_id=d.get('dec_id') or f'{bc_id}.DEC.{i + 1}',
            bc_id=bc_id,
            ncit_dec_code=d.get('ncit_dec_code', ''),
            dec_label=d.get('dec_label', ''),
            data_type=d.get('data_type', 'string'),
            example_set=d.get('example_set', ''),
            sort_order=i,
        )
        db.session.add(dec)


@bp.route('/')
def index():
    key = session.get('ingestion_key')
    queue = (
        IngestionRecord.query
        .filter_by(session_key=key, status='pending')
        .all()
    ) if key else []
    return render_template('ingestion.html', queue=queue, page_title='Ingestion')


@bp.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('ingestion.index'))
    f = request.files['file']
    if not f.filename or not _allowed_file(f.filename):
        flash('Please upload an XLSX, CSV, or JSON file', 'danger')
        return redirect(url_for('ingestion.index'))

    ext = f.filename.rsplit('.', 1)[1].lower()
    existing_ids = {
        bc.bc_id
        for bc in BiomedicalConcept.query
        .with_entities(BiomedicalConcept.bc_id).all()
    }

    if ext == 'xlsx':
        records = parse_xlsx(f)
    elif ext == 'csv':
        records = parse_csv(f)
    else:
        records = parse_json(f)

    records = deduplicate(records, existing_ids)

    key = _get_session_key()
    IngestionRecord.query.filter_by(session_key=key, status='pending').delete()

    for rec in records:
        ir = IngestionRecord(
            session_key=key,
            source_file=f.filename,
            source_sheet=rec.get('source_sheet', ''),
            duplicate=rec.get('duplicate', False),
        )
        ir.mapped = rec.get('mapped', {})
        ir.confidences = rec.get('confidences', {})
        ir.errors = rec.get('errors', [])
        ir.decs = rec.get('decs', [])
        db.session.add(ir)

    db.session.commit()
    flash(f'Parsed {len(records)} records from {f.filename}', 'success')
    return redirect(url_for('ingestion.index'))


@bp.route('/approve/<int:record_id>', methods=['POST'])
def approve(record_id):
    ir = IngestionRecord.query.get_or_404(record_id)
    mapped = ir.mapped
    bc_id = mapped.get('bc_id') or mapped.get('ncit_code', f'IMPORT_{record_id}')
    if not BiomedicalConcept.query.get(bc_id):
        bc = _bc_from_mapped(bc_id, mapped)
        db.session.add(bc)
        _create_decs(bc_id, ir.decs)
        log = AuditLog(
            entity_type='BiomedicalConcept',
            entity_id=bc_id,
            action='created_via_ingestion',
            actor='system',
            after_state=mapped,
        )
        db.session.add(log)
        flash(f'BC {bc_id} added to library', 'success')
    else:
        flash(f'BC {bc_id} already exists', 'warning')
    ir.status = 'approved'
    db.session.commit()
    return redirect(url_for('ingestion.index'))


@bp.route('/reject/<int:record_id>', methods=['POST'])
def reject(record_id):
    ir = IngestionRecord.query.get_or_404(record_id)
    ir.status = 'rejected'
    db.session.commit()
    return redirect(url_for('ingestion.index'))


@bp.route('/approve_all', methods=['POST'])
def approve_all():
    key = session.get('ingestion_key')
    if not key:
        return redirect(url_for('ingestion.index'))
    pending = (
        IngestionRecord.query
        .filter_by(session_key=key, status='pending')
        .all()
    )
    added = 0
    for ir in pending:
        if ir.errors or ir.duplicate:
            ir.status = 'rejected'
            continue
        mapped = ir.mapped
        bc_id = (
            mapped.get('bc_id')
            or mapped.get('ncit_code', f'IMPORT_{ir.id}')
        )
        if not BiomedicalConcept.query.get(bc_id):
            bc = _bc_from_mapped(bc_id, mapped)
            db.session.add(bc)
            _create_decs(bc_id, ir.decs)
            ir.status = 'approved'
            added += 1
        else:
            ir.status = 'approved'
    db.session.commit()
    flash(f'Approved {added} BCs', 'success')
    return redirect(url_for('ingestion.index'))
