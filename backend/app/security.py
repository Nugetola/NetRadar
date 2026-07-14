"""Small dependency-free HS256 bearer-token and service-key authentication."""
import base64
import hashlib
import hmac
import json
import time
from fastapi import Header, HTTPException, status
from .config import get_settings


def _part(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def issue_token(subject: str, role: str = "ADMIN", ttl_seconds: int = 28800) -> str:
    header = _part(b'{"alg":"HS256","typ":"JWT"}')
    payload = _part(json.dumps({"sub": subject, "role": role, "exp": int(time.time()) + ttl_seconds}, separators=(",", ":")).encode())
    signature = _part(hmac.new(get_settings().jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def verify_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        expected = _part(hmac.new(get_settings().jwt_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected): raise ValueError("invalid signature")
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) < time.time(): raise ValueError("expired")
        return data
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired access token") from exc


async def require_access(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    if not settings.auth_required:
        return {"sub": "development", "role": "ADMIN"}
    if settings.service_api_key and x_api_key and hmac.compare_digest(x_api_key, settings.service_api_key):
        return {"sub": "service", "role": "SERVICE"}
    if authorization and authorization.startswith("Bearer "):
        return verify_token(authorization[7:])
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token or API key required")
