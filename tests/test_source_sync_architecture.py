from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from api.services import source_sync, source_sync_contracts, source_sync_identity


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FACADE_SYMBOLS = {
    "SourceSyncError",
    "accept_all_source_differences",
    "analyze_first_import_snapshot",
    "apply_first_import_auto_create",
    "assign_source_row_match",
    "create_draft_snapshot",
    "create_movie_from_source_row",
    "decide_source_field",
    "defer_source_row_for_research",
    "dismiss_duplicate",
    "first_import_report",
    "get_source_review_queue",
    "latest_active_snapshot",
    "parse_directors",
    "partition_source_review_queue",
    "reconcile_snapshot",
    "snapshot_summary",
    "source_bulk_decision_counts",
    "source_new_addition_rows",
    "source_provenance_for_movie",
    "source_row_conflicts",
    "undo_source_field_decision",
}
CONSUMER_MODULES = (
    "api.services.source_sync",
    "api.services.trusted_movies",
    "api.services.movies_curated",
    "api.routers.ui.source_sync",
    "api.routers.ui.first_import",
    "api.routers.ui.review",
    "api.routers.ui.grid",
    "api.routers.ui.detail",
)


def test_source_sync_facade_exports_production_contract() -> None:
    assert PUBLIC_FACADE_SYMBOLS <= set(source_sync.__all__)


def test_source_sync_facade_reuses_extracted_contracts_and_identity() -> None:
    assert source_sync.SourceSyncError is source_sync_contracts.SourceSyncError
    assert source_sync.ParsedSourceRow is source_sync_contracts.ParsedSourceRow
    assert source_sync.SourceReviewItem is source_sync_contracts.SourceReviewItem
    assert source_sync.parse_directors is source_sync_identity.parse_directors
    assert source_sync.build_research_links is source_sync_identity.build_research_links


def test_source_sync_consumers_import_without_order_cycles() -> None:
    for modules in (CONSUMER_MODULES, tuple(reversed(CONSUMER_MODULES))):
        code = "; ".join(f"import {module}" for module in modules)
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_source_sync_implementation_modules_do_not_import_facade() -> None:
    implementation_paths = sorted((ROOT / "api" / "services").glob("source_sync_*.py"))
    assert implementation_paths
    for path in implementation_paths:
        source = path.read_text(encoding="utf-8")
        assert "from api.services.source_sync import" not in source
        assert "from api.services import source_sync" not in source
