"""Tests for routes/ncit_alignment.py."""

from unittest.mock import patch

import openpyxl

from extensions import db
from models.alignment import AlignmentJob


class _ImmediateThread:
    """Stand-in for threading.Thread that runs its target synchronously on
    .start(), so route tests can assert final DB state with no real
    background thread and no sleeping/polling."""

    def __init__(self, target, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


def _fake_write_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["NCI Concept Code", "Exists in CDISC"])
    ws.append(["C1", True])
    wb.save(path)


def _popen_side_effect(populate_proc, augment_proc):
    def _effect(cmd, **kwargs):
        if "src.populate_complete_list" in cmd:
            _fake_write_xlsx(cmd[cmd.index("--output") + 1])
            return populate_proc
        return augment_proc

    return _effect


class TestIndex:
    def test_empty_state_returns_200(self, client):
        r = client.get("/ncit-alignment/")
        assert r.status_code == 200

    def test_shows_most_recent_job(self, client, app):
        with app.app_context():
            db.session.add(AlignmentJob(status="completed", augment_cdisc_hits=5))
            db.session.commit()
        r = client.get("/ncit-alignment/")
        assert r.status_code == 200


class TestStart:
    def test_creates_job_and_runs_to_completion(self, client, app, tmp_path, monkeypatch):
        from unittest.mock import MagicMock

        monkeypatch.setattr(app, "instance_path", str(tmp_path))

        populate_proc = MagicMock(stderr=iter(["  batches 1/1  elapsed= 1.0s  rate= 1.0 b/s  eta= 0.0s\n"]), returncode=0)
        augment_proc = MagicMock(stderr=iter(["Wrote 2 rows (1 CDISC hits) to report.xlsx — 0.1s\n"]), returncode=0)

        with (
            patch("services.alignment_runner.threading.Thread", _ImmediateThread),
            patch("services.alignment_runner.subprocess.Popen", side_effect=_popen_side_effect(populate_proc, augment_proc)),
        ):
            r = client.post("/ncit-alignment/start")

        assert r.status_code == 302
        with app.app_context():
            job = AlignmentJob.query.first()
            assert job.status == "completed"
            assert job.augment_cdisc_hits == 1

    def test_rejects_concurrent_start(self, client, app):
        with app.app_context():
            db.session.add(AlignmentJob(status="running_populate"))
            db.session.commit()

        with patch("services.alignment_runner.threading.Thread") as mock_thread:
            r = client.post("/ncit-alignment/start")
            mock_thread.assert_not_called()

        assert r.status_code == 302
        with app.app_context():
            assert AlignmentJob.query.count() == 1

    def test_rejects_concurrent_start_xhr_returns_409(self, client, app):
        with app.app_context():
            db.session.add(AlignmentJob(status="running_populate"))
            db.session.commit()

        with patch("services.alignment_runner.threading.Thread"):
            r = client.post("/ncit-alignment/start", headers={"X-Requested-With": "XMLHttpRequest"})

        assert r.status_code == 409


class TestStatus:
    def test_no_job_returns_none_status(self, client):
        r = client.get("/ncit-alignment/status")
        assert r.status_code == 200
        assert r.get_json() == {"status": "none"}

    def test_returns_job_shape_without_raw_paths(self, client, app):
        with app.app_context():
            db.session.add(
                AlignmentJob(
                    status="running_populate",
                    populate_batches_done=5,
                    populate_batches_total=10,
                    xlsx_path="/should/not/leak.xlsx",
                )
            )
            db.session.commit()

        r = client.get("/ncit-alignment/status")
        data = r.get_json()
        assert data["status"] == "running_populate"
        assert data["populate_batches_done"] == 5
        assert data["populate_batches_total"] == 10
        assert data["xlsx_ready"] is False
        assert data["json_ready"] is False
        assert "xlsx_path" not in data
        assert "json_path" not in data


class TestDownloads:
    def _completed_job_with_files(self, app, tmp_path):
        xlsx_path = tmp_path / "report.xlsx"
        json_path = tmp_path / "report.json"
        xlsx_path.write_bytes(b"fake-xlsx-bytes")
        json_path.write_text("[]")
        with app.app_context():
            job = AlignmentJob(status="completed", xlsx_path=str(xlsx_path), json_path=str(json_path))
            db.session.add(job)
            db.session.commit()
            return job.id

    def test_download_xlsx_200(self, client, app, tmp_path):
        job_id = self._completed_job_with_files(app, tmp_path)
        r = client.get(f"/ncit-alignment/download/xlsx/{job_id}")
        assert r.status_code == 200
        assert r.data == b"fake-xlsx-bytes"

    def test_download_json_200(self, client, app, tmp_path):
        job_id = self._completed_job_with_files(app, tmp_path)
        r = client.get(f"/ncit-alignment/download/json/{job_id}")
        assert r.status_code == 200
        assert r.data == b"[]"

    def test_download_unknown_job_404(self, client):
        assert client.get("/ncit-alignment/download/xlsx/999999").status_code == 404
        assert client.get("/ncit-alignment/download/json/999999").status_code == 404

    def test_download_not_yet_completed_404(self, client, app):
        with app.app_context():
            job = AlignmentJob(status="running_populate")
            db.session.add(job)
            db.session.commit()
            job_id = job.id
        assert client.get(f"/ncit-alignment/download/xlsx/{job_id}").status_code == 404
        assert client.get(f"/ncit-alignment/download/json/{job_id}").status_code == 404

    def test_download_missing_file_on_disk_404(self, client, app, tmp_path):
        missing = str(tmp_path / "gone.xlsx")
        with app.app_context():
            job = AlignmentJob(status="completed", xlsx_path=missing, json_path=missing)
            db.session.add(job)
            db.session.commit()
            job_id = job.id
        assert client.get(f"/ncit-alignment/download/xlsx/{job_id}").status_code == 404
        assert client.get(f"/ncit-alignment/download/json/{job_id}").status_code == 404
