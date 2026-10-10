"""Settings regressions use synthetic environment values only."""

from io import StringIO
import os

from dotenv import dotenv_values, load_dotenv

from api.config import Settings


def test_empty_dotenv_values_and_comments():
    values = dotenv_values(stream=StringIO('EMPTY= # comment\nQUOTED=""\n'))
    assert values == {"EMPTY": "", "QUOTED": ""}


def test_environment_precedence_and_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_DEPENDENCY_TEST_BASE", "environment")
    monkeypatch.delenv("VAULT_DEPENDENCY_TEST_RESULT", raising=False)
    load_dotenv(
        stream=StringIO(
            "VAULT_DEPENDENCY_TEST_BASE=file\n"
            "VAULT_DEPENDENCY_TEST_RESULT=${VAULT_DEPENDENCY_TEST_BASE}/suffix\n"
        ),
        override=False,
    )
    try:
        assert os.environ["VAULT_DEPENDENCY_TEST_RESULT"] == "environment/suffix"
    finally:
        monkeypatch.delenv("VAULT_DEPENDENCY_TEST_RESULT", raising=False)
    env_file = tmp_path / "synthetic.env"
    env_file.write_text("ADMIN_TOKEN= # intentionally empty\n")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert Settings(_env_file=env_file).admin_token == ""
    monkeypatch.setenv("ADMIN_TOKEN", "synthetic-environment-token")
    assert Settings(_env_file=env_file).admin_token == "synthetic-environment-token"
