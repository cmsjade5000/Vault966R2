"""Freeze the main app's model shape; importing the app never opens a database."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.main import app  # noqa: F401 - register lazily imported router models
from api.db import Base


def main() -> None:
    contract = {
        "format": 1,
        "tables": {
            table.name: sorted(column.name for column in table.columns)
            for table in Base.metadata.sorted_tables
        },
        "movie_unique_indexes": {
            index.name: [column.name for column in index.columns]
            for index in Base.metadata.tables["movies"].indexes
            if index.unique
        },
    }
    (ROOT / "release-schema.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print(f"Wrote release contract for {len(contract['tables'])} tables; no database opened.")


if __name__ == "__main__":
    main()
