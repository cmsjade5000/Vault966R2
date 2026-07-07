from __future__ import annotations

import hashlib
import hmac
import secrets

from api.models.profile import ProfileCredential

KDF_NAME = "pbkdf2_sha256"
KDF_ITERATIONS = 200_000
SALT_BYTES = 16


def _hash_secret(secret: str, *, salt_hex: str, iterations: int = KDF_ITERATIONS) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    )
    return digest.hex()


def new_secret_hash(secret: str) -> tuple[str, str]:
    salt = secrets.token_hex(SALT_BYTES)
    return salt, _hash_secret(secret, salt_hex=salt)


def build_profile_credential(
    *,
    profile_id: int,
    access_key: str,
    passcode: str,
) -> ProfileCredential:
    access_key_salt, access_key_hash = new_secret_hash(access_key)
    passcode_salt, passcode_hash = new_secret_hash(passcode)
    return ProfileCredential(
        profile_id=profile_id,
        access_key_salt=access_key_salt,
        access_key_hash=access_key_hash,
        passcode_salt=passcode_salt,
        passcode_hash=passcode_hash,
        kdf_name=KDF_NAME,
        kdf_iterations=KDF_ITERATIONS,
    )


def credential_matches(
    credential: ProfileCredential,
    *,
    access_key: str,
    passcode: str,
) -> bool:
    if credential.kdf_name != KDF_NAME:
        return False
    access_key_hash = _hash_secret(
        access_key,
        salt_hex=credential.access_key_salt,
        iterations=credential.kdf_iterations,
    )
    passcode_hash = _hash_secret(
        passcode,
        salt_hex=credential.passcode_salt,
        iterations=credential.kdf_iterations,
    )
    return hmac.compare_digest(
        access_key_hash,
        credential.access_key_hash,
    ) and hmac.compare_digest(passcode_hash, credential.passcode_hash)
