# DEPLOYMENT - 집 PC + Cloudflare Tunnel 배포 가이드

## 0. 개요와 핵심 원칙

본 문서는 LawTutor MCP 서버를 **승의 집 데스크탑 PC**에 배포하고 **Cloudflare Tunnel**을 통해 외부에 안전하게 노출하는 절차를 다룬다.

### 0.1 절대 원칙

- ❌ **라우터 포트포워딩 금지** (집 네트워크 노출 위험)
- ❌ **공유기 DMZ 금지**
- ❌ Cloudflare Tunnel 토큰을 git에 커밋 금지
- ❌ Bearer Token을 .env 외부에 저장 금지
- ✅ 모든 외부 접근은 Cloudflare Tunnel 단일 경로

### 0.2 비용 요약

| 항목 | 비용 | 비고 |
|---|---|---|
| Cloudflare Tunnel | 0원 | 무료 |
| Cloudflare DNS | 0원 | 무료 |
| HTTPS 인증서 | 0원 | Cloudflare가 발급 |
| 도메인 | 연 12,000~14,000원 | Cloudflare Registrar 또는 다른 등록업체 |
| 전기세 추가분 | 월 5,000~10,000원 | PC 24/7 가동 |
| **합계** | **월 약 6,000~11,000원** | |

---

## 1. 사전 준비

### 1.1 하드웨어/OS 확인

체크리스트:
- [ ] 데스크탑 PC (랩탑은 비추, 발열/배터리 이슈)
- [ ] RAM 16GB 이상 권장 (LawTutor가 6GB 사용, 본인 작업 여유분)
- [ ] 저장공간 30GB 이상 여유
- [ ] 인터넷 회선 안정적 (가정용 광랜 OK)
- [ ] OS: Windows 10/11 또는 Linux

### 1.2 도메인 준비

도메인은 무조건 필요하다. `*.trycloudflare.com` 임시 URL은 재시작 시 바뀌므로 실용성 X.

옵션:
- **A. Cloudflare Registrar**: 마진 없이 판매. .com 연 약 $10. 한 번에 NS 설정까지 됨.
- **B. 다른 등록업체에서 구매 후 Cloudflare로 NS 이전**: 가비아, 후이즈, 카페24 등에서 구매 후 NS만 Cloudflare로 변경.

추천: **Cloudflare Registrar**가 가장 간단함.

### 1.3 Cloudflare 계정

- https://dash.cloudflare.com 회원가입 (무료)
- 도메인을 Cloudflare에 추가 (Free plan)
- DNS가 Cloudflare를 통과하는지 확인 (보통 NS 변경 후 24시간 이내 활성화)

---

## 2. Docker Desktop 설치 (Windows 기준)

### 2.1 Docker Desktop 설치

1. https://www.docker.com/products/docker-desktop 접속
2. Windows용 다운로드 → 설치
3. 설치 중 "Use WSL 2 instead of Hyper-V" 체크 (권장)
4. 설치 완료 후 재부팅
5. Docker Desktop 실행 → 회원가입(선택) 또는 Skip
6. 작업 표시줄에 고래 아이콘이 떠야 함

### 2.2 동작 확인
PowerShell 또는 Command Prompt에서:
```powershell
docker --version
docker run --rm hello-world
```

`Hello from Docker!` 메시지가 보이면 OK.

### 2.3 Docker Desktop 자동 시작 설정

Docker Desktop → Settings → General → "Start Docker Desktop when you sign in" 체크.

이렇게 하면 PC 재부팅 후 자동으로 Docker가 시작됨.

### 2.4 (선택) WSL2 환경 활용

승님이 WSL2(Ubuntu 등)을 이미 쓰고 계시면, 그 환경에서 작업하시는 게 Linux와 동일해서 편함.
- WSL2 안에서 git clone, python, docker 명령 가능
- Docker Desktop이 자동으로 WSL2와 통합

---

## 3. Cloudflare Tunnel 셋업

### 3.1 Cloudflare Zero Trust 진입

1. https://one.dash.cloudflare.com 접속
2. 처음이면 Zero Trust 팀 이름 설정 (아무거나, 예: lawtutor-승)
3. Free plan 선택

### 3.2 Tunnel 생성

1. 좌측 메뉴 Networks → Tunnels
2. "Create a tunnel" → "Cloudflared" 선택
3. Tunnel 이름: `lawtutor-home`
4. Save

### 3.3 Connector 설치 명령 복사

Tunnel 생성 후 화면에 OS별 설치 명령이 나옴.
**중요**: Docker 옵션을 선택하면 토큰만 따로 빼낼 수 있음.

토큰 형태:
```
eyJhIjoiZGVmYWJjMTIzNC4uLi...
```

이 토큰을 `.env`의 `TUNNEL_TOKEN` 값으로 저장. **이 토큰을 git에 절대 커밋하지 말 것.**

### 3.4 Public Hostname 설정

같은 Tunnel 페이지에서:

1. "Public Hostname" 탭
2. "Add a public hostname"
3. 입력:
   - **Subdomain**: `lawtutor`
   - **Domain**: 본인 도메인 선택
   - **Type**: `HTTP`
   - **URL**: `app:8000`
     (Docker 내부 네트워크에서 app 서비스의 8000 포트)
4. Save

이 작업으로 `https://lawtutor.{도메인}` → `app:8000`으로 트래픽이 라우팅됨.
Cloudflare가 자동으로 DNS CNAME 레코드와 HTTPS 인증서를 만들어준다.

---

## 4. 프로젝트 디렉토리 구성

### 4.1 코드 배치 위치 (Windows)

```
C:\Users\{사용자명}\projects\lawtutor-mcp\
├── (코드 git clone)
├── data\
│   ├── raw\
│   ├── parsed\
│   └── eval\
├── qdrant_storage\
├── bge_m3_cache\
├── .env
└── docker-compose.yml
```

### 4.2 .env 파일 생성

PowerShell에서:
```powershell
cd C:\Users\{사용자명}\projects\lawtutor-mcp
notepad .env
```

내용:
```
# 국가법령정보센터
LAW_GO_KR_OC=your_email_id

# 임베딩
EMBEDDING_PROVIDER=bge_m3
BGE_M3_MODEL_PATH=BAAI/bge-m3
BGE_M3_DEVICE=cpu

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# MCP 서버
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
LAWTUTOR_API_TOKEN={32자_랜덤_생성}

# Cloudflare
TUNNEL_TOKEN={위에서_복사한_토큰}

# 로깅
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=60
```

`LAWTUTOR_API_TOKEN` 값 랜덤 생성:
PowerShell:
```powershell
[System.Web.Security.Membership]::GeneratePassword(48, 0)
```
또는 Python:
```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4.3 .gitignore 확인

`.gitignore`에 다음 항목이 반드시 포함되어야 한다:
```
.env
data/raw/
data/parsed/
qdrant_storage/
bge_m3_cache/
*.log
```

---

## 5. docker-compose.yml

프로젝트 루트의 `docker-compose.yml`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: lawtutor-qdrant
    restart: unless-stopped
    volumes:
      - ./qdrant_storage:/qdrant/storage
    networks:
      - lawtutor-net
    # 외부 노출 X (앱이 내부 네트워크로 접근)

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: lawtutor-app
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./bge_m3_cache:/root/.cache/huggingface
      - ./logs:/app/logs
    depends_on:
      - qdrant
    networks:
      - lawtutor-net
    # 외부 노출 X (cloudflared가 내부에서 접근)

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: lawtutor-tunnel
    restart: unless-stopped
    command: tunnel --no-autoupdate run --token ${TUNNEL_TOKEN}
    env_file:
      - .env
    depends_on:
      - app
    networks:
      - lawtutor-net

networks:
  lawtutor-net:
    driver: bridge
```

핵심:
- `app`도 `qdrant`도 호스트 포트에 바인딩하지 않음 (`ports:` 없음)
- 모든 외부 통신은 `cloudflared` 컨테이너를 통해서만
- 라우터/방화벽 설정 일체 불필요

---

## 6. 데이터 인덱스 준비

### 6.1 처음 한 번: 데이터 수집부터 인덱싱까지

WSL2 또는 Windows PowerShell에서:

```bash
# Python 가상환경 (선택)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # WSL2/Linux

# 의존성 설치
pip install -e .

# 1) 데이터 수집 (M1 단계 끝났을 때)
python scripts/collect_all.py --target all

# 2) 파싱
python scripts/parse_all.py

# 3) Qdrant 컨테이너 먼저 띄우기 (인덱싱용)
docker compose up -d qdrant

# 4) 청킹 + 임베딩 + 인덱싱 (시간 좀 걸림, 30분~1시간)
python scripts/chunk_and_embed.py --recreate
```

### 6.2 인덱싱 시간 단축 팁
- BGE-M3는 첫 다운로드에 ~2.5GB 모델 파일 받음 (`bge_m3_cache/`)
- GPU 있으면 `BGE_M3_DEVICE=cuda`로 변경 시 5~10배 빨라짐
- 배치 크기 조정 가능 (config.py)

---

## 7. 서비스 기동

### 7.1 첫 기동

```bash
cd C:\Users\{사용자명}\projects\lawtutor-mcp
docker compose up -d
```

상태 확인:
```bash
docker compose ps
```

3개 컨테이너(qdrant, app, cloudflared)가 모두 `Up` 상태여야 함.

### 7.2 로그 확인

```bash
# 전체 로그 실시간
docker compose logs -f

# 특정 컨테이너
docker compose logs -f app
docker compose logs -f cloudflared
```

cloudflared 로그에 다음 같은 메시지 보이면 정상:
```
Connection registered ... connIndex=0 ... location=ICN
```
(ICN은 한국에서 가까운 인천 엣지 노드)

### 7.3 동작 확인

브라우저에서 `https://lawtutor.{도메인}/health` 접속.
`{"status":"ok"}` 응답이 보이면 성공.

---

## 8. Claude.ai에서 연결

승님 본인 + 여자친구분 각자 진행:

1. https://claude.ai 접속, 로그인
2. 좌측 하단 프로필 → Settings
3. Connectors 메뉴
4. "Add custom connector" 클릭
5. 입력:
   - **Name**: `LawTutor`
   - **URL**: `https://lawtutor.{도메인}/mcp`
   - **Advanced settings → Authorization**: `Bearer {LAWTUTOR_API_TOKEN}`
6. 저장
7. 새 대화 시작 → "+" 버튼 → Connectors → LawTutor 토글 ON
8. 테스트 질문: "행정절차법 제21조에 대해 알려줘"
9. Claude가 `search_law` 또는 `fetch_article_by_number` 도구를 자동 호출하는지 확인

여자친구분에게 공유할 정보:
- URL: `https://lawtutor.{도메인}/mcp`
- Bearer Token (안전한 채널로 전달)

---

## 9. 24/7 안정 운영 설정

### 9.1 Windows 전원 옵션 (가장 중요)

기본 Windows는 일정 시간 후 절전모드에 들어가는데, 그러면 LawTutor가 정지된다.

**필수 설정:**
1. 시작 → "전원 옵션" 검색
2. "현재 전원 관리 옵션 변경" → "고급 전원 관리 옵션 설정 변경"
3. 다음 항목 모두 "안 함"으로:
   - 디스플레이 끄기 (이건 켜둬도 됨, 화면만 꺼짐)
   - **컴퓨터를 절전 모드로 설정** ← 반드시 "안 함"
   - **하드 디스크 끄기** ← "안 함" 또는 "0"
4. 저장

### 9.2 Wi-Fi 어댑터 절전 비활성화 (Wi-Fi 사용 시)

1. 장치 관리자 → 네트워크 어댑터 → Wi-Fi 어댑터 우클릭 → 속성
2. "전원 관리" 탭
3. "전원을 절약하기 위해 컴퓨터가 이 장치를 끌 수 있음" **체크 해제**

### 9.3 자동 Windows Update 재부팅 통제

Windows Update가 새벽에 자동 재부팅하면 일시 중단됨. Docker Desktop이 자동 시작되니까 보통은 자동 복구되지만, 다음을 권장:
- 작업 시간 설정으로 본인이 PC 사용하는 시간대를 알려줌 → 그 시간엔 재부팅 안 함
- "다시 시작 알림 표시" ON

### 9.4 헬스체크 모니터링 (선택)

외부에서 5분마다 헬스체크하고 실패 시 알림받기:
- **UptimeRobot** (무료, 5분 간격, 50개 모니터링)
- https://uptimerobot.com 가입
- "Add New Monitor" → URL: `https://lawtutor.{도메인}/health`
- 알림: 이메일 또는 Telegram

다운타임 5분 이내 감지됨.

---

## 10. 운영 체크리스트

### 일상 모니터링
```bash
# 컨테이너 상태
docker compose ps

# 메모리/CPU
docker stats

# 로그 (최근 100줄)
docker compose logs --tail=100 app
docker compose logs --tail=100 cloudflared
```

### 업데이트 배포
코드 수정 후:
```bash
cd C:\Users\{사용자명}\projects\lawtutor-mcp
git pull
docker compose build app
docker compose up -d app
```

cloudflared와 qdrant는 그대로 유지됨. app만 재시작.

### 인덱스 갱신 (월 1회 또는 법령 개정 시)
```bash
# 데이터 재수집
python scripts/collect_all.py --target all

# 파싱
python scripts/parse_all.py

# 인덱싱 (기존 컬렉션 덮어쓰기)
python scripts/chunk_and_embed.py --recreate
```

### 백업
- `qdrant_storage/` 디렉토리: 주기적으로 압축해서 외장하드 또는 클라우드 스토리지에 백업
- `data/parsed/`: 인덱싱 재실행 시간을 줄이려면 백업
- `.env`: **별도 안전한 곳에 백업** (PC 고장 시 복구용)
- `bge_m3_cache/`: 다시 다운로드 가능하므로 백업 불필요

---

## 11. 트러블슈팅

### Q. Cloudflare Tunnel이 연결 안 됨
- `docker compose logs cloudflared` 확인
- 토큰이 정확한지 (.env의 TUNNEL_TOKEN)
- Cloudflare Dashboard → Networks → Tunnels에서 상태가 "Healthy"인지

### Q. Claude.ai에서 Custom Connector 추가 시 "Connection failed"
- 브라우저에서 `https://lawtutor.{도메인}/health` 직접 접속해서 응답 확인
- URL 끝이 `/mcp`인지 확인
- 다른 네트워크(모바일 데이터)에서 접속해서 확인 (집 네트워크 캐싱 이슈 배제)

### Q. 도구 호출 시 401
- Bearer Token 정확히 입력했는지
- `.env`와 Claude.ai 입력값이 일치하는지

### Q. 도구 호출 결과가 비어 있음
- Qdrant 컬렉션 확인:
  ```bash
  docker compose exec qdrant ls /qdrant/storage/collections
  ```
- 인덱싱 완료 확인:
  ```bash
  python scripts/chunk_and_embed.py --check
  ```
- 앱 로그에서 임베딩 모델 정상 로드됐는지 확인

### Q. PC 재부팅 후 자동 시작 안 됨
- Docker Desktop이 자동 시작 설정됐는지 (Settings → General)
- `docker compose ps`로 상태 확인
- 자동 시작 안 되면 수동으로:
  ```bash
  cd C:\Users\{사용자명}\projects\lawtutor-mcp
  docker compose up -d
  ```

### Q. 메모리 부족 / OOM
- BGE-M3 device를 cpu로 했는지 확인
- `docker stats`로 어떤 컨테이너가 메모리 많이 쓰는지 확인
- Qdrant 메모리 제한 (docker-compose.yml에 `mem_limit: 2g` 추가)
- 본인 작업 도중 RAM 부족하면 LawTutor 컨테이너 잠시 정지:
  ```bash
  docker compose stop  # 정지
  docker compose start # 재시작
  ```

### Q. 절전모드 들어감 (Windows)
- 9.1 절 전원 옵션 재확인
- `powercfg /requests` 명령으로 어떤 프로세스가 절전 막고 있는지 확인 (디버그용)

### Q. 인터넷 단절 후 복구 안 됨
- 보통 cloudflared가 자동 재연결하는데, 안 되면:
  ```bash
  docker compose restart cloudflared
  ```

---

## 12. PC 자리 비울 때 (출장/여행)

PC를 며칠 떠나야 할 때:

**옵션 A: 그대로 켜두기**
- 가장 간단. 전원만 안 끊기면 됨.
- 정전 위험에 대비해 UPS 구비 권장 (선택)

**옵션 B: 잠시 정지**
- 떠나기 전: `docker compose stop`
- 돌아와서: `docker compose start`
- 이 기간 동안 여자친구분이 사용 못 함을 미리 알릴 것

**옵션 C: 원격 데스크톱**
- TeamViewer, AnyDesk 등으로 원격 제어 환경 미리 셋업
- 문제 생겨도 외부에서 대응 가능

---

## 13. 보안 체크리스트

배포 후 한 번 더 확인:

- [ ] `.env` 파일이 .gitignore에 포함되어 있고 git에 커밋된 적 없는지
- [ ] `TUNNEL_TOKEN`이 git history에 안 들어갔는지 (`git log --all -p | grep TUNNEL_TOKEN`)
- [ ] `LAWTUTOR_API_TOKEN`이 32자 이상 랜덤인지
- [ ] 라우터 포트포워딩 설정이 없는지 (집 라우터 관리 페이지 확인)
- [ ] Windows 방화벽이 정상 동작 중인지
- [ ] Docker Desktop이 최신 버전인지 (보안 패치)
- [ ] Bearer Token을 여자친구분에게 안전한 채널로 전달했는지 (메신저보다는 비밀번호 관리자 또는 직접 만나서)

---

## 14. 향후 개선 (v2 검토 사항)

- **Cloudflare Access** 적용: 이메일 OTP / Google SSO 추가 인증
- **Tailscale**으로 변경: VPN 메시 네트워크, 더 간단한 운영
- **Mini PC 또는 라즈베리파이**로 분리: 본인 작업 PC와 분리하면 안정성 향상
- **자동 백업 스크립트**: qdrant_storage 압축 → 클라우드 스토리지 업로드
