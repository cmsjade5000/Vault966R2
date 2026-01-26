from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import List, Tuple

from api.config import settings

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
STATUS_PATH = ROOT_DIR / "data" / "vault_update_status.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_status() -> dict:
    return {
        "state": "idle",
        "last_run_started": None,
        "last_run_finished": None,
        "last_success_at": None,
        "last_error": None,
        "steps": [],
    }


def load_status() -> dict:
    if not STATUS_PATH.exists():
        return _default_status()
    try:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_status()
    if not isinstance(payload, dict):
        return _default_status()
    merged = _default_status()
    merged.update(payload)
    return merged


def save_status(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATUS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp_path.replace(STATUS_PATH)


def _env_has_any(keys: List[str]) -> bool:
    for key in keys:
        if os.getenv(key):
            return True
    if "TMDB_API_KEY" in keys and settings.tmdb_api_key:
        return True
    if "OMDB_API_KEY" in keys and settings.omdb_api_key:
        return True
    return False


def _task_list() -> List[dict]:
    return [
        {
            "name": "Normalize genres",
            "cmd": ["scripts/normalize_genres.py", "--apply", "--cleanup"],
        },
        {
            "name": "Backfill moods",
            "cmd": ["scripts/backfill_moods.py", "--apply", "--force"],
        },
        {
            "name": "Backfill posters",
            "cmd": ["scripts/backfill_posters.py", "--update-tmdb-id"],
            "requires_any": ["TMDB_API_KEY", "OMDB_API_KEY"],
        },
        {
            "name": "Backfill backdrops",
            "cmd": ["scripts/backfill_backdrops.py", "--apply", "--update-tmdb-id"],
            "requires_any": ["TMDB_API_KEY"],
        },
    ]


def _compact_output(stdout: str, stderr: str) -> str:
    combined = "\n".join([stdout.strip(), stderr.strip()]).strip()
    if not combined:
        return ""
    lines = [line for line in combined.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:240]


def _run_task(command: List[str]) -> Tuple[int, str]:
    full_cmd = [sys.executable, str(ROOT_DIR / command[0]), *command[1:]]
    result = subprocess.run(
        full_cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    summary = _compact_output(result.stdout, result.stderr)
    return result.returncode, summary


def start_update() -> Tuple[bool, dict]:
    status = load_status()
    if status.get("state") == "running":
        return False, status

    status = _default_status()
    status["state"] = "running"
    status["last_run_started"] = _utc_now()
    save_status(status)
    return True, status


def run_update_tasks() -> dict:
    status = load_status()
    status["state"] = "running"
    status["last_run_started"] = status.get("last_run_started") or _utc_now()
    status["last_run_finished"] = None
    status["last_error"] = None
    status["steps"] = []
    save_status(status)

    success = True
    for task in _task_list():
        step = {
            "name": task["name"],
            "status": "pending",
            "summary": "",
            "finished_at": None,
        }

        requires_any = task.get("requires_any")
        if requires_any and not _env_has_any(requires_any):
            step["status"] = "skipped"
            step["summary"] = "missing API key"
            step["finished_at"] = _utc_now()
            status["steps"].append(step)
            save_status(status)
            continue

        script_path = ROOT_DIR / task["cmd"][0]
        if not script_path.exists():
            step["status"] = "skipped"
            step["summary"] = "script missing"
            step["finished_at"] = _utc_now()
            status["steps"].append(step)
            save_status(status)
            continue

        code, summary = _run_task(task["cmd"])
        if code == 0:
            step["status"] = "success"
            step["summary"] = summary
        else:
            step["status"] = "failed"
            step["summary"] = summary or f"exit code {code}"
            success = False
        step["finished_at"] = _utc_now()
        status["steps"].append(step)
        save_status(status)

        if not success:
            status["last_error"] = f"{task['name']} failed"
            break

    status["last_run_finished"] = _utc_now()
    if success:
        status["state"] = "success"
        status["last_success_at"] = status["last_run_finished"]
    else:
        status["state"] = "failed"
    save_status(status)
    return status
