# MILESTONES - LawTutor MCP

## 진행 원칙

- 각 마일스톤은 **사용자 검증 통과 후** 다음으로 진행한다.
- 마일스톤 내부 작업도 반드시 작은 단위로 쪼개서 한 번에 한 모듈만 구현.
- 각 마일스톤 완료 시 GitHub 커밋(`milestone-Mn-complete` 태그) 생성.

---

## M0: 프로젝트 부트스트랩

### 목표
빈 디렉토리에서 시작해서 코드를 작성할 수 있는 상태까지 만든다.

### 작업
1. `pyproject.toml` 생성 (ARCHITECTURE.md 8절 의존성 반영)
2. `.gitignore`, `.gitattributes`, `.env.example` 생성
3. 디렉토리 골격 생성 (빈 `__init__.py` 포함)
4. `docker-compose.yml` 작성 (qdrant 서비스만 일단)
5. `src/lawtutor/config.py` 작성 (Settings 클래스)
6. `src/lawtutor/constants.py` 작성 (수집 대상 법령 리스트 등)
7. `README.md` 초안 작성
8. `git init` + 초기 커밋

### 사용자 결정 필요 사항
- 패키지 매니저 (uv 추천)
- 호스트 OS (Windows / Linux / WSL2)

### 완료 기준
- `uv sync` 후 `python -c "from lawtutor.config import settings; print(settings)"` 정상 동작
- `docker compose up -d qdrant` 로 Qdrant 실행 후 `localhost:6333` 응답
- Windows 호스트 시 줄바꿈 LF로 강제됐는지 .gitattributes 확인

---

## M1: 데이터 수집 파이프라인

### 목표
국가법령정보센터 OPEN API에서 데이터를 수집한다.

### 사전 작업 (사용자가 수행)
- 국가법령정보센터(open.law.go.kr) 회원가입
- OPEN API 사용 신청 (1~2일 승인 대기)
- 발급받은 OC 값을 `.env`에 입력

### 작업

**M1.1 API 클라이언트 베이스**
- `src/lawtutor/collectors/base.py`
- httpx 비동기 클라이언트 래퍼
- 인증 처리 (OC 파라미터 자동 주입)
- 재시도 로직 (tenacity)
- Rate limit 대응 (sleep)
- 응답 원본을 `data/raw/{target}/{date}/` 에 저장

**M1.2 법령 수집기**
- `src/lawtutor/collectors/law_collector.py`
- `lawSearch.do?target=law` 으로 목록 조회 (페이징)
- `lawService.do?target=law&MST=...` 로 본문 조회
- `constants.py`의 `TARGET_LAWS` 리스트만 수집

**M1.3 판례 수집기**
- `src/lawtutor/collectors/prec_collector.py`
- `target=prec` 사용
- 검색 키워드는 행정법 핵심 용어 리스트 사용

**M1.4 헌재결정례 수집기**
- `src/lawtutor/collectors/detc_collector.py`
- `target=detc` 사용

**M1.5 법령해석례 수집기**
- `src/lawtutor/collectors/expc_collector.py`
- `target=expc` 사용

**M1.6 통합 실행 스크립트**
- `scripts/collect_all.py`
- CLI 인자로 어느 collector를 돌릴지 선택
- 진행 로그 + 실패 항목 retry queue

### Claude Code에 명시할 주의사항
- API 응답 구조를 모르면 추측 금지. 작은 샘플 1개만 먼저 수집해서 사용자에게 보여주고 스키마 결정.
- 응답이 XML이면 `xml.etree.ElementTree` 또는 `lxml` 사용 (사용자 승인)
- 인코딩 이슈 주의 (응답이 EUC-KR일 가능성 확인)

### 완료 기준
- `data/raw/law/`, `data/raw/prec/`, `data/raw/detc/`, `data/raw/expc/` 에 데이터 채워짐
- 핵심 법령 10개+ 수집 완료
- 각 collector의 단위 테스트 (mock 사용) 통과

---

## M2: 파싱, 청킹, 임베딩, 인덱싱

### 목표
원본 데이터를 정형화하고 청크 단위로 Qdrant에 인덱싱한다.

### 작업

**M2.1 Pydantic 데이터 모델**
- `src/lawtutor/models/{law,precedent,decision,interpretation}.py`
- ARCHITECTURE.md 메타데이터 필드 모두 표현
- `src/lawtutor/models/search.py` 에 MCP 응답 모델 정의
- 직렬화/역직렬화 테스트 포함

**M2.2 Parser**
- `src/lawtutor/parsers/{각각}.py`
- 원본 XML/JSON → Pydantic 모델
- `data/parsed/{target}/*.json` 으로 저장

**M2.3 Chunker**
- `src/lawtutor/chunking/law_chunker.py`
  - 조 단위 분할
  - 길이 임계값 초과 시 항 단위 분할
- `src/lawtutor/chunking/prec_chunker.py`
  - 판시사항/판결요지/이유 섹션 분할
- 청크 모델: `chunk_models.py`에 `Chunk` Pydantic 클래스

**M2.4 Embedder**
- `src/lawtutor/embeddings/base.py` 추상 인터페이스
- `src/lawtutor/embeddings/bge_m3.py` 구현
- CPU/GPU 자동 감지 (config.BGE_M3_DEVICE 우선)
- 배치 처리

**M2.5 Vector Store**
- `src/lawtutor/vector_store/client.py`
- Qdrant 클라이언트 초기화
- 컬렉션 생성/재생성 메서드
- payload index 등록
- upsert/search 래퍼

**M2.6 인덱싱 스크립트**
- `scripts/chunk_and_embed.py`
- parsed 데이터 읽음 → 청킹 → 임베딩 → upsert
- 컬렉션별로 분리 처리
- 진행률 표시

### 사용자 결정 필요 사항
- 청킹 임계값
- 컬렉션 리셋 전략
- GPU 사용 여부 (있다면 CUDA, 없으면 CPU)

### 완료 기준
- 4개 컬렉션이 Qdrant에 생성됨
- 법령 청크 1000개+, 판례 청크 500개+ 인덱싱
- 임의 키워드로 search 호출 시 관련 결과 반환

---

## M3: MCP 서버 핵심 기능

### 목표
공식 MCP Python SDK를 사용해 6개 도구를 제공하는 MCP 서버 구현.

### 사전 조사
- 최신 `mcp` Python SDK 버전 확인
- Streamable HTTP transport 사용법
- FastAPI 통합 방식
- Tool description 모범 사례

### 작업

**M3.1 검색 로직 (Retriever)**
- `src/lawtutor/retrieval/retriever.py`
- 쿼리 → 임베딩 → Qdrant 검색 → Pydantic 모델 변환
- 컬렉션별 필터링 로직

**M3.2 응답 포매터**
- `src/lawtutor/retrieval/formatter.py`
- Qdrant 검색 결과 → MCP SearchResponse 형식
- 메타데이터 무결성 검증

**M3.3 MCP 서버 골격**
- `src/lawtutor/mcp_server/server.py`
- FastMCP 인스턴스 생성
- 의존성 주입

**M3.4 6개 도구 구현 (한 번에 하나씩)**
순서:
1. `tools/search_law.py`
2. `tools/fetch_article.py`
3. `tools/search_precedent.py`
4. `tools/search_decision.py`
5. `tools/fetch_case.py`
6. `tools/search_interpretation.py`

**M3.5 Bearer Token 인증**
- `src/lawtutor/mcp_server/auth.py`
- FastAPI dependency
- 토큰 검증 + 401 처리

**M3.6 FastAPI 통합**
- `src/lawtutor/mcp_server/http_app.py`
- /health 엔드포인트 (인증 불필요)
- /mcp 엔드포인트 (인증 필요, MCP 마운트)
- Rate limiting

**M3.7 로컬 개발용 실행 스크립트**
- `scripts/run_server.py`

### 완료 기준
- `python scripts/run_server.py` 로 로컬 서버 실행
- `curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/health` 200
- MCP Inspector로 6개 도구 모두 호출 성공
- 단위 테스트 + E2E 테스트 통과

---

## M4: 배포 (집 PC + Cloudflare Tunnel)

### 목표
승의 집 데스크탑에 Docker로 배포하고, Cloudflare Tunnel을 통해 Claude.ai에서 접근 가능한 상태로 만든다.

### 사전 작업 (사용자가 수행)
- 도메인 준비 (Cloudflare Registrar 권장, 연 약 14,000원)
- Cloudflare 계정 생성 + 도메인을 Cloudflare에 추가
- Cloudflare Zero Trust 활성화 (Free plan)
- Docker Desktop 설치 (Windows) 또는 Docker Engine 설치 (Linux)

### 작업

**M4.1 Dockerfile**
- 베이스: `python:3.11-slim`
- 멀티 스테이지 빌드
- non-root 유저
- HEALTHCHECK 명령 추가
- Windows/Linux 어디서 빌드해도 동작

**M4.2 docker-compose.yml (3개 서비스)**
- `qdrant`: 외부 노출 X
- `app`: 외부 노출 X (cloudflared가 내부에서 접근)
- `cloudflared`: 아웃바운드 only
- `restart: unless-stopped` 모두 설정
- DEPLOYMENT.md 5절 그대로

**M4.3 Cloudflare Tunnel 설정 (사용자 수행 + 가이드 작성)**
- DEPLOYMENT.md 3절 절차 검증
- Tunnel 생성 → 토큰 발급 → .env에 저장
- Public Hostname 설정 (lawtutor.{도메인} → app:8000)
- 동작 확인

**M4.4 .env 파일 템플릿 정비**
- `.env.example`에 모든 변수 명시
- 토큰 형식 코멘트
- 절대 git 커밋 X 명시

**M4.5 24/7 안정성 가이드 작성**
- DEPLOYMENT.md 9절 (Windows 전원 옵션, Wi-Fi 절전 비활성화 등)
- 사용자가 직접 확인하도록 체크리스트 제공

**M4.6 헬스체크 모니터링 (선택)**
- UptimeRobot 등 외부 서비스 연동
- /health 엔드포인트 응답 5분 간격 확인

**M4.7 Claude.ai 연결 가이드**
- README.md 또는 docs/USER_GUIDE.md
- 사용자가 따라할 수 있는 단계별 스크린샷 자리(placeholder)

### 사용자 결정 필요 사항
- 도메인 등록업체 (Cloudflare Registrar / 가비아 / 후이즈 등)
- Cloudflare Access 추가 적용 여부 (선택, 권장)

### 완료 기준
- 외부에서 `curl https://lawtutor.{도메인}/health` 200 응답
- Claude.ai에서 Custom Connector 등록 성공
- 다른 계정에서도 같은 URL/Token으로 등록 후 사용 가능
- PC 재부팅 후 자동 복구 검증 (실제 재부팅 테스트)
- 인터넷 일시 단절 후 cloudflared 재연결 검증
- 본인 작업 시 RAM/CPU 충돌 없는지 확인

---

## M5: 평가셋 + 성능 측정

### 목표
정량 평가가 가능한 상태. 본 시스템은 LLM이 없으므로 **검색 정확도 위주로 평가**.

### 작업

**M5.1 평가셋 구축**
- `data/eval/eval_set_v1.jsonl`
- 30~50문항
- 7급 기출 기반으로 사용자가 작성

**M5.2 평가 메트릭**
- `src/lawtutor/evaluation/metrics.py`
- Retrieval recall@k
- MRR
- 메타데이터 무결성 비율

**M5.3 평가 실행기**
- `scripts/run_eval.py`
- 평가셋 로드 → 도구 호출 → 메트릭 집계 → 리포트
- 결과 `data/eval_results/{timestamp}.json`

**M5.4 (선택) 실사용 로그 분석**
- 사용자 질문 + 호출된 도구 + 검색 결과 로깅
- 빈약한 결과를 받는 질문 분석

### 완료 기준
- 자동 평가 파이프라인 1줄 실행 가능
- 첫 평가 결과: PRD 5.2절 목표치(recall@5 80%) 도달 또는 미달 사유 분석

---

## 우선순위와 일정 가이드

### 절대 우선
M0 → M1 → M2 → M3 → M4

### 시간 안배 (참고용, 주말 파트타임 기준)
- M0: 1~2일
- M1: 1주
- M2: 1~2주
- M3: 1주
- M4: 3~5일 (Cloudflare Tunnel 셋업 + 안정성 검증)
- M5: 3~5일

총 4~6주 예상.

### 단축 경로 (포트폴리오 우선)
M0 → M1 → M2 → M3 까지만 만들고 로컬 데모 수준으로 마무리.
M4(배포)는 실사용 결정 후 진행.
이 시점까지만 해도 "MCP 서버 + 도메인 특화 RAG" 포트폴리오로 충분.

---

## 차별 포인트 (포트폴리오 어필용)

기존 RAG 프로젝트(AYNIG)와 차별화:

1. **MCP 서버 구축** — 2024~2025년 새로 표준화된 영역, 경험자 적음
2. **도메인 특화 청킹** — 법령(조 단위), 판례(섹션 단위) 별도 설계
3. **시행일자 기반 현행 법령 필터링** — 단순 RAG가 아닌 도메인 지식 반영
4. **Cloudflare Tunnel + 집 PC 셀프 호스팅** — 비용/보안 트레이드오프 사고
5. **검색만 제공, 추론은 클라이언트에 위임** — 책임 분리 설계
