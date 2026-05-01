# =============================================================================
# LawTutor MCP Server - Dockerfile
# 멀티스테이지 빌드: 빌드 스테이지에서 의존성 설치, 런타임은 slim 이미지
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# 시스템 빌드 의존성 (일부 패키지가 C 확장을 컴파일할 수 있음)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# 의존성 먼저 복사 → 캐시 활용
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --prefix=/install .

# 소스 코드 복사 후 패키지 설치
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps --prefix=/install .

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# 보안: non-root 유저
RUN groupadd -r lawtutor && useradd -r -g lawtutor -m lawtutor

WORKDIR /app

# 빌드 스테이지에서 설치된 패키지 복사
COPY --from=builder /install /usr/local

# 스크립트 복사 (run_server.py)
COPY scripts/ ./scripts/

# 소유권 설정
RUN chown -R lawtutor:lawtutor /app

# non-root 유저로 전환
USER lawtutor

# 환경 변수 기본값
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 헬스체크 (30초 간격, 10초 타임아웃, 3회 실패 시 unhealthy)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

CMD ["python", "scripts/run_server.py"]
