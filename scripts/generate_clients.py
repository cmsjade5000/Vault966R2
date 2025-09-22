"""Generate Python and TypeScript API clients from the frozen OpenAPI spec."""

import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT_DIR / "openapi" / "openapi.json"
PY_CONFIG = ROOT_DIR / "openapi-client-config.yml"


def run(cmd):
    process = subprocess.run(cmd, cwd=ROOT_DIR)
    if process.returncode != 0:
        raise SystemExit(process.returncode)


def generate_python_client(output_dir: pathlib.Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    run(
        [
            sys.executable,
            "-m",
            "openapi_python_client.cli",
            "generate",
            "--path",
            str(OPENAPI_PATH),
            "--config",
            str(PY_CONFIG),
            "--output-path",
            str(output_dir),
            "--overwrite",
        ]
    )


def generate_typescript_client(output_dir: pathlib.Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            "npx",
            "openapi-typescript",
            str(OPENAPI_PATH),
            "--output",
            str(output_dir / "index.d.ts"),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate API clients from OpenAPI spec")
    parser.add_argument("--skip-python", action="store_true")
    parser.add_argument("--skip-typescript", action="store_true")
    args = parser.parse_args()

    if not OPENAPI_PATH.exists():
        raise SystemExit("openapi/openapi.json not found. Run scripts/generate_openapi.py first.")

    if not args.skip_python:
        generate_python_client(ROOT_DIR / "client_py")
    if not args.skip_typescript:
        generate_typescript_client(ROOT_DIR / "client_ts")


if __name__ == "__main__":
    main()
