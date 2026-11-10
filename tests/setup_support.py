"""Synthetic-only setup authorization helpers; never runs against a live DB."""

from fastapi.testclient import TestClient
from contextlib import contextmanager

from api.db import get_db
from api.main import app
from api.services.setup_grants import issue_setup_grant

SYNTHETIC_CODE = "synthetic-one-time-setup-code-only"
LOCAL_ORIGIN = {"Origin": "http://127.0.0.1"}


@contextmanager
def local_browser():
    # Reuse the outer fixture's isolated DB dependency; only client/host differ.
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345)) as local:
        yield local


def authorize_setup(client, *, owner_name="Cory", code=SYNTHETIC_CODE):
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        issue_setup_grant(db, owner_name=owner_name, code=code)
    finally:
        generator.close()
    landing = client.get("/setup/claim", follow_redirects=False)
    assert landing.status_code == 200
    claim = client.post(
        "/setup/claim", headers=LOCAL_ORIGIN, data={"setup_code": code}, follow_redirects=False
    )
    assert claim.status_code == 303
    assert code not in claim.text
