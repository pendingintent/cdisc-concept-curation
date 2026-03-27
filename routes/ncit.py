from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models.bc import BiomedicalConcept
from extensions import db
from services.ncit_api import NCItApiClient

bp = Blueprint('ncit', __name__)


@bp.route('/')
def index():
    return redirect(url_for('ncit.mapping'))


@bp.route('/mapping')
def mapping():
    # Surface BCs that have no NCIt code yet — these need manual resolution
    unresolved = BiomedicalConcept.query.filter(
        (BiomedicalConcept.ncit_code == None) | (BiomedicalConcept.ncit_code == '')
    ).limit(50).all()
    return render_template(
        'ncit_mapping.html',
        unresolved=unresolved,
        results=[],
        search_term='',
        page_title='NCIt Mapping',
    )


@bp.route('/search')
def search_ncit():
    term = request.args.get('term', '').strip()
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.args.get('format') == 'json'
    )
    if not term:
        if is_ajax:
            return jsonify([])
        return render_template(
            'ncit_mapping.html',
            results=[],
            search_term='',
            unresolved=[],
            page_title='NCIt Mapping',
        )

    client = NCItApiClient()
    results = client.search_concept(term, size=10)

    if is_ajax:
        return jsonify(results)

    unresolved = BiomedicalConcept.query.filter(
        (BiomedicalConcept.ncit_code == None) | (BiomedicalConcept.ncit_code == '')
    ).limit(50).all()
    return render_template(
        'ncit_mapping.html',
        results=results,
        search_term=term,
        unresolved=unresolved,
        page_title='NCIt Mapping',
    )


@bp.route('/resolve/<bc_id>', methods=['POST'])
def resolve(bc_id):
    bc = BiomedicalConcept.query.get_or_404(bc_id)
    ncit_code = request.form.get('ncit_code', '').strip()
    if ncit_code:
        bc.ncit_code = ncit_code
        # Promote temporary IMPORT_ IDs to their resolved NCIt code
        if not bc.bc_id or bc.bc_id.startswith('IMPORT_'):
            bc.bc_id = ncit_code
        db.session.commit()
        flash(f'NCIt mapping updated for {bc.short_name}', 'success')
    return redirect(url_for('ncit.mapping'))
