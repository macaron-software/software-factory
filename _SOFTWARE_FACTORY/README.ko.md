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

# Macaron 소프트웨어 팩토리

**멀티 에이전트 소프트웨어 팩토리 — 자율 AI 에이전트가 전체 제품 라이프사이클을 오케스트레이션**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[기능](#기능) · [빠른 시작](#빠른-시작) · [스크린샷](#스크린샷) · [아키텍처](#아키텍처) · [기여](#기여)

</div>

---

## 이것은 무엇인가요?

Macaron은 소프트웨어 개발 라이프사이클 전체를 오케스트레이션하는 **자율 멀티 에이전트 플랫폼**입니다 — 아이디어에서 배포까지 — 협력하는 전문 AI 에이전트를 사용합니다.

94개의 AI 에이전트가 구조화된 워크플로우를 통해 협력하는 **가상 소프트웨어 팩토리**라고 생각하세요. SAFe 방법론, TDD 실천, 자동화 품질 게이트를 따릅니다.

### 주요 특징

- **94개 전문 에이전트** — 아키텍트, 개발자, 테스터, SRE, 보안 분석가, 프로덕트 오너
- **12개 오케스트레이션 패턴** — 솔로, 병렬, 계층, 네트워크, 적대적 쌍, 휴먼인더루프
- **SAFe 정렬 라이프사이클** — Portfolio → Epic → Feature → Story, PI 케이던스
- **자가 복구** — 자율 인시던트 감지, 트리아지 및 복구
- **보안 우선** — 인젝션 가드, RBAC, 시크릿 스크러빙, 커넥션 풀
- **DORA 메트릭** — 배포 빈도, 리드 타임, MTTR, 변경 실패율

## 스크린샷

<table>
<tr>
<td width="50%">
<strong>포트폴리오 — 전략 위원회와 거버넌스</strong><br>
<img src="docs/screenshots/ko/portfolio.png" alt="Portfolio" width="100%">
</td>
<td width="50%">
<strong>PI 보드 — 프로그램 인크리먼트 계획</strong><br>
<img src="docs/screenshots/ko/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>에이전트 — 94개 전문 AI 에이전트</strong><br>
<img src="docs/screenshots/ko/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>아이디어 워크샵 — AI 브레인스토밍</strong><br>
<img src="docs/screenshots/ko/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>미션 컨트롤 — 실시간 실행 모니터링</strong><br>
<img src="docs/screenshots/ko/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>모니터링 — 시스템 건강과 메트릭</strong><br>
<img src="docs/screenshots/ko/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## 빠른 시작

### 방법 1: Docker (권장)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

make setup
# Edit .env with your LLM API key

make run
```

Open **http://localhost:8090**

### 방법 2: Docker Compose (수동)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### 방법 3: 로컬 개발

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

export OPENAI_API_KEY=sk-...

make dev
```

### 설치 확인

```bash
curl http://localhost:8090/api/health
```

## 기여

기여를 환영합니다! 가이드라인은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

## 라이선스

**GNU Affero General Public License v3.0** — [LICENSE](LICENSE)

---

<div align="center">

**사랑을 담아 만든 [Macaron Software](https://github.com/macaron-software)**

[버그 신고](https://github.com/macaron-software/software-factory/issues) · [기능 요청](https://github.com/macaron-software/software-factory/issues)

</div>
