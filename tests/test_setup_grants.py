"""Synthetic capabilities only. Never generates or submits real credentials."""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.db import Base
from api.main import app
from api.models.profile import AppSetup, Profile, ProfileCredential, SetupGrant
from api.services.setup import create_first_profile_setup
from api.services.setup_grants import (
    SETUP_BROWSER_COOKIE,
    SetupGrantError,
    issue_setup_grant,
    bind_setup_grant,
    require_bound_setup_grant,
)
from tests.setup_support import local_browser, authorize_setup, SYNTHETIC_CODE, LOCAL_ORIGIN
from tests.test_setup import _clear_legacy_credentials

PASSWORD = "synthetic-grant-test-password-only"
NONCE_A = "A" * 43
NONCE_B = "B" * 43


@pytest.fixture
def client(client):
    with local_browser() as local:
        yield local


def test_direct_owner_post_cannot_claim_even_from_loopback(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    response = client.post(
        "/setup",
        headers=LOCAL_ORIGIN,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
    )
    assert response.status_code == 403
    assert db_session.query(ProfileCredential).count() == 0
    assert db_session.query(Profile).count() == 0
    issue_setup_grant(db_session, owner_name="Cory", code=SYNTHETIC_CODE)
    response = client.post(
        "/setup",
        headers=LOCAL_ORIGIN,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
    )
    assert response.status_code == 403
    assert db_session.query(ProfileCredential).count() == 0
    assert PASSWORD not in response.text


def test_claim_is_single_use_browser_bound_and_consumed_atomically(
    client, db_session, monkeypatch, caplog
):
    _clear_legacy_credentials(monkeypatch)
    authorize_setup(client)
    cookie = client.cookies.get(SETUP_BROWSER_COOKIE)
    grant = db_session.get(SetupGrant, 1)
    assert grant.code_hash != SYNTHETIC_CODE and grant.browser_hash != cookie
    assert len(grant.browser_hash) == 64
    assert grant.code_salt and grant.bound_at and grant.consumed_at is None
    page = client.get("/setup")
    assert page.status_code == 200 and 'value="Cory"' in page.text
    assert page.headers["cache-control"] == "no-store"
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 45678)) as other:
        assert other.get("/setup", follow_redirects=False).headers["location"] == "/setup/claim"
        other.get("/setup/claim")
        replay = other.post(
            "/setup/claim", headers=LOCAL_ORIGIN, data={"setup_code": SYNTHETIC_CODE}
        )
        assert replay.status_code == 403
        assert SYNTHETIC_CODE not in replay.text
        assert (
            other.post(
                "/setup",
                headers=LOCAL_ORIGIN,
                data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
            ).status_code
            == 403
        )
    assert client.get("/setup/claim", follow_redirects=False).headers["location"] == "/setup"
    wrong_name = client.post(
        "/setup",
        headers=LOCAL_ORIGIN,
        data={"profile_name": "Attacker", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
    )
    assert wrong_name.status_code == 400
    db_session.expire_all()
    assert db_session.get(SetupGrant, 1).consumed_at is None
    mismatch = client.post(
        "/setup",
        headers=LOCAL_ORIGIN,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": "different"},
    )
    assert mismatch.status_code == 400
    db_session.expire_all()
    assert db_session.get(SetupGrant, 1).consumed_at is None
    completed = client.post(
        "/setup",
        headers=LOCAL_ORIGIN,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
        follow_redirects=False,
    )
    assert completed.status_code == 303
    assert completed.headers["location"] == "/ui/movies"
    db_session.expire_all()
    assert db_session.get(SetupGrant, 1).consumed_at is not None
    assert client.cookies.get(SETUP_BROWSER_COOKIE) is None
    with pytest.raises(SetupGrantError):
        require_bound_setup_grant(db_session, browser_nonce=cookie)
    assert (
        SYNTHETIC_CODE not in caplog.text
        and PASSWORD not in caplog.text
        and cookie not in caplog.text
    )


def test_claim_wrong_expired_reissued_or_unbound_grants_fail_closed(
    client, db_session, monkeypatch
):
    _clear_legacy_credentials(monkeypatch)
    issue_setup_grant(db_session, owner_name="Cory", code=SYNTHETIC_CODE, now=1000)
    with pytest.raises(SetupGrantError):
        bind_setup_grant(db_session, code=SYNTHETIC_CODE, browser_nonce=NONCE_A, now=1600)
    issue_setup_grant(db_session, owner_name="Cory", code=SYNTHETIC_CODE)
    client.get("/setup/claim")
    assert (
        client.post(
            "/setup/claim", headers=LOCAL_ORIGIN, data={"setup_code": "wrong-synthetic-code-only"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/setup/claim",
            headers={"Origin": "http://evil.example"},
            data={"setup_code": SYNTHETIC_CODE},
        ).status_code
        == 403
    )
    assert client.post("/setup/claim", data={"setup_code": SYNTHETIC_CODE}).status_code == 403
    assert (
        client.post(
            "/setup/claim",
            headers=LOCAL_ORIGIN,
            data={"setup_code": SYNTHETIC_CODE},
            follow_redirects=False,
        ).status_code
        == 303
    )
    nonce = client.cookies.get(SETUP_BROWSER_COOKIE)
    issue_setup_grant(db_session, owner_name="Cory", code="replacement-synthetic-setup-code-only")
    with pytest.raises(SetupGrantError):
        require_bound_setup_grant(db_session, browser_nonce=nonce)
    with pytest.raises(SetupGrantError):
        bind_setup_grant(db_session, code=SYNTHETIC_CODE, browser_nonce=NONCE_B)
    with pytest.raises(SetupGrantError):
        bind_setup_grant(
            db_session, code="replacement-synthetic-setup-code-only", browser_nonce=None
        )
    bind_setup_grant(
        db_session, code="replacement-synthetic-setup-code-only", browser_nonce=NONCE_B
    )
    with pytest.raises(SetupGrantError):
        require_bound_setup_grant(db_session, browser_nonce=NONCE_B, now=int(time.time()) + 601)


def test_claim_nonce_cookie_private_and_request_scope(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    response = client.get("/setup/claim")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/setup" in cookie
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "same-origin"
    nonce = client.cookies.get(SETUP_BROWSER_COOKIE)
    assert nonce not in response.text
    with TestClient(app, base_url="http://127.0.0.1", client=("192.0.2.10", 12345)) as remote:
        assert remote.get("/setup/claim").status_code == 403
        assert (
            remote.post(
                "/setup/claim", headers=LOCAL_ORIGIN, data={"setup_code": SYNTHETIC_CODE}
            ).status_code
            == 403
        )
    assert client.get("/setup/claim", headers={"Host": "vault.example"}).status_code == 403


def test_private_form_policy_survives_claim_owner_and_reviewer_enrollment(
    client, db_session, monkeypatch
):
    _clear_legacy_credentials(monkeypatch)
    issue_setup_grant(db_session, owner_name="Cory", code=SYNTHETIC_CODE)
    claim_page = client.get("/setup/claim")
    claim = client.post(
        "/setup/claim",
        headers=LOCAL_ORIGIN,
        data={"setup_code": SYNTHETIC_CODE},
        follow_redirects=False,
    )
    assert claim.status_code == 303
    owner_page = client.get("/setup")
    owner = client.post(
        "/setup",
        headers=LOCAL_ORIGIN,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
        follow_redirects=False,
    )
    assert owner.status_code == 303
    reviewer_page = client.get("/ui/profiles/new")
    assert reviewer_page.status_code == 200
    for response in (claim_page, claim, owner_page, reviewer_page):
        assert response.headers["referrer-policy"] == "same-origin"
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "origin", [None, "null", "http://evil.example", "http://localhost", "http://127.0.0.1:8000"]
)
def test_origin_rejection_does_not_bind_or_consume_valid_grant(
    client, db_session, monkeypatch, origin
):
    _clear_legacy_credentials(monkeypatch)
    issue_setup_grant(db_session, owner_name="Cory", code=SYNTHETIC_CODE)
    client.get("/setup/claim")
    headers = {"Origin": origin} if origin is not None else {}
    rejected_claim = client.post(
        "/setup/claim", headers=headers, data={"setup_code": SYNTHETIC_CODE}
    )
    assert rejected_claim.status_code == 403
    grant = db_session.get(SetupGrant, 1)
    db_session.refresh(grant)
    assert grant.bound_at is None and grant.consumed_at is None
    assert db_session.query(Profile).count() == 0

    accepted_claim = client.post(
        "/setup/claim",
        headers=LOCAL_ORIGIN,
        data={"setup_code": SYNTHETIC_CODE},
        follow_redirects=False,
    )
    assert accepted_claim.status_code == 303
    rejected_owner = client.post(
        "/setup",
        headers=headers,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
    )
    assert rejected_owner.status_code == 403
    db_session.refresh(grant)
    assert grant.bound_at is not None and grant.consumed_at is None
    assert db_session.query(Profile).count() == 0
    assert db_session.query(ProfileCredential).count() == 0


def test_grant_claim_race_binds_one_browser(tmp_path, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    engine = create_engine(
        f"sqlite:///{tmp_path/'grants.db'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        issue_setup_grant(db, owner_name="Cory", code=SYNTHETIC_CODE)
    barrier = Barrier(2)

    def claim(nonce):
        with sessions() as db:
            barrier.wait()
            try:
                bind_setup_grant(db, code=SYNTHETIC_CODE, browser_nonce=nonce)
                return "bound"
            except SetupGrantError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [NONCE_A, NONCE_B]))
    assert sorted(results) == ["bound", "rejected"]
    with sessions() as db:
        expected = db.get(SetupGrant, 1).browser_hash
        assert expected in {hashlib.sha256(n.encode()).hexdigest() for n in [NONCE_A, NONCE_B]}
    engine.dispose()


def test_owner_failure_rolls_back_grant_consumption(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    authorize_setup(client)
    nonce = client.cookies.get(SETUP_BROWSER_COOKIE)

    def fail():
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(RuntimeError):
        create_first_profile_setup(
            db_session,
            profile_name="Cory",
            access_key="Cory",
            passcode=PASSWORD,
            passcode_confirm=PASSWORD,
            bootstrap_browser_nonce=nonce,
        )
    assert db_session.get(SetupGrant, 1).consumed_at is None
    assert db_session.query(ProfileCredential).count() == 0
    assert not db_session.get(AppSetup, 1).completed


@pytest.mark.parametrize(
    "header", ["Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto"]
)
def test_forwarded_requests_cannot_claim_or_submit_setup(client, db_session, monkeypatch, header):
    _clear_legacy_credentials(monkeypatch)
    issue_setup_grant(db_session, owner_name="Cory", code=SYNTHETIC_CODE)
    assert client.get("/setup/claim", headers={header: "127.0.0.1"}).status_code == 403
    client.get("/setup/claim")
    assert (
        client.post(
            "/setup/claim",
            headers={**LOCAL_ORIGIN, header: "127.0.0.1"},
            data={"setup_code": SYNTHETIC_CODE},
        ).status_code
        == 403
    )
    assert db_session.get(SetupGrant, 1).browser_hash is None
    assert (
        client.post(
            "/setup/claim",
            headers=LOCAL_ORIGIN,
            data={"setup_code": SYNTHETIC_CODE},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post(
            "/setup",
            headers={**LOCAL_ORIGIN, header: "127.0.0.1"},
            data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
        ).status_code
        == 403
    )
    assert db_session.query(ProfileCredential).count() == 0
    assert db_session.get(SetupGrant, 1).consumed_at is None


def test_claim_throttle_and_invalid_input_never_echo_code(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    issue_setup_grant(db_session, owner_name="Cory", code=SYNTHETIC_CODE)
    client.get("/setup/claim")
    oversize = "synthetic-oversize-code-only-" * 6
    response = client.post("/setup/claim", headers=LOCAL_ORIGIN, data={"setup_code": oversize})
    assert response.status_code == 422 and oversize not in response.text
    for _ in range(5):
        assert (
            client.post(
                "/setup/claim",
                headers=LOCAL_ORIGIN,
                data={"setup_code": "synthetic-wrong-claim-only"},
            ).status_code
            == 403
        )
    response = client.post(
        "/setup/claim", headers=LOCAL_ORIGIN, data={"setup_code": SYNTHETIC_CODE}
    )
    assert response.status_code == 429 and SYNTHETIC_CODE not in response.text
    assert db_session.get(SetupGrant, 1).browser_hash is None


def test_completed_setup_cannot_be_reopened_by_issue(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    authorize_setup(client)
    assert (
        client.post(
            "/setup",
            headers=LOCAL_ORIGIN,
            data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
            follow_redirects=False,
        ).status_code
        == 303
    )
    generation = db_session.get(SetupGrant, 1).generation
    with pytest.raises(SetupGrantError, match="complete"):
        issue_setup_grant(db_session, owner_name="Synthetic other", code=SYNTHETIC_CODE)
    assert db_session.get(SetupGrant, 1).generation == generation
    assert db_session.query(Profile).count() == 1


def test_secure_cookie_on_https_and_expired_bound_owner_post(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    with TestClient(app, base_url="https://127.0.0.1", client=("127.0.0.1", 45678)) as browser:
        assert "secure" in browser.get("/setup/claim").headers["set-cookie"].lower()
    authorize_setup(client)
    grant = db_session.get(SetupGrant, 1)
    grant.expires_at = int(time.time()) - 1
    db_session.commit()
    response = client.post(
        "/setup",
        headers=LOCAL_ORIGIN,
        data={"profile_name": "Cory", "passcode": PASSWORD, "passcode_confirm": PASSWORD},
    )
    assert response.status_code == 403 and PASSWORD not in response.text
    assert grant.consumed_at is None and db_session.query(ProfileCredential).count() == 0
