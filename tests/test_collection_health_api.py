from datetime import datetime, timezone

from api.models.maintenance import MaintenanceJob
from api.services import vault_update


def test_refresh_collection_health_recommendation(client, admin_headers) -> None:
    response = client.post(
        "/api/collection-health/recommendation/refresh",
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert "recommendation" in payload
    assert isinstance(payload["recommendation"], str)
    assert payload["recommendation"].strip()


def test_refresh_collection_health_allows_admin_profile_session(
    client, monkeypatch, login_profile
) -> None:
    monkeypatch.setattr(
        "api.routers.collection_health.get_collection_recommendation",
        lambda db, force=False: "session recommendation",
    )
    login_profile(1)

    missing_origin = client.post("/api/collection-health/recommendation/refresh")
    response = client.post(
        "/api/collection-health/recommendation/refresh",
        headers={"Origin": "http://testserver"},
    )

    assert missing_origin.status_code == 403
    assert response.status_code == 200
    assert response.json() == {"recommendation": "session recommendation"}


def test_refresh_collection_health_recommendation_is_throttled(
    client, monkeypatch, login_profile
) -> None:
    monkeypatch.setattr(
        "api.routers.collection_health.get_collection_recommendation",
        lambda db, force=False: "session recommendation",
    )
    login_profile(1)
    headers = {"Origin": "http://testserver"}

    responses = [
        client.post("/api/collection-health/recommendation/refresh", headers=headers)
        for _ in range(11)
    ]

    assert [response.status_code for response in responses[:10]] == [200] * 10
    assert responses[10].status_code == 429


def test_update_run_requires_admin_profile_same_origin(client, monkeypatch, login_profile) -> None:
    task_values = []

    def fake_start_update(task="all", **kwargs):
        task_values.append(task)
        return True, {"state": "running", "task_id": task, "steps": []}

    monkeypatch.setattr(
        "api.routers.collection_health.start_update",
        fake_start_update,
    )
    monkeypatch.setattr(
        "api.routers.collection_health.run_update_tasks",
        lambda task="all", record_job=False: {
            "state": "success",
            "task_id": task,
            "steps": [],
        },
    )
    login_profile(1)

    missing_origin = client.post("/api/collection-health/update/run")
    response = client.post(
        "/api/collection-health/update/run",
        headers={"Origin": "http://testserver"},
    )

    assert missing_origin.status_code == 403
    assert response.status_code == 200
    assert response.json() == {
        "started": True,
        "status": {"state": "running", "task_id": "all", "steps": []},
    }
    assert task_values == ["all"]


def test_update_run_accepts_single_maintenance_task(client, monkeypatch, login_profile) -> None:
    task_values = []

    def fake_start_update(task="all", **kwargs):
        task_values.append(task)
        return True, {"state": "running", "task_id": task, "steps": []}

    monkeypatch.setattr("api.routers.collection_health.start_update", fake_start_update)
    monkeypatch.setattr(
        "api.routers.collection_health.run_update_tasks",
        lambda task="all", record_job=False: {
            "state": "success",
            "task_id": task,
            "steps": [],
        },
    )
    login_profile(1)

    response = client.post(
        "/api/collection-health/update/run?task=posters",
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    assert response.json()["status"]["task_id"] == "posters"
    assert task_values == ["posters"]


def test_update_run_creates_durable_maintenance_job(
    client, monkeypatch, login_profile, db_session, tmp_path
) -> None:
    monkeypatch.setattr(vault_update, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(vault_update, "LOCK_PATH", tmp_path / "update.lock")
    monkeypatch.setattr(
        "api.routers.collection_health.run_update_tasks",
        lambda task="all", record_job=False: {"state": "success", "task_id": task},
    )
    login_profile(1)

    response = client.post(
        "/api/collection-health/update/run?task=genres",
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    jobs = db_session.query(MaintenanceJob).all()
    assert len(jobs) == 1
    assert jobs[0].task_id == "genres"
    assert jobs[0].state == "running"
    assert jobs[0].started_by_profile_id == 1


def test_update_status_prefers_durable_maintenance_history(client, db_session) -> None:
    db_session.add(
        MaintenanceJob(
            run_id="run-1",
            task_id="moods",
            state="success",
            started_at=datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 6, 27, 12, 1, tzinfo=timezone.utc),
            steps=[
                {
                    "id": "moods",
                    "name": "Backfill moods",
                    "status": "success",
                    "summary": "updated: 3",
                    "finished_at": "2026-06-27T12:01:00+00:00",
                }
            ],
            reports=[],
        )
    )
    db_session.commit()

    response = client.get("/api/collection-health/update/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["run_id"] == "run-1"
    assert payload["runs"][0]["source"] == "database"
    assert payload["task_statuses"]["moods"]["state"] == "success"
    assert payload["task_statuses"]["moods"]["summary"] == "updated: 3"


def test_update_run_rejects_unknown_maintenance_task(client, login_profile) -> None:
    login_profile(1)

    response = client.post(
        "/api/collection-health/update/run?task=unknown",
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 400
    assert "Unknown maintenance task" in response.text


def test_update_preview_returns_standardized_maintenance_tasks(client) -> None:
    response = client.get("/api/collection-health/update/preview")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["providers"]) == {"tmdb", "omdb"}
    assert isinstance(payload["providers"]["tmdb"], bool)
    assert isinstance(payload["providers"]["omdb"], bool)
    task_by_id = {task["id"]: task for task in payload["tasks"]}
    assert set(task_by_id) == {"genres", "moods", "posters", "backdrops"}
    assert task_by_id["posters"]["candidate_unit"] == "movies missing posters"
    assert task_by_id["backdrops"]["candidate_count"] >= 1
    assert isinstance(task_by_id["genres"]["sample_titles"], list)
    assert task_by_id["genres"]["report"]["url"].endswith("/update/reports/genres")
    assert task_by_id["genres"]["report"]["path"] == "reports/genre_normalization.csv"


def test_update_report_serves_known_report_file(client, monkeypatch, tmp_path) -> None:
    report_path = tmp_path / "genre_normalization.csv"
    report_path.write_text("movie_id,title\n1,Blade Runner\n", encoding="utf-8")
    monkeypatch.setattr(
        "api.routers.collection_health.report_path_for_task",
        lambda task: report_path if task == "genres" else None,
    )

    response = client.get("/api/collection-health/update/reports/genres")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Blade Runner" in response.text


def test_update_report_rejects_unknown_report(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "api.routers.collection_health.report_path_for_task",
        lambda task: None,
    )

    response = client.get("/api/collection-health/update/reports/unknown")

    assert response.status_code == 404
    assert "Unknown maintenance report" in response.text


def test_update_cancel_requires_admin_profile_same_origin(
    client, monkeypatch, login_profile
) -> None:
    monkeypatch.setattr(
        "api.routers.collection_health.request_cancel",
        lambda: (True, {"state": "running", "cancel_requested": True}),
    )
    login_profile(1)

    missing_origin = client.post("/api/collection-health/update/cancel")
    response = client.post(
        "/api/collection-health/update/cancel",
        headers={"Origin": "http://testserver"},
    )

    assert missing_origin.status_code == 403
    assert response.status_code == 200
    assert response.json() == {
        "requested": True,
        "status": {"state": "running", "cancel_requested": True},
    }
