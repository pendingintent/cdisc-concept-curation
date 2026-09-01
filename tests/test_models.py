"""Tests for model property serialization and helper methods."""

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.audit import AuditLog
from models.bc import RESULT_SCALES, BiomedicalConcept, DataElementConcept, partition_result_scales, split_result_scales
from models.ingestion import IngestionRecord
from models.note import Note


class TestAuditLogJsonProperties:
    def test_before_state_round_trips(self, app):
        with app.app_context():
            log = AuditLog()
            log.before_state = {"status": "provisional", "bc_id": "C001"}
            assert log.before_state == {"status": "provisional", "bc_id": "C001"}

    def test_after_state_round_trips(self, app):
        with app.app_context():
            log = AuditLog()
            log.after_state = {"status": "sme_review"}
            assert log.after_state == {"status": "sme_review"}

    def test_none_before_state_returns_none(self, app):
        with app.app_context():
            log = AuditLog()
            assert log.before_state is None

    def test_none_after_state_returns_none(self, app):
        with app.app_context():
            log = AuditLog()
            assert log.after_state is None

    def test_persisted_log_retrieves_state(self, app):
        with app.app_context():
            log = AuditLog(
                entity_type="BiomedicalConcept",
                entity_id="C001",
                action="created",
                actor="tester",
            )
            log.after_state = {"bc_id": "C001", "short_name": "Test"}
            db.session.add(log)
            db.session.commit()
            fetched = AuditLog.query.first()
            assert fetched.after_state["bc_id"] == "C001"


class TestIngestionRecordProperties:
    def test_mapped_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.mapped = {"bc_id": "C001", "short_name": "HR"}
            assert ir.mapped == {"bc_id": "C001", "short_name": "HR"}

    def test_confidences_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.confidences = {"bc_id": 1.0, "short_name": 0.9}
            assert ir.confidences == {"bc_id": 1.0, "short_name": 0.9}

    def test_errors_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.errors = ["short_name is required"]
            assert ir.errors == ["short_name is required"]

    def test_decs_round_trips(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.decs = [{"dec_id": "C001.DEC.1", "dec_label": "Value"}]
            assert ir.decs[0]["dec_label"] == "Value"

    def test_empty_mapped_returns_empty_dict(self, app):
        with app.app_context():
            ir = IngestionRecord()
            assert ir.mapped == {}

    def test_avg_confidence_computed_correctly(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.confidences = {"bc_id": 1.0, "short_name": 0.8, "definition": 0.6}
            assert ir.avg_confidence == round((1.0 + 0.8 + 0.6) / 3 * 100)

    def test_avg_confidence_empty_confidences(self, app):
        with app.app_context():
            ir = IngestionRecord()
            ir.confidences = {}
            assert ir.avg_confidence == 0


class TestBiomedicalConceptToDict:
    def test_to_dict_contains_required_keys(self, app):
        with app.app_context():
            bc = BiomedicalConcept(
                bc_id="C001",
                short_name="Heart Rate",
                definition="Rate of the heart.",
                ncit_code="C001",
                status="provisional",
            )
            d = bc.to_dict()
            for key in ("bc_id", "short_name", "definition", "ncit_code", "status"):
                assert key in d

    def test_to_dict_values_match(self, app):
        with app.app_context():
            bc = BiomedicalConcept(bc_id="C002", short_name="BP", definition="Blood Pressure", ncit_code="C002")
            d = bc.to_dict()
            assert d["bc_id"] == "C002"
            assert d["short_name"] == "BP"

    def test_default_status_is_provisional(self, app):
        with app.app_context():
            bc = BiomedicalConcept(bc_id="C003", short_name="X", definition="Y")
            db.session.add(bc)
            db.session.commit()
            assert bc.status == "provisional"

    def test_to_dict_includes_decs_in_sort_order(self, app):
        with app.app_context():
            bc = BiomedicalConcept(bc_id="C004", short_name="BP", definition="Blood Pressure")
            db.session.add(bc)
            db.session.add_all(
                [
                    DataElementConcept(dec_id="C004.DEC.2", bc_id="C004", dec_label="Diastolic", data_type="decimal", sort_order=1),
                    DataElementConcept(dec_id="C004.DEC.1", bc_id="C004", dec_label="Systolic", data_type="decimal", sort_order=0),
                ]
            )
            db.session.commit()
            decs = bc.to_dict()["decs"]
            assert [d["dec_label"] for d in decs] == ["Systolic", "Diastolic"]

    def test_to_dict_decs_empty_when_none(self, app):
        with app.app_context():
            bc = BiomedicalConcept(bc_id="C005", short_name="X", definition="Y")
            db.session.add(bc)
            db.session.commit()
            assert bc.to_dict()["decs"] == []


class TestResultScales:
    def test_result_scales_alphabetically_sorted(self):
        assert RESULT_SCALES == tuple(sorted(RESULT_SCALES))

    def test_result_scales_contains_expected_values(self):
        assert set(RESULT_SCALES) == {"Quantitative", "Ordinal", "Nominal", "Narrative", "Temporal"}

    def test_split_result_scales_empty(self):
        assert split_result_scales("") == []
        assert split_result_scales(None) == []

    def test_split_result_scales_single(self):
        assert split_result_scales("Quantitative") == ["Quantitative"]

    def test_split_result_scales_multiple_trims_whitespace(self):
        assert split_result_scales("Quantitative; Ordinal ;Nominal") == ["Quantitative", "Ordinal", "Nominal"]

    def test_split_result_scales_ignores_blank_segments(self):
        assert split_result_scales("Quantitative;; Ordinal") == ["Quantitative", "Ordinal"]

    def test_partition_result_scales_all_supported(self):
        supported, unsupported = partition_result_scales("Quantitative; Ordinal")
        assert supported == ["Quantitative", "Ordinal"]
        assert unsupported == []

    def test_partition_result_scales_mixed(self):
        supported, unsupported = partition_result_scales("Quantitative; Qualitative")
        assert supported == ["Quantitative"]
        assert unsupported == ["Qualitative"]

    def test_partition_result_scales_empty(self):
        assert partition_result_scales("") == ([], [])
        assert partition_result_scales(None) == ([], [])


class TestNoteModel:
    def test_defaults(self, app, sample_bc):
        with app.app_context():
            note = Note(bc_id=sample_bc, text="Looks good")
            db.session.add(note)
            db.session.commit()
            assert note.flagged is False
            assert note.resolved is False
            assert note.resolved_at is None
            assert note.created_at is not None

    def test_to_dict_contains_expected_keys(self, app, sample_bc):
        with app.app_context():
            note = Note(bc_id=sample_bc, text="Looks good", created_by="tester")
            db.session.add(note)
            db.session.commit()
            d = note.to_dict()
            for key in ("id", "bc_id", "vlm_group_id", "text", "flagged", "resolved", "resolved_at", "resolved_by", "created_by", "created_at", "updated_at"):
                assert key in d
            assert d["bc_id"] == sample_bc
            assert d["text"] == "Looks good"

    def test_scoped_to_specialization(self, app, sample_spec):
        with app.app_context():
            note = Note(vlm_group_id=sample_spec, text="Spec note")
            db.session.add(note)
            db.session.commit()
            assert note.vlm_group_id == sample_spec
            assert note.bc_id is None

    def test_both_bc_id_and_vlm_group_id_set_raises(self, app, sample_bc, sample_spec):
        with app.app_context():
            db.session.add(Note(bc_id=sample_bc, vlm_group_id=sample_spec, text="x"))
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_neither_bc_id_nor_vlm_group_id_set_raises(self, app):
        with app.app_context():
            db.session.add(Note(text="x"))
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()
