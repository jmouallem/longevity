import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

# pbkdf2_sha256 is broadly compatible across Python versions and remains secure
# for password hashing in this MVP.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def _build_fernet() -> Fernet:
    digest = hashlib.sha256(SECRET_KEY.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


fernet = _build_fernet()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    subject = payload.get("sub")
    if not subject:
        raise JWTError("Missing subject")
    return subject


def encrypt_api_key(api_key: str) -> str:
    return fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_api_key: str) -> str:
    try:
        return fernet.decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted key") from exc


def mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"
