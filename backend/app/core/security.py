"""Single-owner access control and bounded API work for one server process."""

import secrets
import time
from collections import deque
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings

COOKIE = "repolens_session"
router = APIRouter()
_sessions: dict[str, float] = {}
_requests: dict[str, deque[float]] = {}
_active_operations = 0


def _allowed(bucket: str, limit: int) -> bool:
    now = time.monotonic()
    events = _requests.setdefault(bucket, deque())
    while events and events[0] <= now - 60:
        events.popleft()
    if len(events) >= limit:
        return False
    events.append(now)
    return True


def _authenticated(request: Request) -> bool:
    key = get_settings().access_key
    if len(key) < 32:
        return False  # Fail closed even when startup has not run (ASGI tests).
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer ") and secrets.compare_digest(authorization[7:].encode(), key.encode()):
        return True
    token = request.cookies.get(COOKIE, "")
    expires = _sessions.get(token, 0)
    if expires <= time.time():
        _sessions.pop(token, None)
        return False
    return True


def _same_origin(request: Request) -> bool:
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True  # Non-browser API clients can use the owner bearer key.
    host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    origin_host = urlsplit(origin).netloc.lower()
    if origin_host == host.lower():
        return True
    if origin_host.endswith(".trycloudflare.com") or origin_host.startswith("localhost") or origin_host.startswith("127.0.0.1"):
        return True
    return False


class LoginRequest(BaseModel):
    access_key: str = Field(min_length=1, max_length=512)


@router.get("/status")
async def auth_status(request: Request):
    return {"authenticated": _authenticated(request), "configured": len(get_settings().access_key) >= 32}


@router.post("/login")
async def login(payload: LoginRequest, request: Request):
    if not _same_origin(request):
        raise HTTPException(403, "Cross-site sign-in is not allowed")
    if not _allowed("login", 10):
        raise HTTPException(429, "Too many sign-in attempts. Try again in a minute", headers={"Retry-After": "60"})
    key = get_settings().access_key
    if len(key) < 32:
        raise HTTPException(503, "Owner access is not configured")
    if not secrets.compare_digest(payload.access_key.encode(), key.encode()):
        raise HTTPException(401, "Invalid access key")
    now = time.time()
    for token, expires in list(_sessions.items()):
        if expires <= now:
            del _sessions[token]
    if len(_sessions) >= 128:
        del _sessions[min(_sessions, key=_sessions.get)]
    token = secrets.token_urlsafe(32)
    lifetime = get_settings().session_hours * 3600
    _sessions[token] = now + lifetime
    response = JSONResponse({"authenticated": True})
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(COOKIE, token, max_age=lifetime, httponly=True, secure=secure, samesite="strict", path="/api")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/logout")
async def logout(request: Request):
    if not _same_origin(request):
        raise HTTPException(403, "Cross-site sign-out is not allowed")
    _sessions.pop(request.cookies.get(COOKIE, ""), None)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(COOKIE, path="/api", httponly=True, samesite="strict")
    return response


class SecurityMiddleware:
    """Authenticate before parsing uploads; reject oversized or excessive work."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        global _active_operations
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        path = scope["path"]
        public = path in {"/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/logout"}
        if not public and not _authenticated(request):
            return await JSONResponse({"error": "Sign in to access RepoLens"}, status_code=401)(scope, receive, send)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not _same_origin(request):
            return await JSONResponse({"error": "Cross-site requests are not allowed"}, status_code=403)(scope, receive, send)
        settings = get_settings()
        max_bytes = settings.max_upload_bytes + 1024 * 1024 if path.endswith("/upload") else 1024 * 1024
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return await JSONResponse({"error": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
        if content_length < 0 or content_length > max_bytes:
            return await JSONResponse({"error": "Request body exceeds the configured limit"}, status_code=413)(scope, receive, send)
        heavy = request.method == "POST" and (path in {"/api/chat", "/api/evaluation/run"} or path.startswith("/api/repositories/") or path.startswith("/api/retrieval/"))
        if not public and not _allowed("api", settings.api_requests_per_minute):
            return await JSONResponse({"error": "API request limit reached"}, status_code=429, headers={"Retry-After": "60"})(scope, receive, send)
        if heavy and (not _allowed("work", settings.expensive_requests_per_minute) or _active_operations >= settings.max_active_operations):
            return await JSONResponse({"error": "Server is busy. Try again in a minute"}, status_code=429, headers={"Retry-After": "60"})(scope, receive, send)
        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_bytes:
                    raise HTTPException(413, "Request body exceeds the configured limit")
            return message

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
            await send(message)

        if heavy:
            _active_operations += 1
        try:
            await self.app(scope, limited_receive, secured_send)
        finally:
            if heavy:
                _active_operations -= 1
