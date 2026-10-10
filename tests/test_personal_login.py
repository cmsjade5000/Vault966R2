"""Synthetic-only account and archive acceptance tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.config import settings
from api.db import Base
from api.models.movie import Movie
from api.models.profile import (
    AppSetup,
    MoviePreference,
    Profile,
    ProfileArchiveBatch,
    ProfileCredential,
)
from api.services.credentials import build_profile_credential
from api.services.profile_archive import prepare_personal_fresh_start, restore_profile_archive
from api.services.profiles import get_profiles
from api.services.session import (
    SESSION_COOKIE_NAME,
    get_session_secret,
    parse_session_token,
)
from api.services.setup import (
    SetupError,
    create_first_profile_setup,
    matching_db_credential_profile_id,
)
from tests.test_setup import _clear_legacy_credentials
from tests.setup_support import local_browser, authorize_setup, SYNTHETIC_CODE
from api.services.setup_grants import issue_setup_grant, bind_setup_grant


@pytest.fixture
def client(client):
    with local_browser() as local:
        yield local


ORIGIN = {"Origin": "http://127.0.0.1"}
JSON = {**ORIGIN, "Accept": "application/json"}
PASSWORD = "synthetic-password-only"


def owner(client, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    authorize_setup(client)
    result = client.post(
        "/setup",
        headers=ORIGIN,
        data={
            "profile_name": "Cory",
            "access_key": "ignored-hidden-override",
            "passcode": PASSWORD,
            "passcode_confirm": PASSWORD,
        },
        follow_redirects=False,
    )
    assert result.status_code == 303
    return result


def signin(client, name="Cory", password=PASSWORD, route="/login", **extra):
    return client.post(
        route,
        headers=JSON,
        data={"access_key": name, "passcode": password, **extra},
        follow_redirects=False,
    )


def test_personal_signin_switch_cancel_and_roles(client, db_session, monkeypatch):
    owner(client, monkeypatch)
    current_cookie = client.cookies.get(SESSION_COOKIE_NAME)
    admin_id = parse_session_token(current_cookie, secret=get_session_secret(None)).profile_id
    enroll = client.post(
        "/ui/profiles/new",
        headers=ORIGIN,
        data={"profile_name": "Damian", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
        follow_redirects=False,
    )
    assert enroll.status_code == 303
    assert client.cookies.get(SESSION_COOKIE_NAME) == current_cookie
    page = client.get("/ui/switch-person")
    assert page.status_code == 200 and 'href="/ui/movies"' in page.text
    assert 'action="/ui/switch-person"' in page.text
    assert "login-profile-form" not in page.text
    failed = signin(client, "Damian", "wrong", route="/ui/switch-person")
    assert failed.status_code == 401 and client.cookies.get(SESSION_COOKIE_NAME) == current_cookie
    assert client.get("/ui/profiles/new").status_code == 200
    switched = signin(client, "Damian", route="/ui/switch-person", profile_id=admin_id)
    assert switched.json() == {"ok": True, "redirect_url": "/ui/movies"}
    reviewer_id = parse_session_token(
        client.cookies.get(SESSION_COOKIE_NAME), secret=get_session_secret(None)
    ).profile_id
    assert reviewer_id != admin_id
    assert db_session.get(Profile, reviewer_id).role == "reviewer"
    assert client.get("/ui/profiles/new").status_code == 403
    assert (
        client.post(
            "/api/profiles/active", headers=ORIGIN, json={"profile_id": admin_id}
        ).status_code
        == 403
    )
    client.cookies.set("vault_profile_id", str(admin_id))
    assert client.get("/api/profiles").json()["active_profile_id"] == reviewer_id
    client.cookies.clear()
    assert signin(client, "Cory").json()["ok"] is True
    assert client.get("/ui/movies").status_code == 200
    assert db_session.query(MoviePreference).count() == 0


@pytest.mark.parametrize("route", ["/login", "/ui/switch-person"])
@pytest.mark.parametrize("origin", [None, "http://evil.example"])
def test_origin_rejection_preserves_identity(client, monkeypatch, route, origin):
    owner(client, monkeypatch)
    before = client.cookies.get(SESSION_COOKIE_NAME)
    headers = {"Origin": origin} if origin else {}
    response = client.post(
        route,
        headers=headers,
        data={"access_key": "Cory", "passcode": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert client.cookies.get(SESSION_COOKIE_NAME) == before
    assert PASSWORD not in response.text


def test_personal_mode_rejects_legacy_shared_pair_and_old_unlock(client, monkeypatch):
    owner(client, monkeypatch)
    from api.routers.ui.login import _create_unlock_token

    monkeypatch.setattr(settings, "login_access_key", "old-shared")
    monkeypatch.setattr(settings, "login_passcode", "old-shared-password")
    client.cookies.clear()
    client.cookies.set("vault_unlock", _create_unlock_token(None))
    assert signin(client, "old-shared", "old-shared-password").status_code == 401
    assert signin(client, "ignored-hidden-override").status_code == 401
    assert signin(client, "Cory").json()["ok"] is True


def test_archive_restore_keeps_preferences_credentials_and_revokes_sessions(
    client, db_session, monkeypatch
):
    owner(client, monkeypatch)
    old_profile = db_session.query(Profile).filter_by(name="Cory").one()
    old_id = old_profile.id
    credential = db_session.query(ProfileCredential).filter_by(profile_id=old_id).one()
    old_hash = credential.passcode_hash
    movie = db_session.query(Movie).first()
    db_session.add(MoviePreference(profile_id=old_id, movie_id=movie.id, watchlist=True))
    old_completed_at = db_session.get(AppSetup, 1).completed_at
    db_session.commit()
    old_token = client.cookies.get(SESSION_COOKIE_NAME)
    batch = prepare_personal_fresh_start(db_session, expected_active_ids={old_id})
    assert get_profiles(db_session) == []
    assert db_session.query(Movie).count() == 33
    assert client.get("/api/profiles", follow_redirects=False).status_code == 401
    assert client.get("/api/assistant", follow_redirects=False).status_code == 401
    with pytest.raises(ValueError):
        prepare_personal_fresh_start(db_session, expected_active_ids=set())
    assert (
        matching_db_credential_profile_id(db_session, access_key="Cory", passcode=PASSWORD) is None
    )
    db_session.get(AppSetup, 1).local_setup_only = False  # TestClient is not loopback.
    db_session.commit()
    authorize_setup(client)
    assert (
        client.post(
            "/setup",
            headers=ORIGIN,
            data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
            follow_redirects=False,
        ).status_code
        == 303
    )
    replacement_id = db_session.query(Profile).filter(Profile.archived_at.is_(None)).one().id
    new_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert replacement_id != old_id
    replacement_batch = restore_profile_archive(
        db_session, batch_id=batch, expected_active_ids={replacement_id}
    )
    assert replacement_batch and db_session.get(ProfileArchiveBatch, replacement_batch)
    assert db_session.get(Profile, old_id).name == "Cory"
    assert db_session.get(AppSetup, 1).completed_at == old_completed_at
    assert (
        db_session.query(ProfileCredential).filter_by(profile_id=old_id).one().passcode_hash
        == old_hash
    )
    assert db_session.query(MoviePreference).filter_by(profile_id=old_id).one().watchlist
    for token in (old_token, new_token):
        client.cookies.clear()
        client.cookies.set(SESSION_COOKIE_NAME, token)
        assert client.get("/api/profiles", follow_redirects=False).status_code == 401
    client.cookies.clear()
    assert signin(client).json()["ok"] is True
    restore_profile_archive(db_session, batch_id=replacement_batch, expected_active_ids={old_id})
    assert db_session.get(Profile, replacement_id).archived_at is None
    assert db_session.get(Profile, old_id).archived_at is not None


def test_archive_guard_and_transaction_failure_leave_accounts_intact(
    client, db_session, monkeypatch
):
    owner(client, monkeypatch)
    profile = db_session.query(Profile).one()
    with pytest.raises(ValueError):
        prepare_personal_fresh_start(db_session, expected_active_ids={999})

    def fail():
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(RuntimeError):
        prepare_personal_fresh_start(db_session, expected_active_ids={profile.id})
    assert db_session.query(Profile).one().archived_at is None
    assert db_session.query(ProfileArchiveBatch).count() == 0
    assert db_session.get(AppSetup, 1).completed


def test_duplicate_credential_pair_is_rejected(client, db_session, monkeypatch):
    owner(client, monkeypatch)
    other = Profile(name="Ambiguous", role="reviewer")
    db_session.add(other)
    db_session.flush()
    db_session.add(
        build_profile_credential(profile_id=other.id, access_key="Cory", passcode=PASSWORD)
    )
    db_session.commit()
    client.cookies.clear()
    assert signin(client).status_code == 401


def test_fresh_start_setup_requires_direct_loopback(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    db_session.add(
        AppSetup(id=1, completed=False, personal_sign_in_only=True, local_setup_only=True)
    )
    db_session.commit()
    assert client.get("/setup", headers={"Host": "vault.example"}).status_code == 403
    response = client.post(
        "/setup",
        headers=ORIGIN,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
    )
    assert response.status_code == 403
    assert db_session.query(ProfileCredential).count() == 0


def test_concurrent_setup_creates_one_owner(tmp_path, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    engine = create_engine(
        f"sqlite:///{tmp_path / 'synthetic.db'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    nonce = "A" * 43
    with sessions() as db:
        issue_setup_grant(db, owner_name="Synthetic owner", code=SYNTHETIC_CODE)
        bind_setup_grant(db, code=SYNTHETIC_CODE, browser_nonce=nonce)
    barrier = Barrier(2)

    def create(name):
        with sessions() as db:
            barrier.wait()
            try:
                create_first_profile_setup(
                    db,
                    profile_name="Synthetic owner",
                    access_key="Synthetic owner",
                    passcode=PASSWORD,
                    passcode_confirm=PASSWORD,
                    bootstrap_browser_nonce=nonce,
                )
                return "created"
            except SetupError:
                return "already complete"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ["Synthetic A", "Synthetic B"]))
    assert sorted(results) == ["already complete", "created"]
    with sessions() as db:
        assert db.query(Profile).filter_by(role="admin").count() == 1
        assert db.query(ProfileCredential).count() == 1
    engine.dispose()


def test_legacy_personal_pair_signs_directly_and_shared_pair_stays_explicit(client, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    monkeypatch.setattr(settings, "login_access_key_user_a", "synthetic-admin")
    monkeypatch.setattr(settings, "login_passcode_user_a", PASSWORD)
    monkeypatch.setattr(settings, "login_access_key_user_b", "synthetic-reviewer")
    monkeypatch.setattr(settings, "login_passcode_user_b", PASSWORD)
    assert signin(client, "synthetic-reviewer").json() == {"ok": True, "redirect_url": "/ui/movies"}
    assert client.get("/ui/profiles/new").status_code == 403
    monkeypatch.setattr(settings, "login_access_key", "synthetic-shared")
    monkeypatch.setattr(settings, "login_passcode", PASSWORD)
    current = client.cookies.get(SESSION_COOKIE_NAME)
    assert signin(client, "synthetic-shared", route="/ui/switch-person").status_code == 403
    assert client.cookies.get(SESSION_COOKIE_NAME) == current
    client.cookies.clear()
    assert signin(client, "synthetic-shared").json() == {"unlocked": True}
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    assert "Shared access is verified" in client.get("/login?unlocked=1").text


def test_pre_archive_shared_unlock_does_not_return_after_restore(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    monkeypatch.setattr(settings, "login_access_key", "synthetic-shared")
    monkeypatch.setattr(settings, "login_passcode", PASSWORD)
    assert signin(client, "synthetic-shared").json() == {"unlocked": True}
    unlock = client.cookies.get("vault_unlock")
    ids = {p.id for p in get_profiles(db_session)}
    batch = prepare_personal_fresh_start(db_session, expected_active_ids=ids)
    restore_profile_archive(db_session, batch_id=batch, expected_active_ids=set())
    client.cookies.clear()
    client.cookies.set("vault_unlock", unlock)
    result = client.post(
        "/login", headers=JSON, data={"profile_id": min(ids)}, follow_redirects=False
    )
    assert result.status_code == 401
    assert signin(client, "synthetic-shared").json() == {"unlocked": True}
    assert client.post(
        "/login", headers=JSON, data={"profile_id": min(ids)}, follow_redirects=False
    ).json()["ok"]


def test_local_setup_guard_checks_client_and_hostname(client, db_session, monkeypatch):
    from starlette.requests import Request
    from fastapi import HTTPException
    from api.routers.ui.setup import _require_local_setup

    db_session.add(
        AppSetup(id=1, completed=False, personal_sign_in_only=True, local_setup_only=True)
    )
    db_session.commit()

    def request(host, client_host):
        return Request(
            {
                "type": "http",
                "method": "GET",
                "scheme": "http",
                "path": "/setup",
                "headers": [(b"host", host.encode())],
                "client": (client_host, 1),
                "server": ("127.0.0.1", 8000),
            }
        )

    _require_local_setup(request("127.0.0.1:8000", "127.0.0.1"), db_session)
    for host, address in [("vault.example", "127.0.0.1"), ("127.0.0.1:8000", "192.0.2.9")]:
        with pytest.raises(HTTPException):
            _require_local_setup(request(host, address), db_session)


def test_concurrent_duplicate_enrollment_returns_friendly_error(tmp_path):
    from api.services.setup import create_personal_reviewer

    engine = create_engine(
        f"sqlite:///{tmp_path / 'enrollment.db'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    barrier = Barrier(2)

    def enroll(_):
        with sessions() as db:
            barrier.wait()
            try:
                create_personal_reviewer(
                    db,
                    profile_name="Synthetic reviewer",
                    passcode=PASSWORD,
                    passcode_confirm=PASSWORD,
                )
                return "created"
            except SetupError as exc:
                assert "already in use" in str(exc)
                return "friendly error"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(enroll, [1, 2]))
    assert sorted(results) == ["created", "friendly error"]
    with sessions() as db:
        assert db.query(Profile).filter_by(role="reviewer").count() == 1
    engine.dispose()


def test_restore_revokes_pending_browser_claim_and_preserves_old_credentials(
    client, db_session, monkeypatch
):
    from api.services.setup_grants import SetupGrantError, require_bound_setup_grant

    owner(client, monkeypatch)
    old_id = db_session.query(Profile).one().id
    batch = prepare_personal_fresh_start(db_session, expected_active_ids={old_id})
    nonce = "R" * 43
    issue_setup_grant(db_session, owner_name="Synthetic replacement", code=SYNTHETIC_CODE)
    bind_setup_grant(db_session, code=SYNTHETIC_CODE, browser_nonce=nonce)
    restore_profile_archive(db_session, batch_id=batch, expected_active_ids=set())
    with pytest.raises(SetupGrantError):
        require_bound_setup_grant(db_session, browser_nonce=nonce)
    assert db_session.get(AppSetup, 1).completed
    assert (
        matching_db_credential_profile_id(db_session, access_key="Cory", passcode=PASSWORD)
        == old_id
    )


def test_restore_commit_failure_retains_replacement_account_and_pending_grant(
    client, db_session, monkeypatch
):
    from api.models.profile import SetupGrant

    owner(client, monkeypatch)
    old_id = db_session.query(Profile).one().id
    batch = prepare_personal_fresh_start(db_session, expected_active_ids={old_id})
    authorize_setup(client, owner_name="Synthetic replacement")
    nonce = client.cookies.get("vault_setup_browser")
    replacement = create_first_profile_setup(
        db_session,
        profile_name="Synthetic replacement",
        access_key="Synthetic replacement",
        passcode=PASSWORD,
        passcode_confirm=PASSWORD,
        bootstrap_browser_nonce=nonce,
    ).profile
    replacement_id = replacement.id

    def fail():
        raise RuntimeError("synthetic restore failure")

    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(RuntimeError):
        restore_profile_archive(db_session, batch_id=batch, expected_active_ids={replacement_id})
    assert db_session.get(Profile, old_id).archived_at is not None
    assert db_session.get(Profile, replacement_id).archived_at is None
    assert db_session.get(ProfileArchiveBatch, batch).restored_at is None
    assert db_session.query(ProfileArchiveBatch).count() == 1
    assert db_session.get(SetupGrant, 1).consumed_at is not None
    assert (
        matching_db_credential_profile_id(
            db_session, access_key="Synthetic replacement", passcode=PASSWORD
        )
        == replacement_id
    )
