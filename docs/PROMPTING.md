# PROMPTING - Claude Code 작업 지시문 패턴

이 문서는 사용자(승)가 Claude Code 세션에서 사용할 지시문 템플릿을 모은다.
각 지시문은 그대로 복사해서 사용하거나 상황에 맞게 미세 조정할 것.

---

## 0. Claude Code 사용 시 일반 원칙

1. 새 세션 시작 시 항상 먼저 다음을 읽게 한다:
   ```
   먼저 @CLAUDE.md, @docs/PRD.md, @docs/ARCHITECTURE.md, @docs/MILESTONES.md, @docs/DEPLOYMENT.md를 읽어줘.
   읽은 후 "준비됨"이라고만 답하고 다음 지시를 기다려.
   ```

2. 작업 지시는 **마일스톤 단위 또는 그 하위 단위**로 쪼개서 던진다.

3. Claude Code가 폭주하려 하면 다음으로 제어:
   ```
   잠깐. 너무 많이 만들지 말고, 우선 X 모듈만 만들어서 보여줘.
   다른 모듈은 내가 OK한 다음에 진행해.
   ```

4. Claude Code가 추측성 코드를 작성할 조짐이 보이면:
   ```
   추측하지 말고, 모르는 부분은 나에게 질문해.
   특히 API 응답 구조와 MCP SDK 사용법은 실제 호출 결과와 공식 문서를 보고 결정하자.
   ```

---

## 1. 첫 세션 (M0: 부트스트랩)

```
프로젝트 루트의 @CLAUDE.md, @docs/PRD.md, @docs/ARCHITECTURE.md, @docs/MILESTONES.md, @docs/DEPLOYMENT.md를 먼저 읽어줘.

이 프로젝트는 한국 7급 공무원시험 행정법/헌법 학습용 RAG MCP 서버다.
LLM은 Claude Pro가 담당하고, 본 서버는 검색 도구만 제공한다.
배포는 내 집 데스크탑 PC에 Docker로, Cloudflare Tunnel을 통해 외부 노출한다.

오늘은 M0 부트스트랩을 진행한다. MILESTONES.md의 M0 섹션을 기준으로 작업해.

작업 시작 전에 다음 4가지를 결정해서 보고해:
1. 패키지 매니저 선택 (uv 추천 + 이유)
2. Python 버전 (3.11 vs 3.12)
3. 디렉토리 골격에서 추가/변경하고 싶은 부분
4. 호스트 OS가 Windows일 때 줄바꿈/경로 이슈 방지 설정 (.gitattributes 등)

내가 OK 하면 다음 순서로 만들어줘:
1. pyproject.toml + .python-version
2. .gitignore + .gitattributes + .env.example
3. 디렉토리 골격 (빈 __init__.py 포함)
4. docker-compose.yml (Qdrant 서비스만, 일단)
5. src/lawtutor/config.py (Settings)
6. src/lawtutor/constants.py (TARGET_LAWS 등)
7. README.md 초안
8. git init + 첫 커밋

각 파일 만들 때마다 내용 보여주고 진행 확인.
```

---

## 2. M1: 데이터 수집

### 2.1 사전 조사

```
M1 데이터 수집을 시작하기 전에 사전 조사부터 한다.

1. 국가법령정보센터 OPEN API 가이드를 웹 검색해서 다음 확인:
   - lawSearch.do 엔드포인트의 쿼리 파라미터 전체 목록
   - 각 target(law/prec/detc/expc)별 응답 구조 차이
   - 페이징 파라미터
   - 응답 형식이 XML인지 JSON인지, 인코딩
   - Rate limit 명시 여부

2. 결과를 docs/api_reference.md 로 정리. 추측 금지. 출처 URL 명시.

3. 정리한 내용 보고 OK 하면 BaseCollector 구현으로 진행.
```

### 2.2 BaseCollector

```
BaseCollector 구현.

요구사항:
- src/lawtutor/collectors/base.py
- httpx.AsyncClient 사용
- OC 인증 자동 주입
- tenacity로 재시도 (5xx, 네트워크 오류, 타임아웃)
- 응답 원본을 data/raw/{target}/{YYYY-MM-DD}/ 디렉토리에 저장 (pathlib.Path 사용, Windows 호환)
- 호출 간 sleep으로 rate limit 대응
- 구조화된 로깅 (structlog)

구현 후 단위 테스트:
- tests/test_collectors/test_base.py
- httpx mock 사용

코드 보여주기 전에:
1. 클래스 인터페이스 시그니처 먼저 보여주기
2. 핵심 메서드 로직을 의사코드로 설명
OK 받은 후 실제 구현.
```

### 2.3 첫 Collector + 실데이터 검증

```
LawCollector를 단계별로 구현.

Step 1: 가장 간단한 법령 1개(예: 행정절차법) 1개 조문만 가져오는 최소 코드.
Step 2: 실제 호출해서 응답 원본을 보여줘. 파싱은 아직 X.
Step 3: 응답 구조를 같이 보고 어떻게 파싱할지 결정.
Step 4: TARGET_LAWS 전체 수집 로직 확장.
Step 5: 단위 테스트 추가.

추측해서 한 번에 만들지 말 것. 응답 구조를 같이 보고 결정.
```

### 2.4 나머지 Collector

```
LawCollector 패턴이 검증되었으니 동일 구조로 나머지 3개:
- PrecCollector (target=prec)
- DetcCollector (target=detc)
- ExpcCollector (target=expc)

각 Collector마다:
1. 샘플 1개 호출 → 응답 보여주기 → 파싱 전략 합의
2. 본격 구현
3. 단위 테스트

3개 한 번에 보여주지 말고 하나씩 진행.
```

### 2.5 통합 수집 스크립트

```
scripts/collect_all.py 만들기.

요구사항:
- argparse 사용
- --target law|prec|detc|expc|all 옵션
- --resume 옵션
- 진행률 tqdm 또는 structlog
- 실패 항목 data/raw/_failed/{target}.jsonl

만들고 dry-run 모드로 동작 확인 후 출력 보여주기.
```

---

## 3. M2: 청킹/임베딩/인덱싱

### 3.1 데이터 모델

```
M2 시작. 우선 Pydantic 데이터 모델만 먼저.

ARCHITECTURE.md 메타데이터 스키마 그대로 반영:
- src/lawtutor/models/law.py - LawArticle 모델
- src/lawtutor/models/precedent.py - Precedent 모델
- src/lawtutor/models/decision.py - ConstitutionalDecision 모델
- src/lawtutor/models/interpretation.py - LegalInterpretation 모델
- src/lawtutor/models/search.py - SearchResult, SearchResponse (MCP 응답)

각 모델:
- pydantic v2
- 모든 필드 타입 힌트
- Field(..., description="...")
- Optional 명확히
- model_config로 extra="forbid"

작성 후 M1 raw 데이터 1개를 실제 파싱해서 모델에 담아보고 결과 보여주기.
```

### 3.2 청킹

```
청킹 전략은 이 프로젝트의 품질을 좌우한다. 신중히.

먼저 LawChunker 하나만 구현.

요구사항:
- ARCHITECTURE.md 6.1절 그대로
- 조 단위, 800자 초과 시 항 단위 분할
- 청크 텍스트 형식: "[법령명] 제○조 (제목)\n[본문]"
- 메타데이터 모든 필드 보존
- chunk_id: f"{law_id}_art{article_no}_{paragraph_no or 'full'}"

구현 후:
1. 행정절차법 1건 실제 청킹 결과 보여주기
2. 길이 분포 출력
3. 800자 임계값 적절성 같이 판단

테스트:
- 짧은 조: 1청크
- 긴 조: 항 단위 분할
- 메타데이터 보존
```

### 3.3 임베딩 + 벡터 스토어

```
임베딩과 Qdrant 인덱싱 구축.

순서:
1. src/lawtutor/embeddings/base.py - BaseEmbedder
2. src/lawtutor/embeddings/bge_m3.py - BGE-M3 (FlagEmbedding)
   - config.BGE_M3_DEVICE 우선 (cpu/cuda)
   - 디바이스 자동 감지 폴백
3. src/lawtutor/vector_store/client.py - Qdrant 래퍼
4. src/lawtutor/vector_store/schemas.py - 컬렉션 정의

각 단계마다 보여주고 검증.

벡터 스토어 메서드:
- create_collection(name, vector_size, payload_indices)
- upsert_chunks(collection_name, chunks)
- search(collection_name, query_vector, top_k, filters)
- collection_exists(name)
- recreate_collection(name)

작은 샘플로 end-to-end 동작 확인 후 보고.
첫 1건 임베딩 시간 측정해서 보고. (CPU 환경)
```

### 3.4 통합 인덱싱 스크립트

```
scripts/chunk_and_embed.py.

플로우:
1. data/parsed/ 에서 정형 데이터 로드
2. target별 chunker 적용
3. 임베딩 생성 (배치)
4. Qdrant upsert

옵션:
- --target all|law|prec|detc|expc
- --recreate
- --batch-size

진행률 + 통계 출력. 실제 한 번 돌려보고 결과 보여주기.
```

---

## 4. M3: MCP 서버

### 4.1 MCP SDK 사전 조사

```
MCP 서버 구현 전 사전 조사.

웹 검색으로:
1. mcp Python SDK 최신 버전과 설치 방법
2. FastMCP 사용법
3. Streamable HTTP transport 설정 (SSE는 deprecated)
4. FastAPI 통합 방식
5. Tool description 모범 사례
6. Bearer Token 인증 패턴

결과를 docs/mcp_reference.md 로 정리. 추측 금지.

OK 하면 검색 로직 → MCP 서버 순으로 구현.
```

### 4.2 검색 로직

```
MCP 도구가 사용할 검색 로직 먼저.

src/lawtutor/retrieval/retriever.py:
- Retriever 클래스
- 의존성: embedder, qdrant client
- 메서드:
  - search(collection, query, top_k, filters) -> list[Chunk]
  - fetch_by_metadata(collection, filter_dict) -> list[Chunk]
- 메타데이터 필터 빌더

src/lawtutor/retrieval/formatter.py:
- Qdrant raw 결과 → SearchResponse Pydantic
- 메타데이터 무결성 검증

구현 후 단위 테스트 (mock Qdrant client).
```

### 4.3 MCP 서버 골격

```
src/lawtutor/mcp_server/server.py 구현.

- FastMCP 인스턴스 생성
- 의존성 주입 패턴
- 도구 등록은 다음 단계

src/lawtutor/mcp_server/auth.py:
- Bearer Token 검증
- FastAPI Depends 형태

src/lawtutor/mcp_server/http_app.py:
- FastAPI 앱
- /health (인증 X)
- /mcp (인증 O, MCP 마운트)
- Rate limiting

scripts/run_server.py:
- uvicorn 실행

여기까지 만들고 curl로 /health 응답 확인.
```

### 4.4 도구 하나씩 구현

```
6개 도구 중 search_law 먼저.

src/lawtutor/mcp_server/tools/search_law.py:
- @mcp.tool 데코레이터
- 입력: PRD 4.1.1 그대로
- 출력: SearchResponse
- docstring: ARCHITECTURE.md 4.5절 형식

구현 후:
1. 단위 테스트
2. MCP Inspector(`npx @modelcontextprotocol/inspector`)로 호출 테스트
3. 실제 쿼리 3~5개 결과 확인

OK 받으면 fetch_article_by_number → search_precedent → search_decision → fetch_case → search_interpretation 순서.
```

### 4.5 로컬 E2E 테스트

```
모든 도구 구현 후 로컬 E2E.

scripts/run_server.py로 서버 띄우고:
1. MCP Inspector 도구 목록 정상 노출
2. 각 도구 호출 결과가 SearchResponse 형식
3. Bearer Token 잘못 입력 시 401
4. Rate limit 초과 시 429

샘플 시나리오 5개:
1. "행정절차법 제21조" → fetch_article_by_number
2. "처분의 사전통지 의무" → search_law
3. "대법원 2018두12345" → fetch_case_by_number
4. "공무원 직권면직 헌재" → search_constitutional_decision
5. "행정대집행 요건" → search_law
```

---

## 5. M4: 집 PC + Cloudflare Tunnel 배포

### 5.1 배포 사전 점검

```
배포 시작 전 점검:

1. 호스트 OS 확인 (Windows/Linux/WSL2). uname 또는 systeminfo로 확인.
2. Docker Desktop 또는 Docker Engine 정상 동작? (docker --version, docker run hello-world)
3. 도메인 준비됐는지 (Cloudflare에 추가됐는지)
4. Cloudflare Zero Trust 활성화됐는지

위 4가지 보고받은 후 진행.
```

### 5.2 Dockerfile

```
Dockerfile 작성.

요구사항:
- 베이스: python:3.11-slim
- 멀티 스테이지 빌드 (의존성 빌드 단계 + 런타임 단계)
- non-root 유저
- HEALTHCHECK 명령어 추가
- 이미지 크기 최소화

작성 후 로컬에서 빌드 테스트:
docker build -t lawtutor:test .

빌드 시간과 최종 이미지 크기 보고.
```

### 5.3 docker-compose.yml (3개 서비스)

```
DEPLOYMENT.md 5절 그대로 docker-compose.yml 작성.

세 서비스:
- qdrant: 외부 노출 X, 볼륨 ./qdrant_storage
- app: 외부 노출 X (cloudflared가 내부에서 접근)
- cloudflared: 명령어 'tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}'

추가:
- 모두 restart: unless-stopped
- 같은 네트워크(lawtutor-net)
- mem_limit으로 Qdrant 상한 (선택, 본인 작업 RAM 보호)

작성 후 docker compose config로 검증.
실제 기동은 사용자가 직접 (.env에 TUNNEL_TOKEN 입력 후).
```

### 5.4 Cloudflare Tunnel 셋업 가이드 검증

```
DEPLOYMENT.md 3절 (Cloudflare Tunnel 셋업) 절차를 사용자 입장에서 다시 검토.
누락된 단계나 오해할 수 있는 부분이 있는지 점검.

특히 다음 부분 명확한지 확인:
1. Public Hostname의 Service URL이 'app:8000'이라는 점 (localhost:8000 아님)
2. .env의 TUNNEL_TOKEN 형태 (eyJ로 시작)
3. 도메인 NS가 Cloudflare로 변경된 후에 작업해야 함

문제 발견 시 docs/DEPLOYMENT.md 수정 제안.
```

### 5.5 Windows 24/7 안정성 가이드

```
DEPLOYMENT.md 9절 (24/7 안정 운영 설정)을 더 상세히.

특히 Windows 사용자가 놓치기 쉬운:
1. 전원 옵션 (절전모드 비활성화) - 스크린샷 자리 명시
2. Wi-Fi 어댑터 절전
3. Windows Update 재부팅 통제
4. Docker Desktop 자동 시작

작성 후 사용자가 따라할 수 있게 체크리스트 형태로 보강.
```

### 5.6 Claude.ai 연결 사용자 가이드

```
README.md 또는 docs/USER_GUIDE.md에 사용자(여자친구분) 연결 가이드.

DEPLOYMENT.md 8절 내용을 사용자 친화적으로 재정리:
- 스크린샷 placeholder
- 토큰을 안전하게 받는 방법 안내
- 첫 사용 시 테스트 질문 예시

작성 후 보여주기.
```

---

## 6. M5: 평가

### 6.1 평가셋 빌더

```
평가셋 30~50개 작성 도구.

scripts/build_eval_set.py:
- 인터랙티브 CLI
- 한 문항씩 입력:
  · 질문
  · 카테고리
  · 난이도
  · 호출되어야 할 도구
  · 예상 조문 (콤마 구분)
  · 예상 사건번호 (콤마 구분)
- data/eval/eval_set_v1.jsonl append
- 중복 검사

이걸로 사용자(나)가 30개 만들 예정.
```

### 6.2 평가 메트릭과 러너

```
평가 메트릭 + 실행기.

src/lawtutor/evaluation/metrics.py:
- retrieval_recall_at_k
- mean_reciprocal_rank
- metadata_integrity_rate

scripts/run_eval.py:
- 평가셋 로드
- 각 항목 명시 도구 호출
- 메트릭 집계
- 결과 data/eval_results/{timestamp}.json
- 콘솔 markdown 표
- --compare-with PATH

먼저 5문항 dry-run 출력 검증.
```

---

## 7. 응급 대응 지시문

### 7.1 폭주 제어
```
잠깐, 그만. 한 번에 너무 많이 만들고 있어.
지금까지 만든 것 중에 X 모듈만 보여주고, 나머지는 보류.
내가 OK 한 다음에 진행해.
```

### 7.2 추측 차단
```
지금 추측해서 작성한 부분이 있어 보여.
실제 데이터/응답/문서를 보고 확정하지 않은 부분은 모두 표시하고, 검증 방법을 제안해줘.
특히 MCP SDK와 Cloudflare Tunnel 설정은 공식 문서 확인 필수.
```

### 7.3 LLM 호출 의심
```
이 프로젝트에서는 LLM API(Anthropic, OpenAI 등) 직접 호출이 금지야.
검색 결과만 반환하면 답변 생성은 Claude Pro가 한다.
LLM API 호출 코드 추가됐는지 점검하고 보고해.
```

### 7.4 Windows 호환성 의심
```
방금 추가한 코드/스크립트가 Windows에서도 동작하는지 확인:
1. 경로 처리: pathlib.Path 사용했는지 (os.path.join 또는 / 직접 사용 X)
2. 줄바꿈: 텍스트 파일 작성 시 newline 처리
3. shell 스크립트는 .sh와 .ps1 둘 다 제공
점검 후 보고.
```

### 7.5 라우터 포트포워딩 의심
```
docker-compose.yml에서 host 포트 바인딩이 추가됐는지 점검.
app 컨테이너의 ports: 항목이 있으면 안 됨 (cloudflared만 외부 통신).
DEPLOYMENT.md 0절 절대 원칙 위반 여부 확인.
```

### 7.6 보안 점검 (배포 전)
```
배포 전 보안 점검:
1. .env가 .gitignore에 포함됐는지
2. TUNNEL_TOKEN이 git history에 들어갔는지 (git log --all -p | findstr TUNNEL_TOKEN)
3. LAWTUTOR_API_TOKEN 32자 이상 랜덤인지
4. 라우터 포트포워딩 X (사용자 직접 확인)
5. CORS 설정이 적절한지
6. Rate limit 동작하는지
7. 로그에 토큰/PII 출력되지 않는지

각 항목 체크 후 보고.
```

### 7.7 큰 리팩터링 발견
```
지금 큰 변경을 단행하려고 하는데 사전 협의가 안 됐어.
변경 전 상태로 되돌리고, 어떤 변경을 왜 하려고 하는지 먼저 설명해.
```

---

## 8. 마일스톤 종료 점검

각 마일스톤 끝에:

```
M{n} 완료 점검.

다음 보고:
1. MILESTONES.md의 M{n} 완료 기준 항목별 체크
2. 추가된 의존성이 CLAUDE.md 2절과 일치하는지
3. Windows 호환성 (M{n}에서 추가된 부분)
4. 새로 만든 모듈에 docstring/타입힌트 다 있는지
5. 테스트 커버리지
6. data/, .env에 민감 정보 없는지
7. README/문서 업데이트 필요 항목

문제 없으면 git tag milestone-M{n}-complete.
```
