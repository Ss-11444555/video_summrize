"""Authentication, authorization, and password utilities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict

from fastapi import HTTPException, status

from backend.app.core.config import settings


TOKEN_SEPARATOR = "."


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return "pbkdf2_sha256${}${}".format(salt, derived_key.hex())


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash.startswith("pbkdf2_sha256$"):
        return secrets.compare_digest(password, password_hash)

    _, salt, stored_hash = password_hash.split("$", 2)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return hmac.compare_digest(derived_key.hex(), stored_hash)


def _encode_part(value: Dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_part(value: str) -> Dict[str, Any]:
    padding = "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(value + padding)
    return json.loads(raw.decode("utf-8"))


def create_access_token(payload: Dict[str, Any], expires_minutes: int = 120) -> str:
    token_payload = dict(payload)
    token_payload["exp"] = int(time.time()) + (expires_minutes * 60)
    encoded_payload = _encode_part(token_payload)
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return TOKEN_SEPARATOR.join([encoded_payload, signature])


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        encoded_payload, signature = token.split(TOKEN_SEPARATOR, 1)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token format.",
        ) from error

    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token signature.",
        )

    payload = _decode_part(encoded_payload)
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
        )

    return payload
