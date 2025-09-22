"""Utility to write the FastAPI OpenAPI schema to openapi/openapi.json."""

import json
import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    output_dir = ROOT_DIR / "openapi"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "openapi.json"
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {output_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
