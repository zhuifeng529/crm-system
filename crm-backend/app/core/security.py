from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: dict[str, Any], expires_minutes: int | None = None) -> tuple[str, str, datetime]:
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)
    jti = uuid4().hex
    payload = {**subject, "exp": expire, "jti": jti}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expire


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
