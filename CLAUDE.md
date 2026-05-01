# LawTutor MCP - 한국 7급 공무원시험 행정법/헌법 학습 RAG MCP 서버

이 문서는 모든 작업 세션의 시작 시점에 자동으로 컨텍스트로 로드된다.
Claude Code는 이 문서의 규칙을 절대 어기지 말 것.

---

## 1. 프로젝트 목표

한국 7급 공무원시험(행정직) 응시자를 위한 행정법/헌법 RAG 도구를 **MCP(Model Context Protocol) 서버**로 제공한다. 사용자는 본인의 Claude Pro 구독을 통해 이 MCP 서버에 연결해서 사용한다.

### 1.1 왜 MCP 서버인가
- LLM 추론은 Claude Pro가 담당하므로 별도 LLM API 비용이 발생하지 않는다.
- 본 서버는 **검색 도구**만 제공. 답변 생성은 Claude Pro 본체가 처리한다.
- 사용자는 Claude.ai에서 Custom Connector로 추가하기만 하면 사용 가능.

### 1.2 차별점
- 검색된 1차 출처(국가법령정보센터)에 근거한 RAG로 범용 LLM의 할루시네이션 차단
- 시행일자 메타데이터 기반 현행 법령 우선 반환
- 인용 정확성 검증을 검색 결과 단계에서 보장

### 1.3 배포 환경
- 사용자(승) 본인의 **집 데스크탑**에서 24/7 구동
- **Cloudflare Tunnel**을 통해 외부 노출 (포트포워딩/공인 IP 불필요)
- HTTPS, DDoS 보호, WAF 자동 (Cloudflare 무료 제공)
- 운영 비용: 도메인비(연 1만원대) + 전기세 외 0원

---

## 2. 기술 스택 (변경 시 사용자 사전 승인 필수)

- **언어/런타임**: Python 3.11+
- **MCP SDK**: `mcp` (공식 Python SDK) 또는 `fastmcp`
- **웹 프레임워크**: FastAPI + uvicorn (Streamable HTTP transport 지원)
- **벡터 DB**: Qdrant (Docker 컨테이너)
- **임베딩 모델**: BGE-M3 (한국어 성능 우수). CPU 또는 GPU(있다면) 모두 지원
- **데이터 소스**: 국가법령정보센터 OPEN API (`open.law.go.kr`) **단일 소스**
- **데이터 검증**: Pydantic v2
- **HTTP 클라이언트**: httpx (비동기 지원)
- **테스트**: pytest, pytest-asyncio
- **포매터/린터**: ruff, black
- **환경 변수**: pydantic-settings (`.env` 파일 사용)
- **배포**:
  - 호스트 OS: Windows 10/11 또는 Linux (사용자 PC에 따름. 1순위 Windows + WSL2, 차선 네이티브 Linux)
  - 컨테이너: Docker Desktop (Windows) 또는 Docker Engine (Linux)
  - 외부 노출: Cloudflare Tunnel (cloudflared)
  - HTTPS 종단: Cloudflare Edge (TLS 인증서 발급/갱신 자동)

위에 없는 라이브러리 추가는 반드시 사용자에게 사유와 함께 승인 요청할 것.

---

## 3. 절대 원칙 (위반 시 즉시 중단)

### 3.1 데이터 수집 원칙
- 케이스노트(casenote.kr) 등 외부 사이트 크롤링 금지. 이용약관 위반 및 데이터베이스권 침해 리스크.
- 모든 법령/판례/헌재결정례/법령해석례 데이터는 국가법령정보센터 OPEN API에서만 수집.
- API 응답 원본(XML/JSON)을 절대 버리지 말고 `data/raw/` 디렉토리에 보존. 파싱은 별도 단계에서 수행.

### 3.2 MCP 서버 응답 원칙
- 본 서버는 LLM이 아니다. **답변을 생성하지 않는다.**
- 검색 결과를 구조화된 형태로 반환만 한다 (조문, 판례, 결정례 원문 + 메타데이터).
- 클라이언트(Claude Pro 등)가 검색 결과를 받아 답변을 생성하도록 한다.
- 검색 결과에는 **출처 메타데이터를 빠짐없이 포함**한다 (법령명, 조문번호, 시행일, 사건번호 등).

### 3.3 시행일자 처리 원칙
- 한국 법령은 개정이 잦다. 청크 메타데이터에 `effective_date`(시행일), `promulgation_date`(공포일), `is_active`(현행 여부) 필드를 반드시 포함.
- 검색 시 기본 필터로 `is_active=True`를 적용. 도구 인자로 `include_historical=True` 옵션 제공.

### 3.4 보안
- API 키, 인증 정보를 코드/커밋에 절대 포함하지 말 것. `.env` 사용.
- `.gitignore`에 `.env`, `data/raw/`, `data/parsed/`, `qdrant_storage/`, `cloudflared/cert.pem`, `cloudflared/*.json` 포함.
- MCP 서버는 **Cloudflare Tunnel을 통해서만 외부 노출**. 직접 포트 개방 금지 (라우터 포트포워딩 금지).
- Cloudflare Access(Zero Trust)로 추가 보호 권장 (선택, 무료 50명까지).
- 인증: 단순 Bearer Token. 토큰은 32바이트 이상 랜덤.

### 3.5 24/7 운영을 고려한 안정성
- 본 서비스는 **집 PC**에서 동작한다. 다음 상황에 견뎌야 한다:
  - 인터넷 일시 단절 → cloudflared 자동 재연결
  - PC 재부팅 → Docker Desktop 자동 시작 + 컨테이너 자동 복구
  - 절전모드 진입 방지 (Windows 전원 옵션 조정 가이드 제공)
- 헬스체크 엔드포인트(`/health`)로 외부 모니터링 가능.

---

## 4. 코드 작성 규칙

- 모든 함수/메서드에 타입 힌트 필수.
- 모든 public 함수/클래스에 docstring 필수 (한국어 OK, 영어 OK).
- 데이터 모델은 dict가 아닌 Pydantic 모델로 정의.
- 변수/함수명은 영어. 주석/docstring은 한국어 또는 영어.
- 환경 변수 접근은 `os.getenv` 직접 호출이 아닌 `config.py`의 Settings 클래스 경유.
- 비동기 가능한 I/O(API 호출, DB 쿼리)는 async/await 사용.
- 매직 넘버 금지. 모든 상수는 `constants.py` 또는 `config.py`에 정의.
- MCP tool 정의 시 description은 LLM이 도구를 잘 선택할 수 있게 명확하게 작성.
- 호스트 OS가 Windows일 가능성을 항상 고려: 경로 처리는 `pathlib.Path`, 줄바꿈은 LF 강제 (.gitattributes).

---

## 5. 작업 진행 방식 (가장 중요)

이 프로젝트는 한 번에 다 짜는 프로젝트가 아니다. 다음 사이클을 엄격히 지킬 것.

1. **계획 보고**: 새 작업 요청 시 즉시 코드 작성 금지. 먼저 다음을 보고한다.
   - 무엇을 만들 것인지
   - 어떤 파일을 어떤 순서로 만들지
   - 사용자가 결정해야 할 사항(라이브러리 선택, 스키마 결정 등)
   - 예상 리스크
2. **사용자 승인 대기**: 사용자가 "OK" 또는 수정 지시를 줄 때까지 대기.
3. **작은 단위 구현**: 한 번에 한 모듈만. 큰 변경을 한 커밋에 몰지 말 것.
4. **구현 후 검토 요청**: 모듈 단위로 사용자에게 보여주고 피드백 받은 뒤 다음 단계로.
5. **테스트 동반 작성**: 새 모듈은 가능하면 같은 PR/커밋에 pytest 테스트 포함.

---

## 6. 절대 하지 말 것

- 법령 텍스트, 판례 텍스트를 코드에 하드코딩하기 (반드시 API 통해 수집)
- 사용자 승인 없이 외부 라이브러리 추가
- API 응답 원본 폐기
- 큰 리팩토링을 사전 협의 없이 단행
- MCP 서버 안에서 LLM 호출하기 (Claude API, OpenAI API 등 절대 X — Claude Pro의 역할)
- "대략 이런 식이면 될 것 같다"는 추측성 코드 (불확실하면 사용자에게 질문)
- 라우터 포트포워딩으로 외부 노출 (Cloudflare Tunnel만 사용)
- 무인증으로 MCP 서버 외부 노출
- Cloudflare Tunnel 토큰을 git에 커밋

---

## 7. 참고 문서

상세 사양은 다음을 참조:
- `docs/PRD.md` - 제품 요구사항 (무엇을 만드는가)
- `docs/ARCHITECTURE.md` - 시스템 아키텍처 (어떻게 만드는가)
- `docs/MILESTONES.md` - 단계별 작업 계획 (언제 무엇을 만드는가)
- `docs/DEPLOYMENT.md` - 집 PC + Cloudflare Tunnel 배포 가이드
- `docs/PROMPTING.md` - Claude Code 작업 시 사용자가 사용할 지시문 패턴
