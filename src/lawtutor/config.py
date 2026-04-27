"""LawTutor MCP 서버 설정.

모든 환경 변수 접근은 이 모듈의 settings 인스턴스를 통해서만 수행한다.
os.getenv() 직접 호출 금지.
"""

from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 프로젝트 루트 디렉토리 (src/lawtutor/config.py 기준 3단계 상위)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """환경 변수 기반 애플리케이션 설정."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- 국가법령정보센터 API --
    law_go_kr_oc: str = Field(
        default="",
        description="국가법령정보센터 OPEN API 인증용 OC (이메일 ID)",
    )

    # -- 임베딩 모델 --
    embedding_provider: str = Field(
        default="bge_m3",
        description="임베딩 모델 제공자",
    )
    bge_m3_model_path: str = Field(
        default="BAAI/bge-m3",
        description="BGE-M3 모델 경로 (HuggingFace repo 또는 로컬 경로)",
    )
    bge_m3_device: str = Field(
        default="cpu",
        description="임베딩 실행 디바이스 (cpu 또는 cuda)",
    )

    # -- Qdrant --
    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant 서버 호스트 (Docker 내부: qdrant, 로컬 개발: localhost)",
    )
    qdrant_port: int = Field(
        default=6333,
        description="Qdrant REST API 포트",
    )

    # -- MCP 서버 --
    mcp_server_host: str = Field(
        default="0.0.0.0",
        description="MCP 서버 바인딩 호스트",
    )
    mcp_server_port: int = Field(
        default=8000,
        description="MCP 서버 포트",
    )
    lawtutor_api_token: str = Field(
        default="",
        description="Bearer Token 인증용 API 토큰 (32자 이상 랜덤)",
    )

    # -- Cloudflare Tunnel --
    tunnel_token: str = Field(
        default="",
        description="Cloudflare Tunnel 토큰 (docker-compose에서 사용)",
    )

    # -- 데이터 경로 --
    data_raw_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "raw",
        description="API 응답 원본 저장 경로",
    )
    data_parsed_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "parsed",
        description="파싱된 데이터 저장 경로",
    )

    # -- 로깅 --
    log_level: str = Field(
        default="INFO",
        description="로그 레벨 (DEBUG, INFO, WARNING, ERROR)",
    )

    # -- Rate Limit --
    rate_limit_per_minute: int = Field(
        default=60,
        description="분당 최대 요청 수",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings 싱글턴 인스턴스를 반환한다."""
    return Settings()


# 편의를 위한 모듈 레벨 인스턴스
settings = get_settings()
