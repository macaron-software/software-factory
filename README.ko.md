<p align="center">
  <a href="README.md">English</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.zh-CN.md">中文</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pt.md">Português</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.ko.md">한국어</a>
</p>

<div align="center">

# Software Factory

**멀티 에이전트 소프트웨어 팩토리 — 전체 제품 라이프사이클을 오케스트레이션하는 자율 AI 에이전트**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[라이브 데모: sf.macaron-software.com](https://sf.macaron-software.com)** — "Skip (Demo)"를 클릭하여 탐색

[기능](#기능) · [빠른 시작](#빠른-시작) · [스크린샷](#스크린샷) · [아키텍처](#아키텍처) · [기여하기](#기여하기)

</div>

---

## 이것은 무엇인가?

Software Factory는 아이디어 구상부터 배포까지 전체 소프트웨어 개발 라이프사이클을 오케스트레이션하는 **자율 멀티 에이전트 플랫폼**입니다. 전문화된 AI 에이전트들이 협업하여 작업을 수행합니다.

**가상 소프트웨어 공장**으로 생각하면 됩니다. 161개의 AI 에이전트가 구조화된 워크플로우를 통해 협업하며, SAFe 방법론, TDD 실천, 자동화된 품질 게이트를 따릅니다.

### 주요 특징

- **161개 전문 에이전트** — 아키텍트, 개발자, 테스터, SRE, 보안 분석가, 프로덕트 오너
- **10가지 오케스트레이션 패턴** — solo, sequential, parallel, hierarchical, network, loop, router, aggregator, wave, human-in-the-loop
- **SAFe 정렬 라이프사이클** — Portfolio → Epic → Feature → Story (PI 주기 포함)
- **자동 복구** — 자율적 인시던트 감지, 분류 및 자가 수리
- **LLM 회복력** — 다중 공급자 폴백, 지터 재시도, 속도 제한 인식, 환경 변수 기반 모델 구성
- **OpenTelemetry 관측성** — Jaeger를 통한 분산 추적, 파이프라인 분석 대시보드
- **지속적 감시견** — 일시 중지된 실행 자동 재개, 비활성 세션 복구, 실패 정리
- **보안 우선** — 프롬프트 주입 방어, RBAC, 비밀 정보 제거, 연결 풀링
- **DORA 메트릭** — 배포 빈도, 리드 타임, MTTR, 변경 실패율

## 스크린샷

<table>
<tr>
<td width="50%">
<strong>대시보드 — 적응형 SAFe 관점</strong><br>
<img src="docs/screenshots/en/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>포트폴리오 — 전략적 백로그 & WSJF</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI 보드 — 프로그램 인크리먼트 계획</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>아이디에이션 워크숍 — AI 기반 브레인스토밍</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — 애자일 릴리스 트레인 & 에이전트 팀</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>세레모니 — 워크플로우 템플릿 & 패턴</strong><br>
<img src="docs/screenshots/en/ceremonies.png" alt="Ceremonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>모니터링 — DORA 메트릭 & 시스템 헬스</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>온보딩 — SAFe 역할 선택 마법사</strong><br>
<img src="docs/screenshots/en/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>홈 — CTO Jarvis / 비즈니스 아이디어 / 프로젝트 아이디어 탭</strong><br>
<img src="docs/screenshots/en/home.png" alt="홈" width="100%">
</td>
<td width="50%">
<strong>CTO Jarvis — 전략적 AI 어드바이저</strong><br>
<img src="docs/screenshots/en/jarvis.png" alt="CTO Jarvis" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>비즈니스 아이디어 — 6에이전트 마케팅 팀</strong><br>
<img src="docs/screenshots/en/mkt_ideation.png" alt="비즈니스 아이디어" width="100%">
</td>
<td width="50%">
<strong>프로젝트 아이디어 — 멀티 에이전트 기술 팀</strong><br>
<img src="docs/screenshots/en/ideation_projet.png" alt="프로젝트 아이디어" width="100%">
</td>
</tr>
</table>

## 빠른 시작

### 옵션 1: Docker (권장)

Docker 이미지 포함: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # .env.example → .env 복사 (LLM API 키를 편집하여 추가)
make run     # 빌드 및 플랫폼 시작
```

http://localhost:8090 열기 — API 키 없이 탐색하려면 **"Skip (Demo)"**를 클릭하세요.

### 옵션 2: 로컬 설치

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # 설정 파일 생성 (LLM 키 추가 — 3단계 참조)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# 플랫폼 시작
make dev
# 또는 수동: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

http://localhost:8090 열기 — 첫 실행 시 **온보딩 마법사**가 나타납니다.
SAFe 역할을 선택하거나 **"Skip (Demo)"**를 클릭하여 즉시 탐색하세요.

### 3단계: LLM 공급자 구성

API 키가 없으면 플랫폼은 **데모 모드**로 실행됩니다 — 에이전트가 모의 응답을 반환합니다.
UI 탐색에는 유용하지만, 에이전트가 실제 코드나 분석을 생성하지 않습니다.

실제 AI 에이전트를 활성화하려면 `.env`를 편집하고 **하나의** API 키를 추가하세요:

```bash
# 옵션 A: MiniMax (시작에 권장)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# 옵션 B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# 옵션 C: NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

재시작: `make run` (Docker) 또는 `make dev` (로컬)

| 공급자 | 환경 변수 | 모델 |
|--------|----------|------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

플랫폼은 기본 공급자가 실패하면 다른 구성된 공급자로 자동 폴백합니다.
대시보드의 **Settings** 페이지(`/settings`)에서도 공급자를 구성할 수 있습니다.

## 시작하기 — 첫 번째 프로젝트

설치 후 아이디어에서 실제 프로젝트까지의 진행 방법:

### 경로 A: 아이디어에서 시작 (아이디에이션 워크숍)

1. **아이디에이션 페이지 열기** — `/ideation`으로 이동 (또는 사이드바에서 "Ideation" 클릭)
2. **아이디어 설명** — 예: *"실시간 매칭 기능이 있는 기업용 카풀 앱"*
3. **에이전트 토론 관찰** — 5개의 전문 에이전트(프로덕트 매니저, 비즈니스 분석가, 아키텍트, UX 디자이너, 보안)가 SSE 스트리밍을 통해 실시간으로 아이디어를 분석
4. **결과에서 프로젝트 생성** — **"Create an Epic from this idea"**를 클릭하면 플랫폼이:
   - 생성된 `VISION.md`와 CI/CD 스캐폴딩이 포함된 새 **프로젝트** 생성
   - PO 에이전트가 분해한 기능과 사용자 스토리가 포함된 **에픽** 생성
   - **TMA**(유지보수), **보안**, **기술 부채** 미션 자동 프로비저닝

이제 실행 준비가 된 완전한 SAFe 백로그가 있습니다.

### 경로 B: 수동으로 프로젝트 생성

1. `/projects`로 이동하여 **"New Project"** 클릭
2. 입력: 이름, 설명, 기술 스택, 저장소 경로
3. 플랫폼이 자동으로 생성:
   - 프로젝트에 할당된 **프로덕트 매니저 에이전트**
   - **TMA 미션** (지속적 유지보수 — 헬스 모니터링, 인시던트 생성)
   - **보안 미션** (주간 보안 감사 — SAST, 의존성 검사)
   - **기술 부채 미션** (월간 부채 감소 — 계획됨)

### 그 다음: 에픽 & 기능 생성

- **포트폴리오** 페이지(`/portfolio`)에서 WSJF 우선순위화로 에픽 생성
- 에픽에서 **기능**을 추가하고 **사용자 스토리**로 분해
- **PI 보드**(`/pi-board`)를 사용하여 프로그램 인크리먼트를 계획하고 기능을 스프린트에 할당

### 미션 실행

- 미션에서 **"Start"**를 클릭하여 에이전트 실행 시작
- **오케스트레이션 패턴** 선택 (hierarchical, network, parallel...)
- **Mission Control**에서 에이전트 작업을 실시간으로 관찰
- 에이전트가 도구(code_read, git, build, test, security scan)를 자율적으로 사용

### TMA & 보안 — 항상 활성

모든 프로젝트에 대해 **자동으로 활성화** — 별도 구성 불필요:

| 미션 | 유형 | 일정 | 설명 |
|------|------|------|------|
| **TMA** | 프로그램 | 지속적 | 헬스 모니터링, 인시던트 감지, 자동 복구, 티켓 생성 |
| **보안** | 리뷰 | 주간 | SAST 스캔(bandit/semgrep), 의존성 감사, 비밀 정보 탐지 |
| **기술 부채** | 감소 | 월간 | 코드 품질 분석, 리팩토링 권장 사항 |
| **셀프 힐링** | 프로그램 | 지속적 | 5xx/크래시 자동 감지 → TMA 미션 → 에이전트 진단 → 코드 수정 → 검증 |

네 가지 모두 프로젝트와 함께 생성됩니다. TMA, 보안, 셀프 힐링은 **활성** 상태로 시작하고, 기술 부채는 **계획** 상태로 시작합니다(준비되면 활성화).

## 기능

### 161개 전문 AI 에이전트

에이전트는 실제 소프트웨어 조직을 반영하는 팀으로 구성됩니다:

| 팀 | 에이전트 | 역할 |
|----|---------|------|
| **프로덕트** | Product Manager, Business Analyst, PO | SAFe 계획, WSJF 우선순위화 |
| **아키텍처** | Solution Architect, Tech Lead, System Architect | 아키텍처 결정, 디자인 패턴 |
| **개발** | Backend/Frontend/Mobile/Data Engineers | 스택별 TDD 구현 |
| **품질** | QA Engineers, Security Analysts, Test Automation | 테스트, 보안 감사, 침투 테스트 |
| **디자인** | UX Designer, UI Designer | 사용자 경험, 비주얼 디자인 |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD, 모니터링, 인프라 |
| **관리** | Scrum Master, RTE, Agile Coach | 세레모니, 퍼실리테이션, 장애물 제거 |

### 10가지 오케스트레이션 패턴

- **Solo** — 단순 작업을 위한 단일 에이전트
- **Sequential** — 순서대로 실행하는 에이전트 파이프라인
- **Parallel** — 여러 에이전트가 동시에 작업
- **Hierarchical** — 관리자가 하위 에이전트에 위임
- **Network** — 에이전트 간 피어 투 피어 협업
- **Loop** — 조건이 충족될 때까지 에이전트가 반복
- **Router** — 단일 에이전트가 입력에 따라 전문가에게 라우팅
- **Aggregator** — 여러 입력을 단일 집계자가 병합
- **Wave** — 웨이브 내 병렬, 웨이브 간 순차
- **Human-in-the-loop** — 에이전트가 제안하고 사람이 검증

### SAFe 정렬 라이프사이클

완전한 Portfolio → Epic → Feature → Story 계층 구조:

- **전략적 포트폴리오** — 포트폴리오 캔버스, 전략 테마, 가치 스트림
- **프로그램 인크리먼트** — PI 계획, 목표, 의존성
- **팀 백로그** — 사용자 스토리, 작업, 인수 기준
- **스프린트 실행** — 데일리 스탠드업, 스프린트 리뷰, 회고

### 보안 & 컴플라이언스

- **인증** — RBAC 기반 JWT 인증
- **프롬프트 주입 방어** — 악성 프롬프트 감지 및 차단
- **비밀 정보 제거** — 민감 데이터 자동 삭제
- **CSP (콘텐츠 보안 정책)** — 강화된 헤더
- **속도 제한** — 사용자별 API 할당량
- **감사 로깅** — 포괄적 활동 로그

### DORA 메트릭 & 모니터링

- **배포 빈도** — 코드가 프로덕션에 도달하는 빈도
- **리드 타임** — 커밋에서 배포까지의 기간
- **MTTR** — 인시던트 복구 평균 시간
- **변경 실패율** — 실패한 배포 비율
- **실시간 대시보드** — Chart.js 시각화
- **Prometheus 메트릭** — /metrics 엔드포인트

### 품질 메트릭 — 산업적 모니터링

결정론적 품질 스캔(LLM 불필요), 생산 라인처럼 10개 차원:

| 차원 | 도구 | 측정 항목 |
|------|------|----------|
| **복잡도** | radon, lizard | 순환 복잡도, 인지 복잡도 |
| **유닛 테스트 커버리지** | coverage.py, nyc | 라인/브랜치 커버리지 비율 |
| **E2E 테스트 커버리지** | Playwright | 테스트 파일 수, 스펙 커버리지 |
| **보안** | bandit, semgrep | 심각도별 SAST 결과 (critical/high/medium/low) |
| **접근성** | pa11y | WCAG 2.1 AA 위반 |
| **성능** | Lighthouse | Core Web Vitals 점수 |
| **문서화** | interrogate | README, changelog, API 문서, docstring 커버리지 |
| **아키텍처** | madge, jscpd, mypy | 순환 의존성, 코드 중복, 타입 오류 |
| **유지보수성** | custom | 파일 크기 분포, 대형 파일 비율 |
| **적대적 검증** | built-in | 인시던트 비율, 적대적 거부율 |

**워크플로우 단계의 품질 게이트** — 각 워크플로우 단계에 게이트 유형별 구성된 임계값에 따라 품질 배지(PASS/FAIL/PENDING) 표시:

| 게이트 유형 | 임계값 | 사용처 |
|------------|--------|--------|
| `always` | 0% | 분석, 계획 단계 |
| `no_veto` | 50% | 구현, 스프린트 단계 |
| `all_approved` | 70% | 리뷰, 릴리스 단계 |
| `quality_gate` | 80% | 배포, 프로덕션 단계 |

**품질 대시보드** (`/quality`) — 전체 스코어카드, 프로젝트별 점수, 트렌드 스냅샷.
품질 배지는 미션 상세, 프로젝트 보드, 워크플로우 단계, 메인 대시보드에서 확인 가능.

### 지속적 개선 워크플로우

자가 개선을 위한 3개 내장 워크플로우:

| 워크플로우 | 목적 | 에이전트 |
|-----------|------|---------|
| **quality-improvement** | 메트릭 스캔 → 최약 차원 식별 → 개선 계획 및 실행 | QA Lead, Dev, Architect |
| **retrospective-quality** | 스프린트 종료 회고: ROTI, 인시던트, 품질 데이터 수집 → 액션 아이템 | Scrum Master, QA, Dev |
| **skill-evolution** | 에이전트 성능 분석 → 시스템 프롬프트 업데이트 → 기술 진화 | Brain, Lead Dev, QA |

이러한 워크플로우는 **피드백 루프**를 생성합니다: 메트릭 → 분석 → 개선 → 재스캔 → 진행 추적.

### 내장 에이전트 도구

Docker 이미지에는 에이전트가 자율적으로 작업하는 데 필요한 모든 것이 포함:

| 카테고리 | 도구 | 설명 |
|---------|------|------|
| **코드** | `code_read`, `code_write`, `code_edit`, `code_search`, `list_files` | 프로젝트 파일 읽기, 쓰기, 검색 |
| **빌드** | `build`, `test`, `local_ci` | 빌드, 테스트, 로컬 CI 파이프라인 실행 (npm/pip/cargo 자동 감지) |
| **Git** | `git_commit`, `git_diff`, `git_log`, `git_status` | 에이전트 브랜치 격리를 통한 버전 관리 |
| **보안** | `sast_scan`, `dependency_audit`, `secrets_scan` | bandit/semgrep을 통한 SAST, CVE 감사, 비밀 정보 탐지 |
| **QA** | `playwright_test`, `browser_screenshot`, `screenshot` | Playwright E2E 테스트 및 스크린샷 (Chromium 포함) |
| **티켓** | `create_ticket`, `jira_search`, `jira_create` | TMA 추적을 위한 인시던트/티켓 생성 |
| **배포** | `docker_deploy`, `docker_status`, `github_actions` | 컨테이너 배포 및 CI/CD 상태 |
| **메모리** | `memory_store`, `memory_search`, `deep_search` | 세션 간 영구 프로젝트 메모리 |

### 자동 복구 & 자가 수리 (TMA)

자율적 인시던트 감지, 분류 및 자가 수리 주기:

- **하트비트 모니터링** — 실행 중인 모든 미션과 서비스에 대한 지속적 헬스 체크
- **인시던트 자동 감지** — HTTP 5xx, 타임아웃, 에이전트 크래시 → 자동 인시던트 생성
- **분류 & 등급화** — 심각도(P0-P3), 영향 분석, 근본 원인 가설
- **자가 수리** — 에이전트가 자율적으로 문제를 진단하고 수정 (코드 패치, 구성 변경, 재시작)
- **티켓 생성** — 해결되지 않은 인시던트는 사람이 검토할 수 있는 추적 티켓 자동 생성
- **에스컬레이션** — P0/P1 인시던트는 당직 팀에 Slack/이메일 알림 트리거
- **회고 루프** — 인시던트 후 교훈을 메모리에 저장하고 향후 스프린트에 주입

### SAFe 관점 & 온보딩

실제 SAFe 조직을 반영하는 역할 기반 적응형 UI:

- **9개 SAFe 관점** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **적응형 대시보드** — 선택한 역할에 따라 KPI, 빠른 액션, 사이드바 링크가 변경
- **온보딩 마법사** — 3단계 첫 사용자 플로우 (역할 선택 → 프로젝트 선택 → 시작)
- **관점 선택기** — 상단 바 드롭다운에서 언제든지 SAFe 역할 전환
- **동적 사이드바** — 현재 관점에 관련된 네비게이션만 표시

### 4계층 메모리 & RLM 딥 서치

지능적 검색이 가능한 세션 간 영구 지식:

- **세션 메모리** — 단일 세션 내 대화 컨텍스트
- **패턴 메모리** — 오케스트레이션 패턴 실행에서의 학습
- **프로젝트 메모리** — 프로젝트별 지식 (결정, 규칙, 아키텍처)
- **글로벌 메모리** — 프로젝트 간 조직 지식 (FTS5 전문 검색)
- **프로젝트 파일 자동 로드** — CLAUDE.md, SPECS.md, VISION.md, README.md가 모든 LLM 프롬프트에 주입 (최대 8K)
- **RLM 딥 서치** — Recursive Language Model (arXiv:2512.24601) — 최대 10회 탐색 반복의 반복적 WRITE-EXECUTE-OBSERVE-DECIDE 루프

### 에이전트 메르카토 (이적 시장)

팀 구성을 위한 토큰 기반 에이전트 마켓플레이스:

- **에이전트 등록** — 희망 가격으로 에이전트를 이적 리스트에 등록
- **프리 에이전트 풀** — 미배정 에이전트 드래프트 가능
- **이적 & 임대** — 프로젝트 간 에이전트 매매 또는 임대
- **시장 가치 평가** — 기술, 경험, 성과에 기반한 자동 에이전트 가치 평가
- **지갑 시스템** — 프로젝트별 토큰 지갑 및 거래 내역
- **드래프트 시스템** — 프로젝트에 프리 에이전트 영입

### 적대적 품질 가드

가짜/플레이스홀더 코드의 통과를 차단하는 2계층 품질 게이트:

- **L0 결정론적** — 슬롭(lorem ipsum, TBD), 모의(NotImplementedError, TODO), 가짜 빌드, 환각, 스택 불일치 즉시 탐지
- **L1 LLM 시맨틱** — 별도 LLM이 실행 패턴의 출력 품질 검토
- **점수 산정** — 점수 < 5 통과, 5-6 경고와 함께 통과, 7+ 거부
- **강제 거부** — 환각, 슬롭, 스택 불일치, 가짜 빌드는 점수에 관계없이 항상 거부

### 자동 문서화 & 위키

라이프사이클 전반에 걸친 자동 문서 생성:

- **스프린트 회고** — LLM이 생성한 회고 노트를 DB와 메모리에 저장하고, 다음 스프린트 프롬프트에 주입 (학습 루프)
- **단계 요약** — 각 미션 단계에서 결정과 결과에 대한 LLM 생성 요약 생성
- **아키텍처 결정 기록** — 아키텍처 패턴이 설계 결정을 프로젝트 메모리에 자동 기록
- **프로젝트 컨텍스트 파일** — 자동 로드되는 지침 파일(CLAUDE.md, SPECS.md, CONVENTIONS.md)이 살아있는 문서 역할
- **Confluence 동기화** — 엔터프라이즈 문서를 위한 Confluence 위키 페이지 양방향 동기화
- **Swagger 자동 문서** — `/docs`에서 OpenAPI 스키마로 94개 REST 엔드포인트 자동 문서화

## 네 가지 인터페이스

### 1. 웹 대시보드 (HTMX + SSE)

http://localhost:8090 의 메인 UI:

- **실시간 멀티 에이전트 대화** (SSE 스트리밍)
- **PI 보드** — 프로그램 인크리먼트 계획
- **Mission Control** — 실행 모니터링
- **에이전트 관리** — 에이전트 조회, 구성, 모니터링
- **인시던트 대시보드** — 자동 복구 분류
- **모바일 반응형** — 태블릿과 휴대폰에서 작동

### 2. CLI (`sf`)

전체 기능을 갖춘 커맨드라인 인터페이스:

```bash
# 설치 (PATH에 추가)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# 조회
sf status                              # 플랫폼 상태
sf projects list                       # 모든 프로젝트
sf missions list                       # WSJF 점수가 있는 미션
sf agents list                         # 145개 에이전트
sf features list <epic_id>             # 에픽 기능
sf stories list --feature <id>         # 사용자 스토리

# 작업
sf ideation "e-commerce app in React"  # 멀티 에이전트 아이디에이션 (스트리밍)
sf missions start <id>                 # 미션 실행 시작
sf metrics dora                        # DORA 메트릭

# 모니터링
sf incidents list                      # 인시던트
sf llm stats                           # LLM 사용량 (토큰, 비용)
sf chaos status                        # 카오스 엔지니어링
```

**22개 명령 그룹** · 이중 모드: API (라이브 서버) 또는 DB (오프라인) · JSON 출력 (`--json`) · 스피너 애니메이션 · 마크다운 테이블 렌더링

### 3. REST API + Swagger

`/docs` (Swagger UI)에서 자동 문서화된 94개 API 엔드포인트:

```bash
# 예시
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: http://localhost:8090/docs

### 4. MCP 서버 (Model Context Protocol)

AI 에이전트 통합을 위한 24개 MCP 도구 (포트 9501):

```bash
# MCP 서버 시작
python3 -m platform.mcp_platform.server

# 사용 가능한 도구:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## 아키텍처

### 플랫폼 개요

```
                        ┌──────────────────────┐
                        │   CLI (sf) / Web UI  │
                        │   REST API :8090     │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     FastAPI Server           │
                    │  Auth (JWT + RBAC + OAuth)   │
                    │  17 route modules            │
                    └──┬──────────┬────────────┬───┘
                       │          │            │
          ┌────────────┴┐   ┌────┴─────┐   ┌──┴───────────┐
          │ Agent Engine │   │ Workflow │   │   Mission    │
          │ 161 agents   │   │  Engine  │   │    Layer     │
          │ executor     │   │ 39 defs  │   │ SAFe cycle   │
          │ loop+retry   │   │ 10 ptrns │   │ Portfolio    │
          └──────┬───────┘   │ phases   │   │ Epic/Feature │
                 │           │ retry    │   │ Story/Sprint │
                 │           │ skip     │   └──────────────┘
                 │           │ ckpoint  │
                 │           └────┬─────┘
                 │                │
     ┌───────────┴────────────────┴───────────────┐
     │              Services                       │
     │  LLM Client (multi-provider fallback)       │
     │  Tools (code, git, deploy, memory, security)│
     │  MCP Bridge (fetch, memory, playwright)     │
     │  Quality Engine (10 dimensions)             │
     │  Notifications (Slack, Email, Webhook)      │
     └───────────────────┬─────────────────────────┘
                         │
     ┌───────────────────┴─────────────────────────┐
     │              Operations                      │
     │  Watchdog (auto-resume, stall detection)     │
     │  Auto-Heal (incident > triage > fix)         │
     │  OpenTelemetry (tracing + metrics > Jaeger)  │
     └───────────────────┬─────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │   SQLite + Memory   │
              │   4-layer memory    │
              │   FTS5 search       │
              └─────────────────────┘
```

### 파이프라인 흐름

```
Mission Created
     │
     ▼
┌─────────────┐     ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Select     │────▶│sequential│    │ parallel │    │hierarchic│
│  Pattern    │────▶│          │    │          │    │          │
└─────────────┘────▶│ adversar.│    │          │    │          │
                    └────┬─────┘    └────┬─────┘    └────┬─────┘
                         └───────────────┴───────────────┘
                                         │
                    ┌────────────────────────────────────────┐
                    │         Phase Execution                 │
                    │                                        │
                    │  Agent ──▶ LLM Call ──▶ Result         │
                    │                          │             │
                    │              ┌───success──┴──failure──┐│
                    │              ▼                        ▼│
                    │         Code phase?            Retries? │
                    │           │ yes                  │ yes │
                    │           ▼                      ▼     │
                    │     Sandbox Build         Retry w/     │
                    │     Validation            backoff      │
                    │           │                      │ no  │
                    │           ▼                      ▼     │
                    │     Quality Gate          skip_on_fail?│
                    │      │        │            │yes  │no   │
                    │    pass     fail            │     │     │
                    │      │        │             │     ▼     │
                    │      ▼        ▼             │   PAUSED  │
                    │  Checkpoint  PAUSED ◀───────┘     │     │
                    └──────┬─────────────────────────────┘    │
                           │                                  │
                    More phases? ──yes──▶ next phase          │
                           │ no                               │
                           ▼                    watchdog      │
                    Mission Completed     auto-resume ◀───────┘
```

### 관측성

```
┌──────────────────────┐    ┌────────────────────────────────┐
│   OTEL Middleware     │    │     Continuous Watchdog         │
│   (every request)     │    │                                │
│   spans + metrics     │    │  health check    every 60s     │
│         │             │    │  stall detection  phases>60min │
│         ▼             │    │  auto-resume     5/batch 5min  │
│   OTLP/HTTP export    │    │  session recovery  >30min      │
│         │             │    │  failed cleanup   zombies      │
│         ▼             │    └────────────────────────────────┘
│   Jaeger :16686       │
└──────────────────────┘    ┌────────────────────────────────┐
                            │     Failure Analysis            │
┌──────────────────────┐    │                                │
│   Quality Engine      │    │  error classification          │
│   10 dimensions       │    │  phase heatmap                 │
│   quality gates       │    │  recommendations               │
│   radar chart         │    │  resume-all button             │
│   badge + scorecard   │    └────────────────────────────────┘
└──────────────────────┘
                            ┌────────────────────────────────┐
         All data ─────────▶│  Dashboard /analytics           │
                            │  tracing stats + latency chart  │
                            │  error doughnut + phase bars    │
                            │  quality radar + scorecard      │
                            └────────────────────────────────┘
```

### 배포

```
                          Internet
                     ┌───────┴────────┐
                     │                │
          ┌──────────▼─────┐  ┌───────▼────────┐
          │ Azure VM (Prod)│  │ OVH VPS (Demo) │
          │ sf.macaron-software.com   │  │ demo.macaron-software.com  │
          │                │  │                │
          │ Nginx :443     │  │ Nginx :443     │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Platform :8090 │  │ Platform :8090 │
          │ GPT-5-mini     │  │ MiniMax-M2.5   │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Jaeger :16686  │  │ Jaeger :16686  │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ SQLite DB      │  │ SQLite DB      │
          │ /patches (ro)  │  │                │
          └────────────────┘  └────────────────┘
                     │                │
                     └───────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ GitHub          │
                    │ macaron-software│
                    │ /software-factory│
                    └─────────────────┘
```

## 프로젝트 구성

프로젝트는 `projects/*.yaml`에 정의됩니다:

```yaml
project:
  name: my-project
  root_path: /path/to/project
  vision_doc: CLAUDE.md

agents:
  - product_manager
  - solution_architect
  - backend_dev
  - qa_engineer

patterns:
  ideation: hierarchical
  development: parallel
  review: adversarial-pair

deployment:
  strategy: blue-green
  auto_prod: true
  health_check_url: /health

monitoring:
  prometheus: true
  grafana_dashboard: project-metrics
```

## 디렉토리 구조

```
├── platform/                # 에이전트 플랫폼 (152개 Python 파일)
│   ├── server.py            # FastAPI 앱, 포트 8090
│   ├── agents/              # 에이전트 루프, 실행기, 저장소
│   ├── a2a/                 # 에이전트 간 메시징 버스
│   ├── patterns/            # 10개 오케스트레이션 패턴
│   ├── missions/            # SAFe 미션 라이프사이클
│   ├── sessions/            # 대화 실행기 + SSE
│   ├── web/                 # 라우트 + Jinja2 템플릿
│   ├── mcp_platform/        # MCP 서버 (23개 도구)
│   └── tools/               # 에이전트 도구 (코드, git, 배포)
│
├── cli/                     # CLI 'sf' (6개 파일, 2100+ LOC)
│   ├── sf.py                # 22개 명령 그룹, 40+ 하위 명령
│   ├── _api.py              # httpx REST 클라이언트
│   ├── _db.py               # sqlite3 오프라인 백엔드
│   ├── _output.py           # ANSI 테이블, 마크다운 렌더링
│   └── _stream.py           # 스피너가 있는 SSE 스트리밍
│
├── dashboard/               # 프론트엔드 HTMX
├── deploy/                  # Helm 차트, Docker, K8s
├── tests/                   # E2E Playwright 테스트
├── skills/                  # 에이전트 기술 라이브러리
├── projects/                # 프로젝트 YAML 구성
└── data/                    # SQLite 데이터베이스
```

## 테스트

```bash
# 모든 테스트 실행
make test

# E2E 테스트 (Playwright — 먼저 설치 필요)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test

# 유닛 테스트
pytest tests/

# 카오스 엔지니어링
python3 tests/test_chaos.py

# 내구성 테스트
python3 tests/test_endurance.py
```

## 배포

### Docker

Docker 이미지 포함: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.
에이전트는 기본적으로 프로젝트 빌드, 스크린샷이 포함된 E2E 테스트 실행, SAST 보안 스캔을 수행할 수 있습니다.

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### 환경 변수

전체 목록은 [`.env.example`](.env.example)을 참조하세요. 주요 변수:

```bash
# LLM 공급자 (실제 에이전트에 필요)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # MiniMax API 키

# 인증 (선택사항)
GITHUB_CLIENT_ID=...                 # GitHub OAuth
GITHUB_CLIENT_SECRET=...
AZURE_AD_CLIENT_ID=...               # Azure AD OAuth
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_TENANT_ID=...

# 통합 (선택사항)
JIRA_URL=https://your-jira.atlassian.net
ATLASSIAN_TOKEN=your-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## 적응형 인텔리전스 — GA · RL · Thompson 샘플링 · OKR

플랫폼은 세 가지 보완적인 AI 엔진을 통해 자가 최적화됩니다.

### Thompson 샘플링 — 확률적 팀 선택
- 컨텍스트 `(agent_id, pattern_id, technology, phase_type)`별 `Beta(wins+1, losses+1)` 유지
- 세밀한 적합도 점수 — 컨텍스트별 독립 점수, 교차 컨텍스트 오염 없음
- 콜드 스타트 폴백: 기술 접두사 체인(`angular_19` → `angular_*` → `generic`) 순차 적용
- 소프트 퇴역: 약한 팀에 `weight_multiplier=0.1` 적용, 회복 가능
- 자동 A/B 섀도우 실행; 중립 평가자가 승자 결정
- **Darwin LLM**: Thompson 샘플링을 컨텍스트별 LLM 모델 선택으로 확장

### 유전 알고리즘 — 워크플로우 진화
- 게놈 = PhaseSpec(pattern, agents, gate)의 순서 있는 목록
- 개체군: 40개 게놈, 최대 30세대, 엘리트=2, 변이율=15%, 토너먼트 k=3
- 적합도: 페이즈 성공률 × 에이전트 적합도 × (1 − 거부율) × 리드 타임 보너스
- 상위 3개 제안을 `evolution_proposals`에 저장, 적용 전 인간 검토
- 수동 트리거: `POST /api/evolution/run/{wf_id}` — Workflows → Evolution 탭에서 확인
- 야간 스케줄러; 5개 미만의 미션은 건너뜀

### 강화 학습 — 미션 중 패턴 적응
- Q-러닝 정책 (`platform/agents/rl_policy.py`)
- 액션: keep, switch_parallel, switch_sequential, switch_hierarchical, switch_debate, add_agent, remove_agent
- 상태: `(wf_id, phase_position, rejection_pct, quality_score)` 버킷화
- Q 업데이트: α=0.1, γ=0.9, ε=0.1 — `rl_experience` 테이블에서 오프라인 배치 처리
- 신뢰도 ≥ 70% 및 상태 방문 ≥ 3회일 때만 발동; 점진적 성능 저하 지원

### OKR / KPI 시스템
- 8개 기본 시드: code/migration, security/audit, architecture/design, testing, docs
- OKR 달성도가 GA 적합도와 RL 보상 신호에 직접 반영
- `/teams`에서 인라인 편집, 녹색/황색/빨간색 상태 표시
- 설정에서 프로젝트별 OKR 재정의 가능

---

## v2.1.0의 새로운 기능 (2026년 2월)

### 품질 메트릭 — 산업적 모니터링
- **10개 결정론적 차원** — 복잡도, 커버리지(UT/E2E), 보안, 접근성, 성능, 문서화, 아키텍처, 유지보수성, 적대적 검증
- **워크플로우 단계의 품질 게이트** — 구성 가능한 임계값(always/no_veto/all_approved/quality_gate)으로 단계별 PASS/FAIL 배지
- **품질 대시보드** (`/quality`) — 전체 스코어카드, 프로젝트별 점수, 트렌드 스냅샷
- **모든 곳에 품질 배지** — 미션 상세, 프로젝트 보드, 워크플로우 단계, 메인 대시보드
- **LLM 불필요** — 모든 메트릭은 오픈소스 도구(radon, bandit, semgrep, coverage.py, pa11y, madge)를 사용하여 결정론적으로 산출

### 프로젝트당 4개 자동 프로비저닝 미션
모든 프로젝트에 4개의 운영 미션이 자동 제공:
- **MCO/TMA** — 지속적 유지보수: 헬스 모니터링, 인시던트 분류(P0-P4), TDD 수정, 비회귀 검증
- **보안** — 주간 SAST 스캔, 의존성 감사, CVE 감시, 코드 리뷰
- **기술 부채** — 월간 부채 감소: 복잡도 감사, WSJF 우선순위화, 리팩토링 스프린트
- **셀프 힐링** — 자율 인시던트 파이프라인: 5xx 감지 → TMA 미션 생성 → 에이전트 진단 → 코드 수정 → 검증

### 지속적 개선
- **quality-improvement 워크플로우** — 스캔 → 최약 차원 식별 → 개선 계획 및 실행
- **retrospective-quality 워크플로우** — ROTI, 인시던트, 품질 메트릭이 포함된 스프린트 회고 → 액션 아이템
- **skill-evolution 워크플로우** — 에이전트 성능 분석 → 프롬프트 업데이트 → 기술 진화
- **피드백 루프** — 메트릭 → 분석 → 개선 → 재스캔 → 진행 추적

### SAFe 관점 & 온보딩
- **9개 SAFe 역할 관점** — 역할별 적응형 대시보드, 사이드바, KPI
- **온보딩 마법사** — 역할 및 프로젝트 선택이 포함된 3단계 첫 사용자 플로우
- **관점 선택기** — 상단 바에서 언제든지 SAFe 역할 전환

### 자동 복구 & 자가 수리
- **TMA 하트비트** — 자동 인시던트 생성이 포함된 지속적 헬스 모니터링
- **자가 수리 에이전트** — 일반적인 장애에 대한 자율적 진단 및 수정
- **티켓 에스컬레이션** — 미해결 인시던트가 알림이 포함된 추적 티켓 생성

### 4계층 메모리 & RLM
- **영구 지식** — FTS5가 포함된 세션, 패턴, 프로젝트, 글로벌 메모리 계층
- **RLM 딥 서치** — 복잡한 코드베이스 분석을 위한 재귀적 탐색 루프 (최대 10회 반복)
- **프로젝트 컨텍스트 자동 로드** — CLAUDE.md, SPECS.md, VISION.md가 모든 에이전트 프롬프트에 주입

### 적대적 품질 가드
- **L0 결정론적** — 슬롭, 모의, 가짜 빌드, 환각 즉시 탐지
- **L1 시맨틱** — 실행 출력에 대한 LLM 기반 품질 검토
- **강제 거부** — 환각 및 스택 불일치는 항상 차단

### 에이전트 메르카토
- **토큰 기반 마켓플레이스** — 에이전트 등록, 이적, 임대, 프리 에이전트 드래프트
- **시장 가치 평가** — 기술과 성과에 기반한 자동 에이전트 가격 산정
- **지갑 시스템** — 거래 내역이 포함된 프로젝트별 토큰 경제

### 인증 & 보안
- **JWT 기반 인증** — 로그인/가입/갱신/로그아웃
- **RBAC** — admin, project_manager, developer, viewer 역할
- **OAuth** — GitHub 및 Azure AD SSO 로그인
- **관리자 패널** — 사용자 관리 UI (`/admin/users`)
- **데모 모드** — 즉시 접근을 위한 원클릭 "Skip" 버튼

### 자동 문서화
- **스프린트 회고** — 학습 루프가 포함된 LLM 생성 회고 노트
- **단계 요약** — 미션 단계 결과 자동 문서화
- **Confluence 동기화** — 양방향 위키 통합

### LLM 공급자
- **다중 공급자** — 자동 폴백 체인
- MiniMax M2.5, Azure OpenAI GPT-5-mini, Azure AI Foundry, NVIDIA NIM
- API 키 없이 UI 탐색을 위한 **데모 모드**

### 플랫폼 개선사항
- LLM 비용 추적이 포함된 DORA 메트릭 대시보드
- Jira 양방향 동기화
- Playwright E2E 테스트 스위트 (11개 스펙 파일)
- 국제화 (EN/FR)
- 실시간 알림 (Slack, Email, Webhook)
- 워크플로우 내 디자인 시스템 파이프라인 (UX → dev → review)
- 3D Agent World 시각화

### Darwin — 진화적 팀 선택
- **Thompson Sampling 선택** — `Beta(wins+1, losses+1)` 기반 확률적 agent+pattern 팀 선택 (`agent_id, pattern_id, 기술, 단계_유형` 차원)
- **세밀한 적합도 추적** — 컨텍스트별 독립 점수: Angular 마이그레이션에 강한 팀이 Angular 신기능에는 약할 수 있음
- **유사도 폴백** — 기술 접두사 매칭으로 콜드 스타트 해결 (`angular_19` → `angular_*` → `generic`)
- **소프트 은퇴** — 지속 저성과 팀에 `weight_multiplier=0.1` 적용, 우선순위 하향이지만 복구 가능
- **OKR / KPI 시스템** — 도메인과 단계 유형별 목표 및 지표; 기본 시드 8개
- **A/B 섀도우 테스트** — 두 팀의 적합도 차이가 10 미만이거나 10% 확률로 자동 병렬 실행
- **Teams 대시보드** `/teams` — champion/rising/declining/retired 배지 리더보드, 인라인 OKR 편집, 진화 차트, 선택 이력, A/B 결과
- **논브레이킹 옵트인** — 패턴에서 `agent_id: "skill:developer"` 사용 시 Darwin 활성화; 명시적 ID 변경 없음

## v2.2.0의 새로운 기능 (2026년 2월)

### OpenTelemetry & 분산 추적
- **OTEL 통합** — Jaeger로의 OTLP/HTTP 익스포터가 포함된 OpenTelemetry SDK
- **ASGI 추적 미들웨어** — 모든 HTTP 요청에 대해 스팬, 지연 시간, 상태 추적
- **추적 대시보드** (`/analytics`) — 요청 통계, 지연 시간 차트, 작업 테이블
- **Jaeger UI** — 포트 16686에서 전체 분산 추적 탐색

### 파이프라인 실패 분석
- **실패 분류** — Python 기반 오류 분류 (setup_failed, llm_provider, timeout, phase_error 등)
- **단계 실패 히트맵** — 가장 자주 실패하는 파이프라인 단계 식별
- **추천 엔진** — 실패 패턴에 기반한 실행 가능한 제안
- **전체 재개 버튼** — 대시보드에서 일시 중지된 실행을 원클릭으로 대량 재개

### 지속적 감시견
- **자동 재개** — 일시 중지된 실행을 배치로 자동 재개 (5개/배치, 5분마다, 최대 10개 동시)
- **비활성 세션 복구** — 30분 이상 비활성 세션 감지, 재시도를 위해 중단 표시
- **실패 세션 정리** — 파이프라인 진행을 차단하는 좀비 세션 정리
- **정체 감지** — 60분 이상 단계에 정체된 미션에 자동 재시도

### 단계 회복력
- **단계별 재시도** — 단계별 지수 백오프가 포함된 구성 가능한 재시도 횟수 (기본 3회)
- **skip_on_failure** — 단계를 선택적으로 설정하여 실패 시 파이프라인 계속 실행 가능
- **체크포인팅** — 완료된 단계 저장, 스마트 재개로 완료된 작업 건너뛰기
- **단계 타임아웃** — 10분 제한으로 무한 중단 방지

### 샌드박스 빌드 검증
- **코드 후 빌드 검사** — 코드 생성 단계 후 자동으로 빌드/린트 실행
- **빌드 시스템 자동 감지** — npm, cargo, go, maven, python, docker
- **오류 주입** — 빌드 실패를 에이전트 컨텍스트에 주입하여 자가 수정

### 품질 UI 개선
- **레이더 차트** — `/quality`에서 품질 차원의 Chart.js 레이더 시각화
- **품질 배지** — 프로젝트 헤더에 컬러 점수 원 (`/api/dashboard/quality-badge`)
- **미션 스코어카드** — 미션 상세 사이드바의 품질 메트릭 (`/api/dashboard/quality-mission`)

### 멀티 모델 LLM 라우팅
- **3개의 전문 모델** — `gpt-5.2` 는 무거운 추론, `gpt-5.1-codex` 는 코드/테스트, `gpt-5-mini` 는 경량 작업용
- **역할 기반 라우팅** — 에이전트는 태그(`reasoner`, `architect`, `developer`, `tester`, `doc_writer`…)를 기반으로 자동으로 올바른 모델을 받음
- **실시간 구성 가능** — 재시작 없이 설정 → LLM에서 라우팅 매트릭스 편집

### Darwin LLM — 모델에 대한 Thompson Sampling
- **모델 A/B 테스트** — 동일한 팀(에이전트 + 패턴)이 다른 LLM으로 경쟁; 최고의 모델이 컨텍스트별로 자동 승리
- **베타 분포** — `(agent_id, pattern_id, technology, phase_type, llm_model)`당 `Beta(wins+1, losses+1)`
- **/teams의 LLM A/B 탭** — 모델별 피트니스 순위 및 A/B 테스트 기록
- **우선순위 체인** — Darwin LLM → DB 구성 → 기본값 (우아한 성능 저하)

### 설정 — LLM 탭
- **프로바이더 그리드** — 활성/비활성 상태 및 누락된 API 키 힌트 표시
- **라우팅 매트릭스** — 카테고리별(추론, 생산/코드, 작업, 문서 작성) 무거운/가벼운 모델 구성
- **Darwin LLM A/B 섹션** — 진행 중인 모델 실험의 실시간 보기

## v2.3.0의 새로운 기능 (2026년 2월)

### 재구성된 내비게이션 — 홈 + 대시보드
- **홈 페이지** (`/`) — 세 개의 탭: CTO Jarvis · 비즈니스 아이디어 · 프로젝트 아이디어
- **대시보드** (`/portfolio`) — 세 개의 탭: 개요 · CTO · 비즈니스
- **간소화된 사이드바** — 홈과 대시보드 두 항목만
- **Feather SVG 아이콘** — 이모지를 일관된 벡터 아이콘으로 교체

### CTO Jarvis — 전략적 AI 어드바이저
- **영구적 채팅 패널** — 홈 페이지 전용 탭
- **영구적 메모리** — 기술적 결정과 세션 컨텍스트를 대화 간에 유지
- **CTO 수준 어드바이저** — 아키텍처 결정, 기술 선택 지원
- **플랫폼 인식** — 포트폴리오, 프로젝트, 에이전트 팀의 현재 상태 파악

**도구**: 코드（읽기/검색/편집/쓰기/목록）· Git（commit, diff, log, status, issues/PRs/search）· 빌드/배포（build, lint, test, deploy, Docker, run_command, infra）· 보안（SAST, 시크릿 스캔, 의존성）· MCP（Web fetch, 지식 그래프, Playwright, GitHub）· 프로젝트（Jira, Confluence, SAFe 단계, LRM 컨텍스트）· 메모리（지식 그래프 읽기 + 쓰기）

**빠른 실행 칩**: `포트폴리오 통계` · `진행 중 미션` · `팀 구성` · `GitHub` · `AO Veligo` · `Angular 16→17 마이그레이션` · `기술 부채 · 보안 · a11y · GDPR` · `Git commit & PR` · `E2E + 스크린샷` · `Jira 동기화` · `Wiki 업데이트`

**질문 예시**

> *"포트폴리오 전체 상태는 어떤가요? 지연된 프로젝트가 있나요?"*

> *"Veligo 프로젝트에 SAST 감사를 실행하고 우선 처리해야 할 심각한 CVE 3개를 알려주세요."*

> *"API를 REST에서 GraphQL로 마이그레이션해야 합니다 — 어떤 에이전트 팀을 추천하나요?"*

> *"feature/auth 브랜치의 최근 5개 커밋 diff를 보여주고 변경 사항을 요약해 주세요."*

> *"순환 복잡도 15 이상인 파일을 줄이기 위한 리팩토링 미션을 만들어 주세요."*

> *"현재 기술 부채는 무엇인가요? 영향/노력 기준으로 우선순위를 정해주세요."*

> *"Azure AD SSO 로그인 기능의 사용자 스토리를 작성하고 Jira 티켓을 열어주세요."*

> *"Playwright E2E 테스트를 실행하고 주요 페이지 스크린샷을 찍어주세요."*

> *"이번 달과 지난 달의 DORA 지표를 비교해 주세요 — 어디서 퇴보하고 있나요?"*

> *"PostgreSQL 마이그레이션에 대한 최신 결정으로 아키텍처 위키를 업데이트해 주세요."*


- **라우트** `/mkt-ideation` — 홈 페이지 비즈니스 아이디어 탭에서 접근
- **CMO Sophie Laurent** — 5명의 전문 마케팅 전문가를 이끄는 팀 리더
- **완전한 마케팅 플랜 JSON** — SWOT, TAM/SAM/SOM, 브랜드 전략, GTM, KPI, 예산
- **에이전트 그래프** — 아바타 사진, 협업 엣지, 상세 팝오버의 ig-node 시각화

### PostgreSQL 마이그레이션 + 40 인덱스
- **SQLite → PostgreSQL 마이그레이션** — 완전한 스키마 및 데이터 마이그레이션 스크립트
- **네이티브 PostgreSQL FTS** — `tsvector/tsquery`가 FTS5를 대체, 더 성능적이고 확장 가능
- **40+ PG 인덱스** — 모든 핫 쿼리 경로의 포괄적 커버리지
- **Darwin Teams** — 컨텍스트(기술+단계)별 에이전트 팀 선택을 위한 Thompson 샘플링

## 기여하기

기여를 환영합니다! 가이드라인은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

## 라이선스

이 프로젝트는 AGPL v3 라이선스 하에 배포됩니다 - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 지원

- 라이브 데모: https://sf.macaron-software.com
- 이슈: https://github.com/macaron-software/software-factory/issues
- 토론: https://github.com/macaron-software/software-factory/discussions
