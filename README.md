# LawTutor MCP

한국 7급 공무원시험(행정직) 행정법/헌법 학습을 위한 **RAG MCP 서버**.

국가법령정보센터 OPEN API에서 수집한 **94만 건의 법령·판례·결정례** 데이터를 벡터 DB에 인덱싱하고, Claude Pro 등 MCP 호환 클라이언트에서 정확하게 검색할 수 있도록 6개 도구를 제공한다.

## 핵심 특징

- **할루시네이션 차단**: 국가법령정보센터 OPEN API 단일 소스 기반 RAG. 존재하지 않는 조문·판례 생성 방지
- **하이브리드 검색**: BGE-M3 dense(1024차원) + sparse(lexical) 벡터를 RRF(Reciprocal Rank Fusion)로 융합
- **리랭킹**: 법률 용어 동의어 확장 + N-gram 타이틀 부스트로 법령 검색 정확도 향상
- **현행 법령 우선**: 시행일자 메타데이터 기반 `is_active` 필터링
- **검색만 제공, 추론은 클라이언트에 위임**: MCP 서버는 도구만 노출, LLM 추론은 Claude Pro가 담당
- **셀프 호스팅**: 집 PC + Docker + Cloudflare Tunnel (월 운영비 ~1만원)

## 데이터 규모

| 컬렉션 | 건수 | 데이터 소스 |
|---------|------|-------------|
| 법령 조문 (laws) | 240,695 | 5,500+ 법령의 조문 단위 청크 |
| 대법원 판례 (precedents) | 579,012 | 대법원 판례 섹션 단위 청크 |
| 헌재결정례 (decisions) | 99,394 | 헌법재판소 결정례 |
| 법령해석례 (interpretations) | 26,839 | 법제처·행안부 유권해석 |
| **합계** | **945,940** | |

## 검색 품질

10건 평가셋 기준 (top_k=5):

| 메트릭 | 수치 | 목표 |
|--------|------|------|
| Recall@5 | **0.90** | 0.80 |
| MRR | **0.78** | - |
| 메타데이터 무결성 | **1.00** | - |

```bash
# 평가 실행
uv run python scripts/run_eval.py
```

## 아키텍처

```
[Claude.ai (사용자)]
   ↓ HTTPS
[Cloudflare Edge] ─ DDoS/WAF 보호, TLS 종단
   ↓ Cloudflare Tunnel
[집 PC - Docker Compose]
   ├─ FastAPI + MCP Server
   ├─ Qdrant 벡터 DB (dense + sparse 하이브리드)
   └─ BGE-M3 임베딩 모델 (CPU)
```

### 검색 파이프라인

```
쿼리 → 동의어 확장 → BGE-M3 임베딩(dense+sparse)
  → Qdrant 하이브리드 검색 (RRF fusion)
  → 동의어 타이틀 직접 매칭 병합
  → N-gram 타이틀 부스트 리랭킹
  → top_k 결과 반환
```

## MCP Tools

| 도구 | 설명 |
|---|---|
| `search_law` | 법령 조문 검색 (5,500+ 법령, 하이브리드 검색 + 리랭킹) |
| `search_precedent` | 대법원 판례 검색 (기본 필터: 대법원) |
| `search_constitutional_decision` | 헌법재판소 결정례 검색 |
| `search_legal_interpretation` | 법제처/행안부 유권해석례 검색 |
| `fetch_article_by_number` | 법령명 + 조문번호로 정확한 조문 조회 (payload 필터) |
| `fetch_case_by_number` | 사건번호로 판례/결정례 조회 (payload 필터) |

모든 도구는 DB 미스 시 국가법령정보센터 API 실시간 폴백을 지원한다.

## 기술 스택

- **언어/프레임워크**: Python 3.11+ / FastAPI / uvicorn
- **MCP**: MCP Python SDK (Streamable HTTP transport)
- **벡터 DB**: Qdrant (named vectors: dense + sparse)
- **임베딩**: BGE-M3 (한국어, 1024차원 dense + lexical sparse)
- **검색**: RRF 하이브리드 검색 + 동의어 확장 + N-gram 타이틀 부스트
- **데이터 검증**: Pydantic v2
- **배포**: Docker Compose + Cloudflare Tunnel
- **평가**: Recall@K, MRR, 메타데이터 무결성 자동 평가

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (패키지 매니저)
- Docker Desktop (Windows) 또는 Docker Engine (Linux)

### 설치

```bash
# 레포 클론
git clone https://github.com/seung23/lawtutor-mcp.git
cd lawtutor-mcp

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 값 채우기

# 의존성 설치
uv sync

# Docker 서비스 실행
docker compose up -d
```

### 설정 확인

```bash
uv run python -c "from lawtutor.config import settings; print(settings.model_dump_json(indent=2))"
```

## 프로젝트 구조

```
src/lawtutor/
├── config.py           # 환경 변수 설정 (pydantic-settings)
├── constants.py        # 상수 + 법률 동의어 매핑
├── collectors/         # 국가법령정보센터 API 데이터 수집
├── parsers/            # 원본 XML → 정형 데이터 파싱
├── models/             # Pydantic 데이터 모델
├── chunking/           # 법령(조 단위)/판례(섹션 단위) 청킹
├── embeddings/         # BGE-M3 임베딩 (dense + sparse)
├── vector_store/       # Qdrant 인터페이스 (하이브리드 검색)
├── retrieval/          # 검색 + 리랭킹 로직
├── mcp_server/         # MCP 서버 + 6개 도구 정의
└── evaluation/         # Recall@K / MRR 자동 평가
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
