"""FastAPI HTTP 앱.

/health + /mcp (Rate Limit) 엔드포인트를 제공한다.
인증은 Cloudflare Tunnel + WAF에 위임한다.
Claude.ai Custom Connector는 OAuth만 지원하므로 Bearer Token 미들웨어를 제거했다.
"""

import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from lawtutor.constants import MCP_SERVER_NAME, MCP_SERVER_VERSION
from lawtutor.mcp_server.server import mcp

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


def _rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded,
) -> JSONResponse:
    """Rate limit 초과 시 429 응답."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


# ---------------------------------------------------------------------------
# FastAPI 앱 생성
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """FastAPI 앱을 생성하고 미들웨어/라우트를 등록한다."""
    # MCP session manager를 먼저 준비 (lifespan에서 사용)
    mcp_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """MCP session manager의 lifecycle을 관리한다."""
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title=MCP_SERVER_NAME,
        version=MCP_SERVER_VERSION,
        docs_url=None,   # Swagger UI 비활성화 (프로덕션)
        redoc_url=None,
        lifespan=lifespan,
    )

    # Rate Limiter 등록
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # -----------------------------------------------------------------------
    # /health — 헬스체크
    # -----------------------------------------------------------------------
    @app.get("/health")
    async def health() -> dict:
        """서버 상태를 반환한다. 인증 불필요."""
        return {
            "status": "ok",
            "service": MCP_SERVER_NAME,
            "version": MCP_SERVER_VERSION,
        }

    # -----------------------------------------------------------------------
    # /mcp — MCP Streamable HTTP (인증 필요)
    # streamable_http_app()이 이미 /mcp 경로를 내부에 포함하므로
    # 루트에 마운트해야 최종 경로가 /mcp가 된다.
    # -----------------------------------------------------------------------
    app.mount("/", mcp_app)

    return app
