from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.core.config import settings


@dataclass
class AuthContext:
    actor_id: str
    authenticated: bool


def is_protected_path(path: str) -> bool:
    return path.startswith("/api/v1")


def is_auth_enabled() -> bool:
    return bool((settings.AUTH_API_KEY or "").strip())


def extract_actor_id(request: Request) -> str:
    actor_id = request.headers.get("x-actor-id") or request.headers.get("x-user-id")
    return actor_id.strip() if actor_id and actor_id.strip() else "api-client"


def validate_api_key(request: Request) -> AuthContext:
    if not is_auth_enabled():
        return AuthContext(actor_id=extract_actor_id(request), authenticated=False)

    provided = request.headers.get("x-api-key") or ""
    if not secrets.compare_digest(provided, settings.AUTH_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    return AuthContext(actor_id=extract_actor_id(request), authenticated=True)
