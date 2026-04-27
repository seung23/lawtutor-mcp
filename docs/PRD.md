# PRD - LawTutor MCP

## 1. 문제 정의

### 1.1 현황
한국 7급 공무원시험(행정직) 응시자가 행정법/헌법 학습 중 범용 LLM(Claude, ChatGPT 등)에 법령/판례 관련 질문을 하면 다음과 같은 할루시네이션이 자주 발생한다:

- 존재하지 않는 조문번호 생성 (예: 행정절차법 제30조의5)
- 존재하지 않는 사건번호 생성 (예: 대법원 2019. 5. 14. 선고 2018두12345 판결)
- 실재하는 사건번호에 잘못된 판시사항 매칭
- 폐지/개정된 조문을 현행으로 답변
- 헌재결정례를 대법원 판례로 혼동

학습자가 이를 신뢰하면 잘못된 지식이 굳어져 시험에서 감점 요인이 된다.

### 1.2 해결 방향
1차 출처(국가법령정보센터)의 원문 데이터를 RAG로 인덱싱하고, **MCP(Model Context Protocol) 서버**로 제공한다. 사용자가 Claude Pro에서 이 MCP 서버를 Custom Connector로 추가하면, Claude가 질문을 받았을 때 자동으로 본 서버의 검색 도구를 호출해서 1차 출처에 근거한 답변을 생성한다.

### 1.3 왜 MCP인가
- **비용**: Claude Pro 정액제($20/월) 안에서 LLM 추론 처리. API 토큰 비용 0원.
- **분리**: 검색은 본 서버, 추론은 Claude Pro. 각자 잘하는 일에 집중.
- **확장성**: 다른 MCP 호환 클라이언트(Claude Desktop, Cursor, Cline 등)에서도 동일하게 사용 가능.

---

## 2. 타겟 사용자

- **주 사용자**: 7급 공무원시험(행정직) 수험생 1명 (개인 프로젝트)
- **시험 과목 범위**: 행정법총론, 헌법
- **사용자 환경**: Claude Pro 구독자
- **예상 사용 패턴**:
  - 기본서를 보다가 모르는 개념/판례 질문
  - 기출 문제 풀이 후 해설 보강
  - 특정 조문에 대한 사례형 적용 질문
  - 판례 비교/구분 질문 ("X판례와 Y판례의 차이는?")

---

## 3. 데이터 요구사항

### 3.1 데이터 소스
**국가법령정보센터 OPEN API (open.law.go.kr) 단일 소스 사용.**
다른 사이트(케이스노트 등) 크롤링은 이용약관 위반으로 사용 금지.

API 엔드포인트:
- `lawSearch.do` - 목록 조회
- `lawService.do` - 본문 조회
- 인증: 발급받은 OC(이메일 ID)를 쿼리 파라미터로 전달

### 3.2 수집 대상

**행정법 (target=law)**
- 행정기본법
- 행정절차법
- 행정심판법
- 행정소송법
- 국가배상법
- 공공기관의 정보공개에 관한 법률
- 행정대집행법
- 질서위반행위규제법
- 정부조직법 (관련 부분)
- 각 법의 시행령, 시행규칙

**헌법 (target=law)**
- 대한민국헌법

**판례 (target=prec)**
- 위 법령들과 연관된 대법원 판례
- 7급 시험 빈출 판례 (수험서 기준 핵심 판례 우선)
- 최근 10년 이내 판례 우선, 그 이전이라도 시험 핵심 판례는 포함

**헌법재판소 결정례 (target=detc)**
- 헌법 학습용 주요 결정례
- 기본권 챕터별 핵심 결정

**법령해석례 (target=expc)**
- 정부 부처(법제처) 유권해석
- 7급 시험 출제 가능성 있는 행정법 해석례

### 3.3 메타데이터 스키마

**법령(Law) 메타데이터**
- `law_id`: 국가법령정보센터 법령ID
- `law_name`: 법령명
- `article_no`: 조문번호 (예: "30", "30의2")
- `paragraph_no`: 항 번호 (예: "1", "2")
- `subparagraph_no`: 호 번호 (예: "1")
- `effective_date`: 시행일자 (YYYY-MM-DD)
- `promulgation_date`: 공포일자
- `promulgation_no`: 공포번호
- `is_active`: 현행 여부 (Boolean)
- `ministry`: 소관부처
- `revision_history`: 개정 이력 요약

**판례(Precedent) 메타데이터**
- `case_id`: 판례일련번호
- `case_no`: 사건번호 (예: "2018두12345")
- `case_name`: 사건명
- `court`: 법원 (예: "대법원")
- `judgment_date`: 선고일자
- `judgment_type`: 판결/결정 구분
- `referenced_articles`: 참조조문 목록
- `referenced_cases`: 참조판례 목록
- `holding`: 판시사항
- `summary`: 판결요지
- `reasoning`: 이유

**헌재결정례 메타데이터**
- `decision_id`: 결정일련번호
- `case_no`: 사건번호 (예: "2018헌마123")
- `case_name`: 사건명
- `decision_date`: 선고일자
- `decision_type`: 결정 유형 (위헌, 합헌, 헌법불합치 등)
- `referenced_articles`: 참조조문
- `holding`: 결정요지
- `reasoning`: 이유

**법령해석례 메타데이터**
- `interpretation_id`: 해석례번호
- `title`: 안건명
- `interpretation_date`: 회신일자
- `requesting_agency`: 질의기관
- `referenced_law`: 관련 법령
- `summary`: 해석 요지

---

## 4. MCP 서버 기능 요구사항

### 4.1 제공할 MCP Tools

**4.1.1 search_law**
- 설명: 한국 행정법/헌법 법령의 조문을 검색한다. 사용자가 특정 조문, 법령 개념, 사례형 적용 질문을 할 때 호출.
- 입력:
  - `query: str` - 검색 쿼리
  - `top_k: int = 5` - 반환할 결과 수
  - `law_name_filter: str | None = None` - 특정 법령으로 한정
  - `include_historical: bool = False` - 폐지/개정 조문 포함 여부
- 출력: 청크 목록. 각 청크는 본문 + 모든 메타데이터.

**4.1.2 search_precedent**
- 설명: 한국 행정법 관련 대법원 판례를 검색한다. 판례 질문, 판례 비교, 사례 적용 질문에 사용.
- 입력:
  - `query: str`
  - `top_k: int = 5`
  - `referenced_law: str | None = None` - 관련 법령으로 한정
  - `date_from: str | None = None` - 선고일자 하한 (YYYY-MM-DD)
- 출력: 판례 청크 목록. 사건번호 + 판시사항/판결요지/이유 + 메타데이터.

**4.1.3 search_constitutional_decision**
- 설명: 헌법재판소 결정례를 검색한다. 헌법 질문, 기본권 사건, 위헌 여부 질문에 사용.
- 입력:
  - `query: str`
  - `top_k: int = 5`
  - `decision_type_filter: list[str] | None = None` - "위헌", "합헌" 등으로 한정
- 출력: 결정례 청크 목록.

**4.1.4 search_legal_interpretation**
- 설명: 정부 부처(법제처)의 법령 유권해석례를 검색한다. 행정 실무 해석, 법령 적용 모호한 영역 질문에 사용.
- 입력:
  - `query: str`
  - `top_k: int = 5`
- 출력: 해석례 청크 목록.

**4.1.5 fetch_article_by_number**
- 설명: 법령명과 조문번호로 정확한 조문을 직접 조회한다. 사용자가 조문번호를 알고 있을 때 사용.
- 입력:
  - `law_name: str` (예: "행정절차법")
  - `article_no: str` (예: "21")
  - `paragraph_no: str | None = None`
- 출력: 단일 조문 또는 빈 결과.

**4.1.6 fetch_case_by_number**
- 설명: 사건번호로 정확한 판례/결정례를 직접 조회한다.
- 입력:
  - `case_no: str` (예: "2018두12345" 또는 "2018헌마123")
- 출력: 단일 판례/결정례 또는 빈 결과.

### 4.2 응답 형식

모든 도구의 응답은 동일한 구조를 따른다:

```json
{
  "results": [
    {
      "content": "조문 또는 판례 본문 텍스트",
      "metadata": {
        "source_type": "law" | "precedent" | "decision" | "interpretation",
        "law_name": "...",
        "article_no": "...",
        "case_no": "...",
        "effective_date": "...",
        "is_active": true,
        ...
      },
      "score": 0.87
    }
  ],
  "query": "원본 쿼리",
  "total_found": 10,
  "search_metadata": {
    "collections_searched": ["laws"],
    "filters_applied": {"is_active": true},
    "search_time_ms": 123
  }
}
```

### 4.3 인증 및 보안
- 초기 버전: HTTP Bearer Token 인증
- 향후 (선택): Cloudflare Access (Zero Trust) 추가 적용. 무료 50명까지 OAuth/SSO/이메일 OTP.
- HTTPS는 Cloudflare Edge에서 자동 종단 (자체 인증서 관리 불필요)
- Rate limiting: 분당 60 요청

### 4.4 필요 없는 기능 (범위 외)
- LLM 호출 (Claude API 등) — Claude Pro가 처리
- 답변 생성 — Claude Pro가 처리
- 정규식 환각 검증 — 검색 결과만 정확하게 반환하면 충분
- 채팅 UI — Claude.ai 본체가 UI

---

## 5. 비기능 요구사항

### 5.1 성능
- 단일 검색 응답 시간: 평균 500ms 이내, p95 1초 이내 (Cloudflare 엣지 추가 지연 포함)
- 동시 사용자: 1~3명
- 임베딩 인덱스 갱신: 주 1회 또는 사용자 수동 트리거

### 5.2 정확성 (자체 평가셋 기준)
- Retrieval recall@5: 80% 이상
- 응답에 포함된 메타데이터 무결성 100% (메타데이터가 빠지거나 잘못된 케이스 0건)

### 5.3 운영
- 사용자(승) 본인 집 데스크탑 PC에서 24/7 실행
- Cloudflare Tunnel을 통해 `https://{서브도메인}/{도메인}` 으로 외부 노출
- HTTPS endpoint로 외부에서 접근
- 헬스체크 엔드포인트 (`/health`) 제공
- API 호출 비용 추적 불필요 (LLM API 안 쓰니까)

---

## 6. 사용자 시나리오 (E2E)

### 6.1 초기 설정 (1회)
1. 사용자(여자친구분)가 Claude.ai 접속
2. Settings → Connectors → "Add custom connector"
3. URL 입력: `https://lawtutor.{도메인}/mcp`
4. Bearer Token 입력 (승님이 발급)
5. 저장

### 6.2 일상 사용
1. 사용자가 Claude.ai에서 "+" → Connectors → LawTutor 토글 ON
2. 자연어로 질문 입력 (예: "행정절차법상 처분의 사전통지 의무 알려줘")
3. Claude Pro가 자동으로 `search_law(query="처분의 사전통지", ...)` 호출
4. 본 서버가 Qdrant 검색 후 청크 반환
5. Claude Pro가 검색 결과를 바탕으로 답변 생성
6. 사용자에게 답변 + 출처 표시

### 6.3 답변 형식 (Claude Pro 측 책임이지만 가이드)
사용자가 시스템 프롬프트로 다음 형식을 강제할 수 있다:
```
## 핵심 답변
## 근거 법령 (search_law 결과)
## 관련 판례 (search_precedent 결과)
## 시험 출제 포인트
```

---

## 7. 범위 외 (v1에서 다루지 않음)

- 사용자 인증/계정 시스템 (단일 사용자 가정)
- 다중 토큰 발급/관리 UI
- 채점/문제 풀이 모드
- 음성 입력/출력
- 모바일 앱
- 실시간 법령 개정 자동 추적 (수동 갱신만)
- 행정직 외 직군의 법률 (민법, 형법 등)
- 영어 질문 응답
- 자체 LLM 호출 / 자체 답변 생성

---

## 8. 성공 기준

다음을 모두 만족하면 v1 완료로 간주:

1. 사용자(승) 집 PC에 배포되어 Cloudflare Tunnel을 통해 HTTPS로 접근 가능
2. 여자친구분이 본인 Claude Pro에서 Custom Connector로 추가 성공
3. Claude.ai에서 행정법 질문 시 본 서버의 도구가 자동 호출됨
4. 자체 평가셋 30문항에서 retrieval recall@5 80% 이상
5. 검색 결과 메타데이터 무결성 100%
6. 평균 검색 응답 시간 500ms 이내
7. PC 재부팅/인터넷 단절 후 자동 복구 동작 검증
8. README 및 문서가 정리되어 GitHub 포트폴리오로 제출 가능
