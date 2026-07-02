import pytest

from api.models.movie import Movie
from api.models.vault_id import RetiredVaultId
from core.vault_ids import (
    LEGACY_RETIRED_VAULT_IDS,
    allocate_vault_id,
    next_vault_id,
    normalize_vault_id,
    retire_movie_vault_id,
    seed_legacy_retired_vault_ids,
)


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


def test_next_vault_id_skips_retired_deleted_top_id(db_session):
    movie = Movie(vault_id="V0034", title="Deleted Top")
    db_session.add(movie)
    db_session.flush()

    retire_movie_vault_id(
        db_session,
        movie,
        source="test_delete",
        reason="Deleted during test.",
    )
    db_session.delete(movie)
    db_session.commit()

    db_session.add(Movie(vault_id="V0033", title="Current Top"))
    db_session.commit()

    assert next_vault_id(db_session) == "V0035"


def test_seed_legacy_retired_ids_and_skip_them(db_session):
    seed_legacy_retired_vault_ids(db_session)
    db_session.commit()

    retired_ids = {row.vault_id for row in db_session.query(RetiredVaultId).all()}
    assert set(LEGACY_RETIRED_VAULT_IDS) <= retired_ids
    with pytest.raises(ValueError, match="V0087 is retired"):
        allocate_vault_id(db_session, "V0087")
