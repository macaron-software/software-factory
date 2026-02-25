<p align="center">
  <a href="SECURITY.md">English</a> |
  <a href="SECURITY.fr.md">Français</a> |
  <a href="SECURITY.zh-CN.md">中文</a> |
  <a href="SECURITY.es.md">Español</a> |
  <a href="SECURITY.ja.md">日本語</a> |
  <a href="SECURITY.pt.md">Português</a> |
  <a href="SECURITY.de.md">Deutsch</a> |
  <a href="SECURITY.ko.md">한국어</a>
</p>

# 보안 정책

## 지원 버전

| 버전 | 지원 |
|---------|----------|
| 2.2.x   | 예       |
| 2.1.x   | 예       |
| < 2.1   | 아니오        |

## 취약점 보고

보안 취약점을 발견한 경우 책임감 있게 보고해 주세요:

1. 공개 GitHub Issue를 **열지 마세요**
2. **security@macaron-software.com**으로 이메일을 보내주세요
3. 포함 사항:
   - 취약점 설명
   - 재현 단계
   - 잠재적 영향
   - 제안된 수정 (있는 경우)

48시간 이내에 수신을 확인하고 7일 이내에 상세한 답변을 제공합니다.

## 보안 조치

### 인증 및 인가

- 토큰 갱신이 포함된 JWT 인증
- 역할 기반 접근 제어 (RBAC): admin, project_manager, developer, viewer
- OAuth 2.0 통합 (GitHub, Azure AD)
- 보안 쿠키를 사용한 세션 관리

### 입력 검증

- 모든 LLM 입력에 대한 프롬프트 인젝션 방어
- 모든 API 엔드포인트에서의 입력 정제
- 매개변수화된 SQL 쿼리 (원시 SQL 보간 없음)
- 파일 경로 탐색 보호

### 데이터 보호

- 에이전트 출력에서의 비밀 정보 제거 (API 키, 비밀번호, 토큰)
- 소스 코드나 로그에 비밀 정보 미저장
- 민감한 값에 대한 환경 기반 설정
- 데이터 무결성을 위한 SQLite WAL 모드

### 네트워크 보안

- Content Security Policy (CSP) 헤더
- API 엔드포인트의 CORS 설정
- 사용자/IP별 속도 제한
- 프로덕션에서 HTTPS 강제 (Nginx 경유)

### 의존성 관리

- `pip-audit`를 통한 정기 의존성 감사
- bandit 및 semgrep를 사용한 SAST 스캔
- 프로젝트별 자동 보안 미션 (주간 스캔)

## 공개 정책

협조적 공개를 따릅니다. 수정이 릴리스된 후:
1. 보고자에게 크레딧 (익명을 원하지 않는 한)
2. GitHub에 보안 권고 게시
3. 보안 수정 사항으로 변경 로그 업데이트
