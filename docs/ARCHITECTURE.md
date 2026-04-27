# ARCHITECTURE - LawTutor MCP

## 1. 시스템 전체 구조

```
[여자친구분의 디바이스]
   ↓ HTTPS (Claude.ai 웹/앱)
[Claude.ai 서비스 (Anthropic)]
   ↓ HTTPS (MCP Streamable HTTP)
[Cloudflare Edge (전세계 PoP)]
   ↓ 아웃바운드 전용 영구 연결 (cloudflared)
[승의 집 데스크탑 PC]
   ├─ cloudflared (Cloudflare Tunnel 데몬)
   ├─ FastAPI + MCP Server (Python, Docker 컨테이너)
   ├─ Qdrant (Docker 컨테이너)
   └─ BGE-M3 임베딩 모델 (메모리 로드)
```

핵심 포인트:
- **LLM은 본 서버에 없다.** Claude Pro가 LLM 역할.
- 본 서버는 **검색 도구만 노출**하는 MCP 서버.
- **Cloudflare Tunnel 사용**: 라우터 포트포워딩 불필요, 공인 IP 노출 안 됨.
- Cloudflare Edge에서 HTTPS 종단 → 자체 TLS 인증서 관리 불필요.
- DDoS 보호와 WAF는 Cloudflare 무료 제공.

---

## 2. 디렉토리 구조

```
lawtutor-mcp/
├── CLAUDE.md                       # 프로젝트 규칙 (Claude Code 자동 로드)
├── README.md                       # 프로젝트 소개
├── pyproject.toml                  # 의존성 관리
├── .env.example                    # 환경 변수 템플릿
├── .env                            # 실제 환경 변수 (gitignore)
├── .gitignore
├── .gitattributes                  # 줄바꿈 LF 강제 (Windows 호환)
├── docker-compose.yml              # app + qdrant + cloudflared 컨테이너
├── Dockerfile                      # 앱 이미지 빌드
│
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md             # 이 문서
│   ├── MILESTONES.md
│   ├── DEPLOYMENT.md               # 집 PC + Cloudflare Tunnel 배포 가이드
│   └── PROMPTING.md
│
├── src/
│   ├── lawtutor/
│   │   ├── __init__.py
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   ├── constants.py            # 상수 정의
│   │   │
│   │   ├── collectors/             # M1: 데이터 수집
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseCollector
│   │   │   ├── law_collector.py
│   │   │   ├── prec_collector.py
│   │   │   ├── detc_collector.py
│   │   │   └── expc_collector.py
│   │   │
│   │   ├── parsers/                # 원본 → 정형 데이터 파싱
│   │   │   ├── __init__.py
│   │   │   ├── law_parser.py
│   │   │   ├── prec_parser.py
│   │   │   ├── detc_parser.py
│   │   │   └── expc_parser.py
│   │   │
│   │   ├── models/                 # Pydantic 데이터 모델
│   │   │   ├── __init__.py
│   │   │   ├── law.py
│   │   │   ├── precedent.py
│   │   │   ├── decision.py
│   │   │   ├── interpretation.py
│   │   │   └── search.py           # MCP 도구 출력 모델
│   │   │
│   │   ├── chunking/               # M2: 청킹 전략
│   │   │   ├── __init__.py
│   │   │   ├── law_chunker.py
│   │   │   ├── prec_chunker.py
│   │   │   └── chunk_models.py
│   │   │
│   │   ├── embeddings/             # M2: 임베딩
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── bge_m3.py
│   │   │
│   │   ├── vector_store/           # M2: Qdrant 인터페이스
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── retrieval/              # M3: 검색 로직
│   │   │   ├── __init__.py
│   │   │   ├── retriever.py
│   │   │   └── formatter.py
│   │   │
│   │   ├── mcp_server/             # M3-M4: MCP 서버
│   │   │   ├── __init__.py
│   │   │   ├── server.py
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── search_law.py
│   │   │   │   ├── search_precedent.py
│   │   │   │   ├── search_decision.py
│   │   │   │   ├── search_interpretation.py
│   │   │   │   ├── fetch_article.py
│   │   │   │   └── fetch_case.py
│   │   │   ├── auth.py             # Bearer Token 검증
│   │   │   └── http_app.py         # FastAPI 통합
│   │   │
│   │   └── evaluation/             # M5: 평가
│   │       ├── __init__.py
│   │       ├── eval_set.py
│   │       ├── metrics.py
│   │       └── runner.py
│   │
├── scripts/                        # 실행 스크립트
│   ├── collect_all.py
│   ├── parse_all.py
│   ├── chunk_and_embed.py
│   ├── run_eval.py
│   ├── run_server.py               # 로컬 개발용 서버 실행
│   └── deploy/                     # 배포 스크립트
│       ├── start_windows.ps1       # Windows 자동 시작 PowerShell 스크립트
│       ├── start_linux.sh          # Linux 자동 시작 스크립트
│       └── healthcheck.sh          # 외부 모니터링 cron용
│
├── data/                           # gitignore
│   ├── raw/
│   │   ├── law/
│   │   ├── prec/
│   │   ├── detc/
│   │   └── expc/
│   ├── parsed/
│   └── eval/
│       └── eval_set_v1.jsonl       # (이건 git 포함)
│
├── tests/
│   ├── conftest.py
│   ├── test_collectors/
│   ├── test_parsers/
│   ├── test_chunking/
│   ├── test_retrieval/
│   ├── test_mcp_server/
│   │   ├── test_tools.py
│   │   ├── test_auth.py
│   │   └── test_e2e.py
│   └── test_evaluation/
│
└── qdrant_storage/                 # gitignore (Qdrant 영구 데이터)
```

---

## 3. 데이터 흐름

### 3.1 빌드 타임 (인덱스 구축)

```
[국가법령정보센터 OPEN API]
        ↓ (HTTP, XML)
[Collectors] → data/raw/{target}/{date}/*.xml
        ↓
[Parsers] → data/parsed/{target}/*.json
        ↓
[Chunkers] → 메타데이터 보존 청크 생성
        ↓
[Embedders (BGE-M3)] → 청크별 1024차원 벡터
        ↓
[Qdrant Client] → 4개 컬렉션 upsert
```

### 3.2 런타임 (사용자 질문 처리)

```
[사용자] Claude.ai에 질문 입력
   ↓
[Claude Pro] 질문 분석, MCP 도구 호출 결정
   ↓ HTTPS POST https://lawtutor.{도메인}/mcp
[Cloudflare Edge] HTTPS 종단, WAF/DDoS 보호
   ↓ Cloudflared 영구 터널 (아웃바운드 연결)
[집 PC의 cloudflared] 트래픽 수신
   ↓ Docker 내부 네트워크
[FastAPI 컨테이너] Bearer Token 검증
   ↓
[MCP Server] 도구 실행 (search_law 등)
   ↓
[Retriever] 쿼리 임베딩 → Qdrant 검색 → 메타데이터 필터링
   ↓
[Formatter] MCP 응답 형식으로 변환
   ↓ 응답 (역방향 동일 경로)
[Claude Pro] 검색 결과 받아서 답변 생성
   ↓
[사용자] 답변 표시
```

---

## 4. MCP 서버 구조 상세

### 4.1 사용할 MCP 라이브러리

`mcp` 공식 Python SDK 사용 (FastMCP는 사용자 승인 후).

```python
# 의사코드
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("LawTutor")

@mcp.tool()
async def search_law(
    query: str,
    top_k: int = 5,
    law_name_filter: str | None = None,
    include_historical: bool = False,
) -> SearchResponse:
    """한국 행정법/헌법 법령 조문을 검색합니다.
    
    사용자가 특정 조문, 법령 개념, 사례형 적용 질문을 할 때 사용합니다.
    검색된 조문은 출처 메타데이터(법령명, 조문번호, 시행일)와 함께 반환됩니다.
    """
    ...
```

### 4.2 Transport 선택

**Streamable HTTP** 사용 (2025년 11월 표준).
SSE는 deprecated이므로 사용 금지.

FastAPI에 마운트:
```python
app = FastAPI()
app.mount("/mcp", mcp.streamable_http_app())
```

### 4.3 인증 흐름

**1차 방어**: Bearer Token

```
요청 헤더:
  Authorization: Bearer {LAWTUTOR_API_TOKEN}

검증:
  - 토큰이 .env의 값과 일치
  - 일치하지 않으면 401
```

**2차 방어 (선택, 권장)**: Cloudflare Access

Cloudflare Tunnel과 함께 Cloudflare Access를 활성화하면:
- 무료 플랜 50명까지
- 이메일 OTP, Google SSO, GitHub 인증 등 선택
- MCP 서버 코드 변경 없이 추가 인증 레이어 적용
- 다만 Claude.ai의 Custom Connector가 OAuth를 거쳐야 하므로, 초기에는 Bearer Token만으로 운영하다가 안정화 후 추가 검토

### 4.4 도구별 구현 패턴

각 search_* 도구는 동일한 패턴:

```python
async def search_X(query: str, ...) -> SearchResponse:
    # 1. 입력 검증 (Pydantic이 자동 처리)
    # 2. 임베딩 생성
    query_vector = await embedder.embed(query)
    # 3. Qdrant 검색
    raw_results = await qdrant.search(
        collection_name="X",
        query_vector=query_vector,
        query_filter=build_filter(...),
        limit=top_k,
    )
    # 4. 응답 형식으로 변환
    return formatter.format(raw_results, query)
```

### 4.5 Tool description 작성 원칙

MCP tool의 description은 **LLM이 읽고 도구를 선택하는 기준**이다. 다음을 포함:

1. 무엇을 하는 도구인지 (한 줄 요약)
2. 언제 사용해야 하는지 (트리거 시나리오)
3. 입력 인자 설명 (Pydantic Field description)
4. 출력 형태 안내

예시 (search_law):
```
한국 행정법/헌법 법령 조문을 RAG로 검색합니다.

[사용 시점]
- 사용자가 특정 법령의 조문 내용을 묻는 경우 ("행정절차법 제21조에 대해")
- 법령 개념을 묻는 경우 ("처분의 사전통지란?")
- 사례형 적용 질문 ("이 경우 어떤 조문이 적용되나?")

[반환]
top_k 개의 조문 청크. 각 청크는 본문 + 메타데이터(법령명, 조문번호, 시행일, 현행 여부 등).

[참고]
판례 질문에는 search_precedent를, 헌재결정례에는 search_constitutional_decision을 사용하세요.
```

---

## 5. Qdrant 컬렉션 설계

### 5.1 컬렉션 분리 정책
컬렉션을 4개로 분리한다.

| 컬렉션 | 데이터 | 주 검색 도구 |
|---|---|---|
| `laws` | 법령 조문 | search_law, fetch_article_by_number |
| `precedents` | 대법원 판례 | search_precedent, fetch_case_by_number |
| `decisions` | 헌재결정례 | search_constitutional_decision, fetch_case_by_number |
| `interpretations` | 법령해석례 | search_legal_interpretation |

### 5.2 벡터 차원
- BGE-M3: 1024 차원

### 5.3 Payload 인덱싱
검색 시 필터링용으로 다음 필드는 Qdrant payload index로 등록:
- 공통: `is_active`, `source_type`
- 법령: `law_name`, `effective_date`
- 판례: `court`, `judgment_date`, `referenced_articles`
- 헌재결정: `decision_type`, `decision_date`

---

## 6. 청킹 전략

### 6.1 법령 청킹

법령은 **조(條) 단위로 청킹**한다.

기본 단위: 조 (Article)
- 한 조가 길지 않으면(< 800자) 조 전체를 하나의 청크로
- 한 조가 길면(>= 800자) 항(項) 단위로 분할

청크 텍스트 형식:
```
[법령명] [조문번호] [조문 제목]
[조문 본문 전체]
[항/호 구조 그대로 보존]
```

예시:
```
행정절차법 제21조 (처분의 사전 통지)
① 행정청은 당사자에게 의무를 부과하거나 권익을 제한하는 처분을 하는 경우에는 미리 다음 각 호의 사항을 당사자등에게 통지하여야 한다.
1. 처분의 제목
2. 당사자의 성명 또는 명칭과 주소
...
```

청크 메타데이터:
- 모든 법령 메타데이터 필드 (PRD 3.3 참조)
- 추가: `chunk_type` = "article" 또는 "paragraph"

### 6.2 판례 청킹

판례는 **섹션 단위로 분할**.

청크 분할:
- 청크 1: 판시사항 (holding) + 메타데이터
- 청크 2: 판결요지 (summary) + 메타데이터
- 청크 3: 이유 (reasoning) + 메타데이터 (길면 항목 단위 추가 분할)

각 청크에 동일한 `case_id`, `case_no` 부여.

청크 텍스트 형식:
```
[법원] [선고일자] [사건번호] [사건명]
[섹션명: 판시사항/판결요지/이유]
[본문]
```

### 6.3 헌재결정례 청킹

판례와 동일한 전략.

### 6.4 법령해석례 청킹

해석례는 짧은 편이라 안건당 1~2 청크. `질의요지` + `회답` + `이유`를 하나로 묶거나 분할.

---

## 7. 환경 변수

`.env.example`:
```
# 국가법령정보센터 API
LAW_GO_KR_OC=your_email_id_here

# 임베딩
EMBEDDING_PROVIDER=bge_m3
BGE_M3_MODEL_PATH=BAAI/bge-m3
BGE_M3_DEVICE=cpu                # cpu 또는 cuda (GPU 있으면 cuda)

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# MCP 서버
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
LAWTUTOR_API_TOKEN=secret_random_token_here   # Bearer Token

# Cloudflare Tunnel
TUNNEL_TOKEN=cloudflare_tunnel_token_here     # cloudflared용

# 데이터 경로
DATA_RAW_DIR=./data/raw
DATA_PARSED_DIR=./data/parsed

# 로깅
LOG_LEVEL=INFO

# Rate limit
RATE_LIMIT_PER_MINUTE=60
```

---

## 8. 의존성 핵심 (pyproject.toml)

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",                  # 공식 MCP Python SDK
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "qdrant-client>=1.12.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "FlagEmbedding>=1.3.0",        # BGE-M3
    "tenacity>=9.0.0",
    "structlog>=24.0.0",
    "slowapi>=0.1.9",              # Rate limiting
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.7.0",
    "black>=24.0.0",
]
```

**주의: anthropic, openai, langgraph, langchain 등 LLM 관련 SDK는 본 서버에 추가하지 않는다.**

---

## 9. 배포 아키텍처 (집 PC + Cloudflare Tunnel)

### 9.1 호스트 환경
- **하드웨어**: 사용자(승) 본인 데스크탑 PC
- **OS**: Windows 10/11 (1순위) 또는 Linux (Ubuntu 등)
- **Docker**: Docker Desktop (Windows) 또는 Docker Engine (Linux)
- **외부 노출**: Cloudflare Tunnel (cloudflared 데몬)

### 9.2 컨테이너 구성

`docker-compose.yml`로 3개 서비스 관리:

| 서비스 | 역할 | 외부 노출 |
|---|---|---|
| `app` | FastAPI + MCP 서버 | 내부 네트워크만 (cloudflared가 접근) |
| `qdrant` | 벡터 DB | 내부 네트워크만 |
| `cloudflared` | Cloudflare Tunnel 데몬 | 아웃바운드 only |

`app`은 호스트의 어떤 포트에도 직접 바인딩하지 않는다. cloudflared가 Docker 내부 네트워크로 `app:8000`에 접근.

### 9.3 자원 요구사항

| 항목 | RAM | CPU |
|---|---|---|
| FastAPI 앱 | ~500MB | 평소 1% |
| Qdrant | 1~2GB | 검색 시 잠깐 |
| BGE-M3 모델 | 2~3GB | 임베딩 시 |
| cloudflared | ~100MB | 거의 0 |
| **합계** | **~6GB** | **여유로움** |

승님 PC가 16GB 이상 RAM이면 본인 작업과 병행 가능.
GPU(NVIDIA)가 있으면 BGE-M3 임베딩 속도 5~10배 향상. CPU 모드도 충분히 동작.

### 9.4 Cloudflare Tunnel 동작 원리

cloudflared는 머신에서 Cloudflare 엣지로 아웃바운드 전용 영구 연결을 연다.
인바운드 트래픽이 그 연결을 타고 들어온다.

핵심:
- **포트 개방 불필요** (라우터 포트포워딩 X)
- **공인 IP 노출 안 됨** (내부 IP 정보가 외부에 안 보임)
- **HTTPS는 Cloudflare 엣지에서 종단** (자체 인증서 X)
- **DDoS 보호와 WAF가 무료**

### 9.5 24/7 운영 안정성

다음 시나리오에 대응:

| 상황 | 대응 |
|---|---|
| 인터넷 일시 단절 | cloudflared 자동 재연결 |
| PC 재부팅 | Docker Desktop 자동 시작 + `restart: unless-stopped` |
| 절전모드 진입 | Windows 전원 옵션에서 "디스크/디스플레이만 끄기" 설정 |
| Cloudflare 엣지 장애 | 다른 엣지 노드로 자동 전환 |

자세한 절차는 `docs/DEPLOYMENT.md` 참조.

---

## 10. 보안 고려사항

### 10.1 위협 모델
- 공개 인터넷에 노출된 MCP 서버
- 무차별 토큰 brute force
- DoS 공격
- 부적절한 검색 쿼리 (저장된 데이터는 공개 법령이라 데이터 유출 우려 낮음)
- **집 네트워크 보안** (특히 중요)

### 10.2 대응
- HTTPS 강제 (Cloudflare 엣지에서 종단)
- Bearer Token 검증 (강한 랜덤 문자열, 32바이트 이상)
- Rate limiting (IP 기반, 분당 60)
- **라우터 포트포워딩 절대 X**: Cloudflare Tunnel만 사용
- Docker 컨테이너 격리: 호스트 파일시스템 접근 최소화
- cloudflared 토큰을 .env로 관리, git 커밋 금지
- (선택) Cloudflare Access로 SSO/이메일 인증 추가

### 10.3 향후 보강
사용자 수가 늘어나거나 보안 요구사항이 높아지면:
- Cloudflare Access (Zero Trust) 적용
- API 토큰 로테이션 정책
- mTLS 적용
