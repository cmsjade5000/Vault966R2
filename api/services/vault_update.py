from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, List, Tuple

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.db import SessionLocal
from api.models.maintenance import MaintenanceJob
from api.models.movie import Movie
from core.genres import split_and_normalize
from core.moods import score_moods

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
STATUS_PATH = ROOT_DIR / "data" / "vault_update_status.json"
LOCK_PATH = ROOT_DIR / "data" / "vault_update.lock"
RUN_STALE_AFTER = timedelta(hours=6)
TASK_TIMEOUT_SECONDS = 20 * 60
RUN_HISTORY_LIMIT = 8


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_status() -> dict:
    return {
        "state": "idle",
        "last_run_started": None,
        "last_run_finished": None,
        "last_success_at": None,
        "last_error": None,
        "lock_path": str(LOCK_PATH),
        "task_id": "all",
        "cancel_requested": False,
        "cancel_requested_at": None,
        "steps": [],
        "runs": [],
        "task_statuses": {},
    }


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_stale_running_status(status: dict) -> bool:
    if status.get("state") != "running":
        return False
    started = _parse_timestamp(status.get("last_run_started"))
    if started is None:
        return True
    return datetime.now(timezone.utc) - started > RUN_STALE_AFTER


def load_status() -> dict:
    if not STATUS_PATH.exists():
        status = _default_status()
        status["task_statuses"] = build_task_statuses(status)
        return status
    try:
        payload = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        status = _default_status()
        status["task_statuses"] = build_task_statuses(status)
        return status
    if not isinstance(payload, dict):
        status = _default_status()
        status["task_statuses"] = build_task_statuses(status)
        return status
    merged = _default_status()
    merged.update(payload)
    merged["task_statuses"] = build_task_statuses(merged)
    return merged


def save_status(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    status["task_statuses"] = build_task_statuses(status)
    tmp_path = STATUS_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp_path.replace(STATUS_PATH)


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        return


def request_cancel() -> Tuple[bool, dict]:
    status = load_status()
    if status.get("state") != "running":
        return False, status
    status["cancel_requested"] = True
    status["cancel_requested_at"] = _utc_now()
    status["last_error"] = "cancellation requested"
    save_status(status)
    return True, status


def _cancel_requested() -> bool:
    return bool(load_status().get("cancel_requested"))


def _acquire_lock() -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        status = load_status()
        if not _is_stale_running_status(status):
            return False
        _release_lock()
        try:
            descriptor = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(_utc_now())
    return True


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
            "id": "genres",
            "name": "Normalize genres",
            "description": "Clean genre labels and remove unused genre rows.",
            "cmd": ["scripts/normalize_genres.py", "--apply", "--cleanup"],
            "preview_unit": "movies with genre cleanup",
            "report_path": "reports/genre_normalization.csv",
        },
        {
            "id": "moods",
            "name": "Backfill moods",
            "description": "Recompute mood tags from the current genre rules.",
            "cmd": ["scripts/backfill_moods.py", "--apply", "--force"],
            "preview_unit": "movies with mood changes",
            "report_path": "reports/mood_backfill.csv",
        },
        {
            "id": "posters",
            "name": "Backfill posters",
            "description": "Find missing posters with TMDb or OMDb when API access is available.",
            "cmd": ["scripts/backfill_posters.py", "--update-tmdb-id"],
            "requires_any": ["TMDB_API_KEY", "OMDB_API_KEY"],
            "preview_unit": "movies missing posters",
            "report_path": "reports/poster_backfill.csv",
        },
        {
            "id": "backdrops",
            "name": "Backfill backdrops",
            "description": "Find missing backdrops with TMDb when API access is available.",
            "cmd": ["scripts/backfill_backdrops.py", "--apply", "--update-tmdb-id"],
            "requires_any": ["TMDB_API_KEY"],
            "preview_unit": "movies missing backdrops",
            "report_path": "reports/backdrop_backfill.csv",
        },
    ]


def _task_by_id(task_id: str) -> dict | None:
    for task in _task_list():
        if task["id"] == task_id:
            return task
    return None


def task_ids() -> list[str]:
    return [task["id"] for task in _task_list()]


def _task_list_for(task_id: str | None = None) -> List[dict]:
    if task_id is None or task_id == "all":
        return _task_list()
    task = _task_by_id(task_id)
    if task is None:
        raise ValueError(f"unknown maintenance task: {task_id}")
    return [task]


def _task_report_path(task: dict) -> pathlib.Path:
    return ROOT_DIR / task["report_path"]


def report_path_for_task(task_id: str) -> pathlib.Path | None:
    task = _task_by_id(task_id)
    if task is None:
        return None
    return _task_report_path(task)


def _report_meta(task: dict) -> dict[str, Any]:
    path = _task_report_path(task)
    exists = path.exists()
    return {
        "task_id": task["id"],
        "task_name": task["name"],
        "path": task["report_path"],
        "url": f"/api/collection-health/update/reports/{task['id']}",
        "exists": exists,
        "updated_at": (
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            if exists
            else None
        ),
    }


def _recent_runs(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [run for run in value[:RUN_HISTORY_LIMIT] if isinstance(run, dict)]


def _steps_by_task(steps: object) -> dict[str, dict[str, Any]]:
    if not isinstance(steps, list):
        return {}
    mapped = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        task_id = step.get("id")
        if isinstance(task_id, str):
            mapped[task_id] = step
    return mapped


def _task_status_from_step(
    task: dict,
    *,
    state: str,
    started_at: object,
    finished_at: object,
    step: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": task["id"],
        "name": task["name"],
        "state": step.get("status") if step else state,
        "summary": step.get("summary") if step else "",
        "started_at": started_at,
        "finished_at": step.get("finished_at") if step else finished_at,
        "report": step.get("report") if step and step.get("report") else _report_meta(task),
    }


def build_task_statuses(status: dict) -> dict[str, dict[str, Any]]:
    statuses = {
        task["id"]: {
            "id": task["id"],
            "name": task["name"],
            "state": "idle",
            "summary": "",
            "started_at": None,
            "finished_at": None,
            "report": _report_meta(task),
        }
        for task in _task_list()
    }

    for run in _recent_runs(status.get("runs")):
        task_id = run.get("task_id") if isinstance(run.get("task_id"), str) else "all"
        try:
            tasks = _task_list_for(task_id)
        except ValueError:
            continue
        steps = _steps_by_task(run.get("steps"))
        for task in tasks:
            current = statuses[task["id"]]
            if current["state"] != "idle":
                continue
            step = steps.get(task["id"])
            statuses[task["id"]] = _task_status_from_step(
                task,
                state=str(run.get("state") or "unknown"),
                started_at=run.get("started_at"),
                finished_at=run.get("finished_at"),
                step=step,
            )

    if status.get("state") == "running":
        task_id = status.get("task_id") if isinstance(status.get("task_id"), str) else "all"
        try:
            tasks = _task_list_for(task_id)
        except ValueError:
            tasks = []
        steps = _steps_by_task(status.get("steps"))
        for task in tasks:
            step = steps.get(task["id"])
            statuses[task["id"]] = _task_status_from_step(
                task,
                state="running",
                started_at=status.get("last_run_started"),
                finished_at=None,
                step=step,
            )

    return statuses


def _append_run(status: dict) -> None:
    run = {
        "run_id": status.get("run_id"),
        "task_id": status.get("task_id") or "all",
        "state": status.get("state"),
        "started_at": status.get("last_run_started"),
        "finished_at": status.get("last_run_finished"),
        "last_error": status.get("last_error"),
        "cancel_requested_at": status.get("cancel_requested_at"),
        "steps": status.get("steps") if isinstance(status.get("steps"), list) else [],
        "reports": [
            _report_meta(task)
            for task in _task_list_for(status.get("task_id") or "all")
            if task.get("report_path")
        ],
    }
    runs = [run, *_recent_runs(status.get("runs"))]
    status["runs"] = runs[:RUN_HISTORY_LIMIT]


def _job_to_run(job: MaintenanceJob) -> dict[str, Any]:
    return {
        "run_id": job.run_id,
        "task_id": job.task_id,
        "state": job.state,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "last_error": job.last_error,
        "cancel_requested_at": None,
        "steps": job.steps if isinstance(job.steps, list) else [],
        "reports": job.reports if isinstance(job.reports, list) else [],
        "started_by_profile_id": job.started_by_profile_id,
        "source": "database",
    }


def recent_job_runs(db: Session, limit: int = RUN_HISTORY_LIMIT) -> list[dict[str, Any]]:
    jobs = db.scalars(
        select(MaintenanceJob).order_by(desc(MaintenanceJob.started_at)).limit(limit)
    ).all()
    return [_job_to_run(job) for job in jobs]


def merge_durable_job_history(status: dict, db: Session) -> dict:
    durable_runs = recent_job_runs(db)
    if not durable_runs:
        status["task_statuses"] = build_task_statuses(status)
        return status
    status["runs"] = durable_runs
    status["task_statuses"] = build_task_statuses(status)
    return status


def _parse_status_time(value: object) -> datetime:
    parsed = _parse_timestamp(value)
    return parsed or datetime.now(timezone.utc)


def create_job_record(
    db: Session,
    status: dict,
    *,
    started_by_profile_id: int | None = None,
) -> MaintenanceJob:
    job = MaintenanceJob(
        run_id=str(status.get("run_id") or status.get("last_run_started") or _utc_now()),
        task_id=str(status.get("task_id") or "all"),
        state=str(status.get("state") or "running"),
        started_by_profile_id=started_by_profile_id,
        started_at=_parse_status_time(status.get("last_run_started")),
        finished_at=None,
        last_error=status.get("last_error"),
        steps=status.get("steps") if isinstance(status.get("steps"), list) else [],
        reports=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def finish_job_record(status: dict, db: Session | None = None) -> None:
    run_id = status.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return

    owns_session = db is None
    session = db or SessionLocal()
    try:
        job = session.scalar(select(MaintenanceJob).where(MaintenanceJob.run_id == run_id))
        if job is None:
            return
        job.state = str(status.get("state") or "unknown")
        job.task_id = str(status.get("task_id") or job.task_id or "all")
        job.finished_at = _parse_timestamp(status.get("last_run_finished"))
        job.last_error = status.get("last_error")
        job.steps = status.get("steps") if isinstance(status.get("steps"), list) else []
        reports = []
        for task in _task_list_for(job.task_id):
            if task.get("report_path"):
                reports.append(_report_meta(task))
        job.reports = reports
        session.add(job)
        session.commit()
    finally:
        if owns_session:
            session.close()


def _sample_titles(movies: list[Movie], limit: int = 3) -> list[str]:
    titles = []
    for movie in movies[:limit]:
        label = movie.title
        if movie.year:
            label = f"{label} ({movie.year})"
        titles.append(label)
    return titles


def _genre_preview(db: Session) -> tuple[int, list[str]]:
    movies = db.query(Movie).options(selectinload(Movie.genres)).order_by(Movie.id).all()
    candidates = []
    for movie in movies:
        current = [genre.name for genre in movie.genres if getattr(genre, "name", None)]
        normalized = split_and_normalize(current)
        if normalized and set(current) != set(normalized):
            candidates.append(movie)
    return len(candidates), _sample_titles(candidates)


def _mood_preview(db: Session) -> tuple[int, list[str]]:
    movies = (
        db.query(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .order_by(Movie.id)
        .all()
    )
    candidates = []
    for movie in movies:
        current = {mood.name for mood in movie.moods if getattr(mood, "name", None)}
        genres = [genre.name for genre in movie.genres if getattr(genre, "name", None)]
        computed = set(score_moods(genres, max_moods=1, min_score=1))
        if computed and current != computed:
            candidates.append(movie)
    return len(candidates), _sample_titles(candidates)


def _missing_artwork_preview(db: Session, field_name: str) -> tuple[int, list[str]]:
    field = getattr(Movie, field_name)
    movies = (
        db.query(Movie)
        .filter(or_(field.is_(None), field == "", field == "N/A"))
        .order_by(Movie.id)
        .all()
    )
    return len(movies), _sample_titles(movies)


def build_update_preview(db: Session) -> dict[str, Any]:
    provider_access = {
        "tmdb": _env_has_any(["TMDB_API_KEY"]),
        "omdb": _env_has_any(["OMDB_API_KEY"]),
    }
    previews = {
        "genres": _genre_preview(db),
        "moods": _mood_preview(db),
        "posters": _missing_artwork_preview(db, "poster_url"),
        "backdrops": _missing_artwork_preview(db, "backdrop_url"),
    }
    tasks = []
    for task in _task_list():
        count, sample_titles = previews[task["id"]]
        required_keys = task.get("requires_any") or []
        is_ready = not required_keys or _env_has_any(required_keys)
        tasks.append(
            {
                "id": task["id"],
                "name": task["name"],
                "description": task["description"],
                "candidate_count": count,
                "candidate_unit": task["preview_unit"],
                "sample_titles": sample_titles,
                "requires_any": required_keys,
                "ready": is_ready,
                "blocked_reason": "" if is_ready else "missing API key",
                "report": _report_meta(task),
            }
        )
    return {"providers": provider_access, "tasks": tasks}


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
    try:
        result = subprocess.run(
            full_cmd,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
            timeout=TASK_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        summary = _compact_output(exc.stdout or "", exc.stderr or "")
        return 124, summary or f"timed out after {TASK_TIMEOUT_SECONDS} seconds"
    summary = _compact_output(result.stdout, result.stderr)
    return result.returncode, summary


def start_update(
    task_id: str | None = None,
    *,
    db: Session | None = None,
    started_by_profile_id: int | None = None,
    record_job: bool = False,
) -> Tuple[bool, dict]:
    _task_list_for(task_id)
    status = load_status()
    recent_runs = _recent_runs(status.get("runs"))
    if status.get("state") == "running" and not _is_stale_running_status(status):
        return False, status
    if not _acquire_lock():
        status = load_status()
        status["state"] = "running"
        status["last_error"] = "metadata maintenance already running"
        return False, status

    status = _default_status()
    status["state"] = "running"
    status["task_id"] = task_id or "all"
    status["cancel_requested"] = False
    status["cancel_requested_at"] = None
    status["last_run_started"] = _utc_now()
    status["run_id"] = status["last_run_started"]
    status["runs"] = recent_runs
    save_status(status)
    if record_job and db is not None:
        create_job_record(db, status, started_by_profile_id=started_by_profile_id)
    return True, status


def run_update_tasks(task_id: str | None = None, record_job: bool = False) -> dict:
    try:
        tasks = _task_list_for(task_id)
        status = load_status()
        status["state"] = "running"
        status["task_id"] = task_id or status.get("task_id") or "all"
        status["last_run_started"] = status.get("last_run_started") or _utc_now()
        status["last_run_finished"] = None
        status["last_error"] = None
        status["steps"] = []
        save_status(status)

        success = True
        cancelled = False
        for task in tasks:
            if _cancel_requested():
                cancelled = True
                status = load_status()
                break

            step = {
                "id": task["id"],
                "name": task["name"],
                "status": "pending",
                "summary": "",
                "finished_at": None,
                "report": _report_meta(task),
            }

            requires_any = task.get("requires_any")
            if requires_any and not _env_has_any(requires_any):
                step["status"] = "skipped"
                step["summary"] = "missing API key"
                step["finished_at"] = _utc_now()
                status["steps"].append(step)
                save_status(status)
                if _cancel_requested():
                    cancelled = True
                    status = load_status()
                    break
                continue

            script_path = ROOT_DIR / task["cmd"][0]
            if not script_path.exists():
                step["status"] = "skipped"
                step["summary"] = "script missing"
                step["finished_at"] = _utc_now()
                status["steps"].append(step)
                save_status(status)
                if _cancel_requested():
                    cancelled = True
                    status = load_status()
                    break
                continue

            code, summary = _run_task(task["cmd"])
            if code == 0:
                step["status"] = "success"
                step["summary"] = summary
            else:
                step["status"] = "failed"
                step["summary"] = summary or f"exit code {code}"
                success = False
            current_status = load_status()
            if current_status.get("cancel_requested"):
                status["cancel_requested"] = True
                status["cancel_requested_at"] = current_status.get("cancel_requested_at")
            step["finished_at"] = _utc_now()
            status["steps"].append(step)
            save_status(status)

            if not success:
                status["last_error"] = f"{task['name']} failed"
                break

            if _cancel_requested():
                cancelled = True
                status = load_status()
                break

        status["last_run_finished"] = _utc_now()
        if cancelled:
            status["state"] = "cancelled"
            status["last_error"] = "maintenance cancelled"
            status["cancel_requested"] = False
        elif success:
            status["state"] = "success"
            status["last_success_at"] = status["last_run_finished"]
        else:
            status["state"] = "failed"
        _append_run(status)
        if record_job:
            finish_job_record(status)
        save_status(status)
        return status
    finally:
        _release_lock()
