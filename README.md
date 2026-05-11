# LawTutor MCP

한국 7급 공무원시험(행정직) 행정법/헌법 학습을 위한 **RAG MCP 서버**.

국가법령정보센터의 1차 출처 데이터를 기반으로, Claude Pro 등 MCP 호환 클라이언트에서 법령 조문/판례/헌재결정례/법령해석례를 정확하게 검색할 수 있다.

## 핵심 특징

- **할루시네이션 차단**: 국가법령정보센터 OPEN API 단일 소스 기반 RAG
- **현행 법령 우선**: 시행일자 메타데이터 기반 `is_active` 필터링
- **검색만 제공, 추론은 클라이언트에 위임**: MCP 서버는 도구만 노출, LLM 추론은 Claude가 담당
- **셀프 호스팅**: 집 PC + Docker + Cloudflare Tunnel

## 아키텍처

```
[Claude.ai (사용자)]
   ↓ HTTPS
[Cloudflare Edge] ─ DDoS/WAF 보호, TLS 종단
   ↓ Cloudflare Tunnel
[집 PC]
   ├─ FastAPI + MCP Server (Docker)
   ├─ Qdrant 벡터 DB (Docker)
   └─ BGE-M3 임베딩 모델
```

## MCP Tools

| 도구 | 설명 |
|---|---|
| `search_law` | 행정법/헌법 법령 조문 검색 |
| `search_precedent` | 대법원 판례 검색 |
| `search_constitutional_decision` | 헌법재판소 결정례 검색 |
| `search_legal_interpretation` | 법령해석례 검색 |
| `fetch_article_by_number` | 법령명 + 조문번호로 정확한 조문 조회 |
| `fetch_case_by_number` | 사건번호로 판례/결정례 조회 |

## 기술 스택

- Python 3.11+ / FastAPI / uvicorn
- MCP Python SDK (Streamable HTTP transport)
- Qdrant (벡터 DB)
- BGE-M3 (한국어 임베딩, 1024차원)
- Cloudflare Tunnel (외부 노출)
- Docker Compose

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (패키지 매니저)
- Docker Desktop (Windows) 또는 Docker Engine (Linux)

### 설치

```bash
# 레포 클론
git clone https://github.com/{username}/lawtutor-mcp.git
cd lawtutor-mcp

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 값 채우기

# 의존성 설치
uv sync

# Qdrant 실행
docker compose up -d qdrant
```

### 설정 확인

```bash
uv run python -c "from lawtutor.config import settings; print(settings.model_dump_json(indent=2))"
```

## 프로젝트 구조

```
src/lawtutor/
├── config.py           # 환경 변수 설정 (pydantic-settings)
├── constants.py        # 상수 정의
├── collectors/         # 국가법령정보센터 API 데이터 수집
├── parsers/            # 원본 XML → 정형 데이터 파싱
├── models/             # Pydantic 데이터 모델
├── chunking/           # 법령/판례 청킹 전략
├── embeddings/         # BGE-M3 임베딩
├── vector_store/       # Qdrant 인터페이스
├── retrieval/          # 검색 로직
├── mcp_server/         # MCP 서버 + 도구 정의
└── evaluation/         # 검색 정확도 평가
```

## 데이터 소스

모든 데이터는 [국가법령정보센터 OPEN API](https://open.law.go.kr)에서만 수집한다.
외부 사이트 크롤링은 사용하지 않는다.

## 배포

집 PC에서 Docker Compose + Cloudflare Tunnel로 24/7 운영한다.
상세 절차는 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) 참조.

## 문서

- [PRD](docs/PRD.md) - 제품 요구사항
- [Architecture](docs/ARCHITECTURE.md) - 시스템 아키텍처
- [Milestones](docs/MILESTONES.md) - 단계별 작업 계획
- [Deployment](docs/DEPLOYMENT.md) - 배포 가이드

## License

MIT
