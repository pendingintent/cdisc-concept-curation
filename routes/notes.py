import logging

from flask import Blueprint, jsonify, request

from services import notes_service
from services.bc_service import NotFoundError

logger = logging.getLogger(__name__)

bp = Blueprint("notes", __name__)


def _note_response(note):
    return jsonify(note.to_dict())


@bp.route("/bc/<bc_id>", methods=["POST"])
def create_bc_note(bc_id):
    data = request.get_json(silent=True) or {}
    try:
        note = notes_service.create_bc_note(bc_id, data.get("text"), actor="user")
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _note_response(note), 201


@bp.route("/spec/<vlm_group_id>", methods=["POST"])
def create_spec_note(vlm_group_id):
    data = request.get_json(silent=True) or {}
    try:
        note = notes_service.create_spec_note(vlm_group_id, data.get("text"), actor="user")
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _note_response(note), 201


@bp.route("/<int:note_id>/update", methods=["POST"])
def update_note(note_id):
    data = request.get_json(silent=True) or {}
    try:
        note = notes_service.update_note_text(note_id, data.get("text"), actor="user")
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _note_response(note)


@bp.route("/<int:note_id>/resolve", methods=["POST"])
def resolve_note(note_id):
    data = request.get_json(silent=True) or {}
    try:
        note = notes_service.set_resolved(note_id, bool(data.get("resolved", True)), actor="user")
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _note_response(note)


@bp.route("/<int:note_id>/flag", methods=["POST"])
def flag_note(note_id):
    data = request.get_json(silent=True) or {}
    try:
        note = notes_service.set_flagged(note_id, bool(data.get("flagged", True)), actor="user")
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _note_response(note)
