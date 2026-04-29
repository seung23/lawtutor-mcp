"""Bearer Token 인증.

LAWTUTOR_API_TOKEN 환경 변수와 요청 헤더의 토큰을 비교한다.
/health 엔드포인트는 인증 없이 접근 가능.
"""

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from lawtutor.config import settings

# 인증을 건너뛸 경로
_PUBLIC_PATHS: set[str] = {"/health"}


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Bearer Token 검증 미들웨어.

    Authorization 헤더에서 Bearer 토큰을 추출하고
    LAWTUTOR_API_TOKEN과 비교한다.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> JSONResponse:
        """요청을 가로채 토큰을 검증한다."""
        # 공개 경로는 인증 생략
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        token = settings.lawtutor_api_token

        # 토큰 미설정 시 거부
        if not token:
            return JSONResponse(
                status_code=500,
                content={"detail": "LAWTUTOR_API_TOKEN is not configured"},
            )

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        provided_token = auth_header[len("Bearer "):]

        # 타이밍 공격 방지를 위해 secrets.compare_digest 사용
        if not secrets.compare_digest(provided_token, token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
            )

        return await call_next(request)
