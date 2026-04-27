"""Dual-mode auth: gateway headers (Vexa deployment) or standalone API keys."""

import hmac
import os
import logging
from fastapi import HTTPException, Request, Depends
from fastapi.security import APIKeyHeader

logger = logging.getLogger("meeting_api.auth")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
INTERNAL_API_SECRET = os.environ.get("INTERNAL_API_SECRET", "")


class UserProxy:
    """Minimal user-like object for backward compat with existing endpoint code."""
    def __init__(self, user_id, max_concurrent, scopes):
        self.id = user_id
        self.max_concurrent_bots = max_concurrent
        self.data = {}
        self.email = f"user-{user_id}"
        self.scopes = scopes


async def validate_request(request: Request) -> dict:
    """Returns {user_id, scopes, max_concurrent} or raises 401/403."""
    # 1. Gateway mode: trusted headers (set by api-gateway after token validation)
    #
    # Hardening: require X-Internal-Secret to match INTERNAL_API_SECRET. Without
    # this check any on-network peer can impersonate any user by setting
    # X-User-ID. Upstream relies on the gateway stripping caller-supplied
    # X-User-* headers, but that doesn't defend against on-network peers
    # (transcription, bot, anything else on the docker network).
    user_id = request.headers.get("X-User-ID")
    if user_id:
        if INTERNAL_API_SECRET:
            provided = request.headers.get("X-Internal-Secret", "")
            if not hmac.compare_digest(provided, INTERNAL_API_SECRET):
                raise HTTPException(
                    status_code=403,
                    detail="X-User-ID present but X-Internal-Secret missing or invalid",
                )
        limits_raw = request.headers.get("X-User-Limits", "1")
        try:
            max_concurrent = int(limits_raw)
        except ValueError:
            import json
            try:
                limits = json.loads(limits_raw)
                max_concurrent = int(limits.get("max_concurrent_bots", limits.get("max_concurrent", 1)))
            except (json.JSONDecodeError, TypeError):
                max_concurrent = 1
        return {
            "user_id": int(user_id),
            "scopes": request.headers.get("X-User-Scopes", "").split(","),
            "max_concurrent": max_concurrent,
        }

    # 2. Standalone mode: API key check
    api_key = request.headers.get("X-API-Key", "")
    if API_KEYS:
        if not api_key or api_key not in API_KEYS:
            raise HTTPException(status_code=403, detail="Invalid or missing API key")
        return {"user_id": 0, "scopes": ["*"], "max_concurrent": 999}

    # 3. No auth configured (dev mode)
    if not API_KEYS:
        return {"user_id": 0, "scopes": ["*"], "max_concurrent": 999}

    raise HTTPException(status_code=401, detail="Authentication required")


async def get_user_and_token(request: Request) -> tuple:
    """Backward-compatible wrapper: returns (api_key, UserProxy) for existing code."""
    info = await validate_request(request)
    api_key = request.headers.get("X-API-Key", "")
    user = UserProxy(info["user_id"], info["max_concurrent"], info["scopes"])
    return (api_key, user)
