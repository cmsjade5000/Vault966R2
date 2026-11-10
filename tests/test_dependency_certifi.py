"""Keep the server and regenerated client on the corrected TLS trust bundle."""

from importlib.metadata import version
from pathlib import Path
import ssl
import tomllib

import certifi
import httpx
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from scripts.generate_clients import generate_python_client

ROOT = Path(__file__).resolve().parents[1]


def test_certifi_bundle_removes_compromised_root():
    assert Version(version("certifi")) >= Version("2026.10.19")
    context = ssl.create_default_context(cafile=certifi.where())
    common_names = {
        value
        for certificate in context.get_ca_certs()
        for attributes in certificate["subject"]
        for key, value in attributes
        if key == "commonName"
    }
    assert "emSign ECC Root CA - G3" not in common_names
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


def test_httpx_default_trust_uses_certifi(monkeypatch):
    for name in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
        monkeypatch.delenv(name, raising=False)
    # Host proxy configuration must not affect this offline trust-store probe.
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    create_default_context = ssl.create_default_context
    cafiles = []

    def record_context(*args, **kwargs):
        cafiles.append(kwargs.get("cafile"))
        return create_default_context(*args, **kwargs)

    monkeypatch.setattr(ssl, "create_default_context", record_context)
    with httpx.Client():
        pass
    assert cafiles
    assert set(cafiles) == {certifi.where()}


def test_regenerated_client_preserves_certifi_minimum(tmp_path):
    output_dir = tmp_path / "client_py"
    generate_python_client(output_dir)
    generated = (output_dir / "pyproject.toml").read_text()
    assert generated == (ROOT / "client_py" / "pyproject.toml").read_text()
    dependencies = tomllib.loads(generated)["tool"]["poetry"]["dependencies"]
    specifier = SpecifierSet(dependencies["certifi"])
    assert "2026.7.22" not in specifier
    assert "2026.10.18" not in specifier
    assert "2026.10.19" in specifier
