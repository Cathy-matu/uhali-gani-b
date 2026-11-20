import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


password_hasher = PasswordHasher()
SESSION_COOKIE = "hali_session"
SESSION_TTL = timedelta(hours=12)
JWT_ALGORITHM = "HS256"


def get_auth_secret() -> str:
    secret = os.getenv("AUTH_SECRET_KEY", "")
    if len(secret) < 32 or "replace_with_output" in secret:
        raise RuntimeError("Set AUTH_SECRET_KEY to a random secret of at least 32 characters.")
    return secret


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_session_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + SESSION_TTL},
        get_auth_secret(),
        algorithm=JWT_ALGORITHM,
    )


def read_session_user_id(token: str) -> str | None:
    try:
        payload = jwt.decode(token, get_auth_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
