# 스마트팩토리 휴머노이드 로봇 모니터링 시스템

이전에 만든 ATM 모니터링 시스템의 설계(계층 구조 · 트랜잭션 원자성 · 권한 분리)를
완전히 다른 도메인(스마트팩토리)에 다시 적용해서 만든 개인 포트폴리오 프로젝트입니다.
공장 → 생산라인 → 휴머노이드 로봇 3단계 계층을 실시간으로 모니터링하고, 로봇/라인
오류를 자동으로 감지·전파하며, Claude API로 에러 로그를 분석합니다.

## 주요 기능

- 공장·라인·로봇 계층 실시간 모니터링, 상태(가동중/충전중/오류정지) 자동 반영
- 로봇 오류 등록 시 자동 오류정지 전환, 라인 오류 등록 시 소속 로봇 전체 연쇄 정지
  (모두 DB 트리거 기반, 애플리케이션 코드를 거치지 않아도 항상 보장됨)
- Flask-SocketIO 기반 실시간 알림 (공장 단위 room)
- Claude API를 활용한 로봇 에러 로그 원인 분석 (개별/배치 모드)
- 작업 이력(WorkLog) 기반 통계 — 로봇별/라인별/작업유형별 평균 작업시간, 에너지 비용
- 다중 필터 통합 검색 API + 페이지네이션 (로봇/작업이력/에러 전체)
- 세션 기반 로그인, 역할(공장장/라인 반장)별 서버 강제 데이터 스코핑

## 기술 스택

| 영역 | 기술 |
|---|---|
| 백엔드 | Flask, Flask-SocketIO |
| DB | MariaDB(로컬) / MySQL·Aiven(배포), PyMySQL |
| AI | Anthropic Claude API |
| 프론트엔드 | HTML / CSS / Vanilla JS (fetch API) |
| 인증 | Flask session + werkzeug 비밀번호 해싱 |
| 배포 | Render(앱) + Aiven(DB) |
| 테스트 | pytest, Locust(부하 테스트) |

## 아키텍처

```
routes/ (Blueprint, URL ↔ service 연결)
  → service/ (비즈니스 로직: 페이지네이션, 가공, socketio 발송)
    → dao/ (raw SQL, pymysql)
      → DB (9 Table · View 2 · Trigger 4 · Index 2)
```

## 실행 방법 (로컬)

```bash
git clone <repo-url>
cd smart-factory-monitoring
pip install -r requirements.txt

# .env 파일 생성 (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, SECRET_KEY, ANTHROPIC_API_KEY 등)
cp .env.example .env

# DDL / View / Trigger / Index 적용 (docs/ARCHITECTURE.md 3~6장 참고)
mysql -u root -p smart_factory < schema.sql
mysql -u root -p smart_factory < sql/trigger_setup.sql

python app.py   # http://localhost:5000
```

## 더 자세한 내용

DB 설계 근거(DDL/View/Trigger/Index), Flask 계층 구조, ATM 프로젝트와의 도메인
대응 설계, 개발하며 겪은 버그와 트러블슈팅 기록, 배포 과정까지 전부 정리한
심화 문서는 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)에 있습니다.
