"""MCP 서버 로컬 실행 스크립트.

사용법:
    uv run python scripts/run_server.py
    uv run python scripts/run_server.py --host 127.0.0.1 --port 9000
"""

import argparse

import uvicorn

from lawtutor.config import settings


def main() -> None:
    """서버를 시작한다."""
    parser = argparse.ArgumentParser(description="LawTutor MCP 서버 실행")
    parser.add_argument(
        "--host",
        default=settings.mcp_server_host,
        help=f"바인딩 호스트 (기본: {settings.mcp_server_host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.mcp_server_port,
        help=f"포트 (기본: {settings.mcp_server_port})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="코드 변경 시 자동 리로드 (개발용)",
    )
    args = parser.parse_args()

    # 토큰 미설정 경고
    if not settings.lawtutor_api_token:
        print("WARNING: LAWTUTOR_API_TOKEN이 설정되지 않았습니다.")
        print("  .env 파일에 LAWTUTOR_API_TOKEN을 설정하세요.")
        print("  생성 예: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        return

    print(f"LawTutor MCP 서버 시작: http://{args.host}:{args.port}")
    print(f"  Health: http://{args.host}:{args.port}/health")
    print(f"  MCP:    http://{args.host}:{args.port}/mcp")

    uvicorn.run(
        "lawtutor.mcp_server.http_app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
