from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone

from api.services import vault_update


def _use_temp_state(monkeypatch, tmp_path):
    monkeypatch.setattr(vault_update, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(vault_update, "LOCK_PATH", tmp_path / "update.lock")


def test_start_update_creates_lock_and_blocks_second_start(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)

    started, status = vault_update.start_update()
    second_started, second_status = vault_update.start_update()

    assert started is True
    assert status["state"] == "running"
    assert vault_update.LOCK_PATH.exists()
    assert second_started is False
    assert second_status["state"] == "running"


def test_load_status_initializes_task_statuses(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)

    status = vault_update.load_status()

    assert set(status["task_statuses"]) == {"genres", "moods", "posters", "backdrops"}
    assert status["task_statuses"]["genres"]["state"] == "idle"
    assert status["task_statuses"]["genres"]["report"]["path"] == (
        "reports/genre_normalization.csv"
    )


def test_start_update_recovers_stale_running_status(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)
    stale_started_at = datetime.now(timezone.utc) - timedelta(hours=7)
    vault_update.save_status(
        {
            "state": "running",
            "last_run_started": stale_started_at.isoformat(),
            "steps": [],
        }
    )
    vault_update.LOCK_PATH.write_text("stale", encoding="utf-8")

    started, status = vault_update.start_update()

    assert started is True
    assert status["state"] == "running"
    assert vault_update.LOCK_PATH.read_text(encoding="utf-8") != "stale"


def test_request_cancel_marks_running_status(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)
    vault_update.start_update("genres")

    requested, status = vault_update.request_cancel()

    assert requested is True
    assert status["cancel_requested"] is True
    assert status["cancel_requested_at"]


def test_request_cancel_ignores_idle_status(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)

    requested, status = vault_update.request_cancel()

    assert requested is False
    assert status["state"] == "idle"


def test_run_update_tasks_honors_cancel_before_next_task(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "one.py").write_text("print('one')", encoding="utf-8")
    (scripts_dir / "two.py").write_text("print('two')", encoding="utf-8")
    monkeypatch.setattr(vault_update, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(
        vault_update,
        "_task_list",
        lambda: [
            {
                "id": "one",
                "name": "One",
                "cmd": ["scripts/one.py"],
                "report_path": "reports/one.csv",
            },
            {
                "id": "two",
                "name": "Two",
                "cmd": ["scripts/two.py"],
                "report_path": "reports/two.csv",
            },
        ],
    )
    calls = []

    def record_run(command):
        calls.append(command)
        vault_update.request_cancel()
        return 0, "done"

    monkeypatch.setattr(vault_update, "_run_task", record_run)

    vault_update.start_update("all")
    status = vault_update.run_update_tasks("all")

    assert status["state"] == "cancelled"
    assert status["last_error"] == "maintenance cancelled"
    assert [step["id"] for step in status["steps"]] == ["one"]
    assert calls == [["scripts/one.py"]]


def test_run_update_tasks_releases_lock_after_success(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "fake.py").write_text("print('ok')", encoding="utf-8")
    monkeypatch.setattr(vault_update, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(
        vault_update,
        "_task_list",
        lambda: [
            {
                "id": "fake",
                "name": "Fake task",
                "cmd": ["scripts/fake.py"],
                "report_path": "reports/fake.csv",
            }
        ],
    )
    monkeypatch.setattr(vault_update, "_run_task", lambda command: (0, "done"))

    started, _ = vault_update.start_update()
    status = vault_update.run_update_tasks()

    assert started is True
    assert status["state"] == "success"
    assert status["steps"][0]["summary"] == "done"
    assert status["runs"][0]["state"] == "success"
    assert status["runs"][0]["reports"][0]["task_id"] == "fake"
    assert not vault_update.LOCK_PATH.exists()


def test_run_update_tasks_can_run_single_task(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "one.py").write_text("print('one')", encoding="utf-8")
    (scripts_dir / "two.py").write_text("print('two')", encoding="utf-8")
    monkeypatch.setattr(vault_update, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(
        vault_update,
        "_task_list",
        lambda: [
            {
                "id": "one",
                "name": "One",
                "cmd": ["scripts/one.py"],
                "report_path": "reports/one.csv",
            },
            {
                "id": "two",
                "name": "Two",
                "cmd": ["scripts/two.py"],
                "report_path": "reports/two.csv",
            },
        ],
    )
    calls = []

    def record_run(command):
        calls.append(command)
        return 0, "done"

    monkeypatch.setattr(vault_update, "_run_task", record_run)

    started, _ = vault_update.start_update("two")
    status = vault_update.run_update_tasks("two")

    assert started is True
    assert status["task_id"] == "two"
    assert [step["id"] for step in status["steps"]] == ["two"]
    assert status["task_statuses"]["two"]["state"] == "success"
    assert status["task_statuses"]["one"]["state"] == "idle"
    assert calls == [["scripts/two.py"]]


def test_start_update_preserves_recent_run_history(monkeypatch, tmp_path):
    _use_temp_state(monkeypatch, tmp_path)
    vault_update.save_status(
        {
            "state": "success",
            "runs": [{"run_id": str(index)} for index in range(12)],
        }
    )

    started, status = vault_update.start_update("genres")

    assert started is True
    assert status["task_id"] == "genres"
    assert len(status["runs"]) == vault_update.RUN_HISTORY_LIMIT
    assert status["runs"][0]["run_id"] == "0"


def test_report_path_for_task_is_limited_to_known_tasks() -> None:
    report_path = vault_update.report_path_for_task("genres")

    assert report_path is not None
    assert report_path.name == "genre_normalization.csv"
    assert vault_update.report_path_for_task("../vault.db") is None


def test_run_task_reports_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(vault_update, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(vault_update, "TASK_TIMEOUT_SECONDS", 1)

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(vault_update.subprocess, "run", raise_timeout)

    code, summary = vault_update._run_task(["scripts/slow.py"])

    assert code == 124
    assert summary == "timed out after 1 seconds"
