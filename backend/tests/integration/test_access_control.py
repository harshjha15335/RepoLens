"""Exercise the actual ASGI authentication and request bounds before API work."""

import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI, Request

from app.core import security
from app.core.config import Settings

KEY = "test-owner-access-key-with-32-characters"


@pytest.fixture
def secured_app(monkeypatch):
    settings = Settings(_env_file=None, access_key=KEY, max_upload_mb=1,
                        max_active_operations=2, api_requests_per_minute=10)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "_sessions", {})
    monkeypatch.setattr(security, "_requests", {})
    monkeypatch.setattr(security, "_active_operations", 0)
    app = FastAPI()
    app.add_middleware(security.SecurityMiddleware)
    app.include_router(security.router, prefix="/api/auth")

    @app.get("/api/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/repositories")
    async def repositories():
        return {"repositories": ["private source"]}

    @app.post("/api/repositories/upload")
    async def upload(request: Request):
        return {"bytes": len(await request.body())}

    return app, settings


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/repositories"), ("GET", "/api/sessions"),
    ("GET", "/api/repositories/private/files"), ("POST", "/api/chat"),
    ("DELETE", "/api/repositories/private"), ("POST", "/api/evaluation/run"),
    ("POST", "/api/retrieval/search"), ("GET", "/docs"), ("GET", "/openapi.json"),
])
async def test_anonymous_requests_are_denied_before_route_work(secured_app, method, path):
    app, _ = secured_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://demo.test") as client:
        response = await client.request(method, path)
        assert response.status_code == 401
        assert "private source" not in response.text
        assert (await client.get("/api/health")).status_code == 200


async def test_signin_cookie_logout_revocation_and_bearer(secured_app):
    app, _ = secured_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://demo.test") as client:
        assert not (await client.get("/api/auth/status")).json()["authenticated"]
        assert (await client.post("/api/auth/login", json={"access_key": "wrong"})).status_code == 401
        assert (await client.post("/api/auth/login", json={"access_key": "非ASCII"})).status_code == 401
        login = await client.post("/api/auth/login", json={"access_key": KEY}, headers={"Origin": "https://demo.test"})
        assert login.status_code == 200
        cookie_header = login.headers["set-cookie"].lower()
        assert "httponly" in cookie_header and "secure" in cookie_header and "samesite=strict" in cookie_header
        token = client.cookies[security.COOKIE]
        assert (await client.get("/api/repositories")).status_code == 200
        assert (await client.get("/api/auth/status")).json()["authenticated"]
        assert (await client.post("/api/auth/logout")).status_code == 200
        assert (await client.get("/api/repositories", headers={"cookie": f"{security.COOKIE}={token}"})).status_code == 401
        assert (await client.get("/api/repositories", headers={"Authorization": f"Bearer {KEY}"})).status_code == 200


async def test_cross_site_login_and_mutations_are_rejected(secured_app):
    app, _ = secured_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://demo.test") as client:
        response = await client.post("/api/auth/login", json={"access_key": KEY}, headers={"Origin": "https://evil.test"})
        assert response.status_code == 403
        await client.post("/api/auth/login", json={"access_key": KEY})
        response = await client.post("/api/repositories/upload", content=b"source", headers={"Sec-Fetch-Site": "cross-site"})
        assert response.status_code == 403
        assert (await client.options("/api/repositories", headers={"Origin": "https://evil.test"})).headers.get("access-control-allow-origin") is None


async def test_expired_and_unconfigured_access_fails_closed(secured_app):
    app, settings = secured_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://demo.test") as client:
        await client.post("/api/auth/login", json={"access_key": KEY})
        security._sessions[client.cookies[security.COOKIE]] = time.time() - 1
        assert (await client.get("/api/repositories")).status_code == 401
        settings.access_key = ""
        assert (await client.post("/api/auth/login", json={"access_key": KEY})).status_code == 503
        assert not (await client.get("/api/auth/status")).json()["configured"]


async def test_login_and_authenticated_request_limits(secured_app):
    app, _ = secured_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://demo.test") as client:
        for _ in range(10):
            assert (await client.post("/api/auth/login", json={"access_key": "wrong"})).status_code == 401
        assert (await client.post("/api/auth/login", json={"access_key": "wrong"})).status_code == 429
        for _ in range(10):
            assert (await client.get("/api/repositories", headers={"Authorization": f"Bearer {KEY}"})).status_code == 200
        assert (await client.get("/api/repositories", headers={"Authorization": f"Bearer {KEY}"})).status_code == 429


async def test_streamed_request_without_content_length_is_bounded(secured_app):
    app, _ = secured_app

    async def body():
        for _ in range(3):
            yield b"x" * (1024 * 1024)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://demo.test") as client:
        response = await client.post("/api/repositories/upload", content=body(), headers={"Authorization": f"Bearer {KEY}"})
        assert response.status_code == 413
        response = await client.post("/api/repositories/upload", content=b"x", headers={"Authorization": f"Bearer {KEY}", "Content-Length": str(3 * 1024 * 1024)})
        assert response.status_code == 413


async def test_expensive_operations_are_bounded_and_release_slots(secured_app):
    app, _ = secured_app
    arrived = asyncio.Event()
    release = asyncio.Event()
    count = 0

    @app.post("/api/chat")
    async def chat():
        nonlocal count
        count += 1
        if count == 2:
            arrived.set()
        await release.wait()
        return {"answer": "complete"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://demo.test", headers={"Authorization": f"Bearer {KEY}"}) as client:
        pending = [asyncio.create_task(client.post("/api/chat")) for _ in range(2)]
        await asyncio.wait_for(arrived.wait(), timeout=2)
        assert (await client.post("/api/chat")).status_code == 429
        release.set()
        assert all(response.status_code == 200 for response in await asyncio.gather(*pending))
        assert security._active_operations == 0
        assert (await client.post("/api/chat")).status_code == 200
