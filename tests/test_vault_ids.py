from api.models.movie import Movie
from core.vault_ids import next_vault_id, normalize_vault_id


def test_normalize_vault_id():
    assert normalize_vault_id("v42") == "V0042"
    assert normalize_vault_id("V0981") == "V0981"
    assert normalize_vault_id("42") is None


def test_next_vault_id_uses_highest_existing(db_session):
    db_session.add_all(
        [
            Movie(vault_id="V0001", title="One"),
            Movie(vault_id="V0980", title="Last Legacy"),
        ]
    )
    db_session.flush()

    assert next_vault_id(db_session) == "V0981"
