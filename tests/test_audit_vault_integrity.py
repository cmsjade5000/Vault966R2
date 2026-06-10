from scripts.audit_vault_integrity import _fingerprint


def test_fingerprint_is_stable_and_order_sensitive():
    records = [{"id": 1, "title": "Alien"}, {"id": 2, "title": "Aliens"}]

    assert _fingerprint(records) == _fingerprint(list(records))
    assert _fingerprint(records) != _fingerprint(list(reversed(records)))
