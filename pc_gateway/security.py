"""认证安全工具：负责密码哈希校验、访问令牌生成和过期时间计算。"""

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


# 使用 PBKDF2-HMAC-SHA256 加盐保存密码，不存明文。
def hash_password(password: str, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=iterations,
        salt=base64.b64encode(salt).decode("ascii"),
        digest=base64.b64encode(digest).decode("ascii"),
    )


# 用常量时间比较校验密码，减少时序攻击风险。
def verify_password(password: str, stored_hash: str) -> bool:
    algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
    if algorithm != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_b64.encode("ascii"))
    expected = base64.b64decode(digest_b64.encode("ascii"))
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    return hmac.compare_digest(candidate, expected)


# 生成 URL 安全的随机访问令牌。
def generate_access_token() -> str:
    return secrets.token_urlsafe(32)


def token_expiry() -> datetime:
    return _now() + timedelta(hours=config.TOKEN_TTL_HOURS)
