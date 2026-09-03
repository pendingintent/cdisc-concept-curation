"""Tests for services.alignment_runner. No real subprocess or thread is ever spawned."""

import json
import sys
from unittest.mock import MagicMock, patch

import openpyxl

from extensions import db
from models.alignment import AlignmentJob
from services import alignment_runner


def _mock_proc(stderr_lines, returncode=0):
    proc = MagicMock()
    proc.stderr = iter(stderr_lines)
    proc.returncode = returncode
    proc.wait = MagicMock(return_value=returncode)
    return proc


class TestRunPopulate:
    def test_parses_progress_from_stderr(self, app):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()

            lines = [
                "Fetching NCIt code list...\n",
                "  batches 1/10  elapsed=  3.1s  rate= 0.32 b/s  eta=27.9s\n",
                "  batches 5/10  elapsed= 15.0s  rate= 0.33 b/s  eta=15.0s\n",
                "  batches 10/10  elapsed= 30.0s  rate= 0.33 b/s  eta= 0.0s\n",
            ]
            proc = _mock_proc(lines, returncode=0)
            with patch("services.alignment_runner.subprocess.Popen", return_value=proc) as mock_popen:
                alignment_runner._run_populate(app, job, "/tmp/report.xlsx")

            assert job.populate_batches_done == 10
            assert job.populate_batches_total == 10

            cmd, kwargs = mock_popen.call_args
            assert cmd[0][0] == sys.executable
            assert "-m" in cmd[0] and "src.populate_complete_list" in cmd[0]
            assert "--output" in cmd[0] and "/tmp/report.xlsx" in cmd[0]
            assert kwargs["cwd"] == app.config["ALIGNMENT_SUBMODULE_DIR"]

    def test_nonzero_exit_raises(self, app):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()

            proc = _mock_proc(["some error\n"], returncode=1)
            with patch("services.alignment_runner.subprocess.Popen", return_value=proc):
                try:
                    alignment_runner._run_populate(app, job, "/tmp/report.xlsx")
                    assert False, "expected RuntimeError"
                except RuntimeError:
                    pass


class TestRunAugment:
    def test_parses_final_summary_line_with_commas(self, app):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()

            lines = [
                "Fetching CDISC biomedical concepts index...\n",
                "  1,345 CDISC BC entries indexed\n",
                "Wrote 212,345 rows (8,901 CDISC hits) to /tmp/report.xlsx — 24.7s\n",
            ]
            proc = _mock_proc(lines, returncode=0)
            with patch("services.alignment_runner.subprocess.Popen", return_value=proc) as mock_popen:
                alignment_runner._run_augment(app, job, "/tmp/report.xlsx")

            assert job.augment_rows_total == 212345
            assert job.augment_cdisc_hits == 8901

            _, kwargs = mock_popen.call_args
            assert kwargs["env"]["CDISC_API_KEY"] == app.config["CDISC_API_KEY"]

    def test_nonzero_exit_raises(self, app):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()

            proc = _mock_proc(["some error\n"], returncode=1)
            with patch("services.alignment_runner.subprocess.Popen", return_value=proc):
                try:
                    alignment_runner._run_augment(app, job, "/tmp/report.xlsx")
                    assert False, "expected RuntimeError"
                except RuntimeError:
                    pass


class TestRunPipeline:
    def test_stage_one_failure_short_circuits_stage_two(self, app, tmp_path):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()
            job_id = job.id

        # _run_pipeline pushes its own app context (as the real background
        # thread would); re-enter a fresh one afterward to read committed
        # state, rather than nesting inside the one above — a nested context
        # gets its own scoped session, leaving this outer one's identity map
        # stale for anything committed inside it.
        failing_proc = _mock_proc(["boom\n"], returncode=1)
        with patch("services.alignment_runner.subprocess.Popen", return_value=failing_proc) as mock_popen:
            alignment_runner._run_pipeline(app, job_id, output_dir=str(tmp_path))
        assert mock_popen.call_count == 1

        with app.app_context():
            reloaded = db.session.get(AlignmentJob, job_id)
            assert reloaded.status == "failed"
            assert reloaded.error_message

    def test_success_path_marks_completed(self, app, tmp_path):
        with app.app_context():
            job = AlignmentJob()
            db.session.add(job)
            db.session.commit()
            job_id = job.id

        populate_lines = ["  batches 1/1  elapsed= 1.0s  rate= 1.0 b/s  eta= 0.0s\n"]
        augment_lines = ["Wrote 2 rows (1 CDISC hits) to report.xlsx — 0.1s\n"]
        populate_proc = _mock_proc(populate_lines, returncode=0)
        augment_proc = _mock_proc(augment_lines, returncode=0)

        def _fake_write_xlsx(path):
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["NCI Concept Code", "Exists in CDISC"])
            ws.append(["C1", True])
            wb.save(path)

        def _popen_side_effect(cmd, **kwargs):
            if "src.populate_complete_list" in cmd:
                _fake_write_xlsx(cmd[cmd.index("--output") + 1])
                return populate_proc
            return augment_proc

        with patch("services.alignment_runner.subprocess.Popen", side_effect=_popen_side_effect):
            alignment_runner._run_pipeline(app, job_id, output_dir=str(tmp_path))

        with app.app_context():
            reloaded = db.session.get(AlignmentJob, job_id)
            assert reloaded.status == "completed"
            assert reloaded.completed_at is not None
            assert reloaded.xlsx_path and reloaded.json_path
            with open(reloaded.json_path) as f:
                records = json.load(f)
            assert records == [{"NCI Concept Code": "C1", "Exists in CDISC": True}]


class TestWriteJsonExport:
    def test_produces_list_of_dicts(self, tmp_path):
        xlsx_path = str(tmp_path / "in.xlsx")
        json_path = str(tmp_path / "out.json")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Code", "Name"])
        ws.append(["C1", "First"])
        ws.append(["C2", "Second"])
        wb.save(xlsx_path)

        alignment_runner._write_json_export(xlsx_path, json_path)

        with open(json_path) as f:
            records = json.load(f)
        assert records == [
            {"Code": "C1", "Name": "First"},
            {"Code": "C2", "Name": "Second"},
        ]


class TestStartJob:
    def test_raises_when_a_job_is_already_running(self, app):
        with app.app_context():
            db.session.add(AlignmentJob(status="running_populate"))
            db.session.commit()

            with patch("services.alignment_runner.threading.Thread") as mock_thread:
                try:
                    alignment_runner.start_job()
                    assert False, "expected RuntimeError"
                except RuntimeError:
                    pass
                mock_thread.assert_not_called()

            assert AlignmentJob.query.count() == 1

    def test_creates_job_and_spawns_daemon_thread(self, app):
        with app.app_context():
            with patch("services.alignment_runner.threading.Thread") as mock_thread:
                job = alignment_runner.start_job(actor="tester")

            assert job.id is not None
            assert job.status == "pending"
            assert job.created_by == "tester"
            assert AlignmentJob.query.count() == 1

            _, kwargs = mock_thread.call_args
            assert kwargs["daemon"] is True
            assert kwargs["target"] is alignment_runner._run_pipeline
            assert kwargs["args"][1] == job.id
            mock_thread.return_value.start.assert_called_once()

    def test_succeeds_again_once_prior_job_is_terminal(self, app):
        with app.app_context():
            db.session.add(AlignmentJob(status="completed"))
            db.session.commit()

            with patch("services.alignment_runner.threading.Thread"):
                job = alignment_runner.start_job()

            assert job.status == "pending"
            assert AlignmentJob.query.count() == 2
