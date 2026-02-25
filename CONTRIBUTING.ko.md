<p align="center">
  <a href="CONTRIBUTING.md">English</a> |
  <a href="CONTRIBUTING.fr.md">Français</a> |
  <a href="CONTRIBUTING.zh-CN.md">中文</a> |
  <a href="CONTRIBUTING.es.md">Español</a> |
  <a href="CONTRIBUTING.ja.md">日本語</a> |
  <a href="CONTRIBUTING.pt.md">Português</a> |
  <a href="CONTRIBUTING.de.md">Deutsch</a> |
  <a href="CONTRIBUTING.ko.md">한국어</a>
</p>

# Software Factory 기여 가이드

Software Factory에 기여해 주셔서 감사합니다! 이 문서는 기여를 위한 지침과 안내를 제공합니다.

## 행동 강령

참여함으로써 [행동 강령](CODE_OF_CONDUCT.ko.md)을 준수하는 데 동의합니다.

## 기여 방법

### 버그 보고

1. 중복을 피하기 위해 [기존 Issue](https://github.com/macaron-software/software-factory/issues)를 확인하세요
2. [버그 보고서 템플릿](.github/ISSUE_TEMPLATE/bug_report.md)을 사용하세요
3. 포함 사항: 재현 단계, 예상 동작 대 실제 동작, 환경 세부 정보

### 기능 제안

1. [기능 요청 템플릿](.github/ISSUE_TEMPLATE/feature_request.md)으로 Issue를 생성하세요
2. 사용 사례와 예상 동작을 설명하세요
3. 다른 사용자에게 왜 유용한지 설명하세요

### Pull Requests

1. 리포지토리를 포크
2. 기능 브랜치 생성: `git checkout -b feature/my-feature`
3. 아래 코딩 표준에 따라 변경
4. 테스트 작성 또는 업데이트
5. 테스트 실행: `make test`
6. 명확한 메시지로 커밋 (아래 규약 참조)
7. 푸시하고 Pull Request 생성

## 개발 환경 설정

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make test
make dev
```

## 코딩 표준

### Python

- **스타일**: PEP 8, `ruff`로 강제
- **타입 힌트**: 공개 API에 필수
- **독스트링**: 모듈, 클래스, 공개 함수에 Google 스타일
- **임포트**: 모든 파일에 `from __future__ import annotations`

### 커밋 메시지

[Conventional Commits](https://www.conventionalcommits.org/)를 따르세요:

```
feat: WebSocket 실시간 채널 추가
fix: 미션 API 라우트 순서 수정
refactor: api.py를 서브 모듈로 분할
docs: 아키텍처 다이어그램 업데이트
test: 워커 큐 테스트 추가
```

### 테스트

- `tests/`의 유닛 테스트 (`pytest` 사용)
- 비동기 테스트 (`pytest-asyncio` 사용)
- `platform/tests/e2e/`의 E2E 테스트 (Playwright 사용)
- 모든 새 기능에 테스트 필수

### 아키텍처 규칙

- **LLM이 생성하고, 결정론적 도구가 검증** — 창의적 작업에 AI, 검증에 스크립트/컴파일러
- **대형 파일 금지** — 500줄 이상 모듈은 서브 패키지로 분할
- **SQLite 영속화** — 외부 데이터베이스 의존 없음
- **멀티 프로바이더 LLM** — 단일 프로바이더 하드코딩 금지
- **하위 호환성** — 새 기능이 기존 API를 깨뜨리면 안 됨

## 라이선스

기여함으로써, 귀하의 기여가 [AGPL v3 라이선스](LICENSE) 하에 라이선스됨에 동의합니다.
