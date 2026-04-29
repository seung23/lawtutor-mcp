"""Bearer Token 인증 미들웨어 단위 테스트."""

import pytest
from unittest.mock import patch, PropertyMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lawtutor.mcp_server.auth import BearerTokenMiddleware

TEST_TOKEN = "test-secret-token-12345678901234"


def _make_app() -> FastAPI:
    """테스트용 FastAPI 앱을 생성한다."""
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/protected")
    async def protected() -> dict:
        return {"data": "secret"}

    app.add_middleware(BearerTokenMiddleware)
    return app


class TestBearerTokenMiddleware:
    """Bearer Token 미들웨어 테스트."""

    def test_health_no_auth_required(self) -> None:
        """헬스체크는 인증 없이 접근 가능."""
        with patch("lawtutor.mcp_server.auth.settings") as mock:
            mock.lawtutor_api_token = TEST_TOKEN
            client = TestClient(_make_app())
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_protected_no_token(self) -> None:
        """토큰 없이 보호된 경로 접근 시 401."""
        with patch("lawtutor.mcp_server.auth.settings") as mock:
            mock.lawtutor_api_token = TEST_TOKEN
            client = TestClient(_make_app())
            resp = client.get("/protected")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_protected_wrong_token(self) -> None:
        """잘못된 토큰으로 접근 시 401."""
        with patch("lawtutor.mcp_server.auth.settings") as mock:
            mock.lawtutor_api_token = TEST_TOKEN
            client = TestClient(_make_app())
            resp = client.get(
                "/protected",
                headers={"Authorization": "Bearer wrong-token"},
            )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_protected_valid_token(self) -> None:
        """올바른 토큰으로 접근 시 200."""
        with patch("lawtutor.mcp_server.auth.settings") as mock:
            mock.lawtutor_api_token = TEST_TOKEN
            client = TestClient(_make_app())
            resp = client.get(
                "/protected",
                headers={"Authorization": f"Bearer {TEST_TOKEN}"},
            )
        assert resp.status_code == 200
        assert resp.json()["data"] == "secret"

    def test_protected_no_bearer_prefix(self) -> None:
        """Bearer 접두사 없이 토큰만 보내면 401."""
        with patch("lawtutor.mcp_server.auth.settings") as mock:
            mock.lawtutor_api_token = TEST_TOKEN
            client = TestClient(_make_app())
            resp = client.get(
                "/protected",
                headers={"Authorization": "Token some-token"},
            )
        assert resp.status_code == 401

    def test_empty_token_config(self) -> None:
        """토큰이 설정되지 않으면 500."""
        with patch("lawtutor.mcp_server.auth.settings") as mock:
            mock.lawtutor_api_token = ""
            client = TestClient(_make_app())
            resp = client.get(
                "/protected",
                headers={"Authorization": "Bearer any-token"},
            )
        assert resp.status_code == 500
        assert "not configured" in resp.json()["detail"]
