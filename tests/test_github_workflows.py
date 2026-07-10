from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_security_workflow_runs_codeql_for_python_and_javascript() -> None:
    workflow = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")

    assert "github/codeql-action/init@v4" in workflow
    assert "github/codeql-action/analyze@v4" in workflow
    assert "languages: python,javascript-typescript" in workflow
    assert "security-events: write" in workflow
    assert "cron:" in workflow
