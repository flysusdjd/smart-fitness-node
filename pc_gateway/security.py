from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from . import config


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=iterations,
        salt=base64.b64encode(salt).decode("ascii"),
        digest=base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
    if algorithm != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_b64.encode("ascii"))
    expected = base64.b64decode(digest_b64.encode("ascii"))
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    return hmac.compare_digest(candidate, expected)


def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def token_expiry() -> datetime:
    return _now() + timedelta(hours=config.TOKEN_TTL_HOURS)
