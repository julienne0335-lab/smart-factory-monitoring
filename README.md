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
- (확장) MQTT 가상 센서 시뮬레이터 → 백엔드 실시간 반영 파이프라인 — 하드웨어 없이
  로컬에서 IoT 수집 계층 아키텍처를 검증 (로컬 전용, 자세한 내용은 아래 참고)

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

### (선택) MQTT 센서 시뮬레이터 실행

75대 로봇의 배터리·관절마모 값을 실시간으로 흘려보내는 가상 센서 파이프라인입니다.
Mosquitto 브로커가 필요합니다(winget으로 설치하면 Windows 서비스로 자동 실행됨 —
`mosquitto/mosquitto.conf`에 브로커가 없을 때 수동 실행하는 방법도 적어뒀습니다).

```bash
# 1) python app.py로 백엔드를 먼저 띄워두면(위 단계) mqtt_bridge.py가 자동으로 구독을 시작함
# 2) 별도 터미널에서 시뮬레이터 실행
python scripts/mqtt_sensor_simulator.py
```

배터리가 `warning_threshold`(기본 20) 아래로 떨어지면 `battery_status_update`
트리거가 로봇 상태를 자동으로 `충전중`으로 바꾸고, `robot_sensor_update` 소켓
이벤트가 해당 공장 room으로 실시간 전파됩니다.

### (선택) Docker로 한 번에 실행 (앱 + MariaDB + Mosquitto)

로컬에 MariaDB/Mosquitto를 직접 설치하지 않고, docker-compose로 전체 스택을
한 번에 띄울 수 있습니다.

> **주의**: 위 "MQTT 센서 시뮬레이터" 절차대로 로컬에 Mosquitto를 Windows
> 서비스로 이미 설치했다면, 그 서비스가 `1883` 포트를 점유하고 있어서
> mosquitto 컨테이너가 못 뜹니다. Docker 스택을 쓰기 전에 서비스 관리자에서
> "Mosquitto Broker" 서비스를 멈추거나(`Stop-Service mosquitto`, 관리자 권한
> 필요), 관리자 PowerShell에서 `net stop mosquitto`를 실행하세요. 로컬
> 서비스로 다시 돌아가려면 `Start-Service mosquitto`로 재시작하면 됩니다.

```bash
cp .env.docker.example .env.docker
# .env.docker에 ANTHROPIC_API_KEY, SECRET_KEY 값을 채운다
# (DB_HOST/MQTT_BROKER_HOST 등은 docker-compose.yml이 서비스명 기준으로 이미 채워줌)

docker compose up --build
# http://localhost:5000
```

첫 실행 시 `sql/smart_factory_dump_notrig_final.sql` + `sql/docker-init/02_triggers.sql`이
MariaDB 컨테이너의 `docker-entrypoint-initdb.d`로 자동 실행되어 스키마·트리거가
바로 준비됩니다(데이터가 이미 있는 볼륨이면 재실행되지 않음). MQTT 시뮬레이터는
호스트에서 그대로 실행하면 됩니다(mosquitto 컨테이너가 `127.0.0.1:1883`으로 게시됨):

```bash
python scripts/mqtt_sensor_simulator.py
```

앱 컨테이너는 프로젝트 폴더를 그대로 마운트하므로 코드를 수정하면 (Werkzeug
reloader가) 자동 반영됩니다.

## 테스트

```bash
pip install -r requirements-test.txt
pytest tests/          # service 계층 단위 테스트 (DB 없이, DAO/socketio는 Mock)
```

Docker 스택을 띄운 상태라면, 컨테이너 3개가 실제로 붙어서 동작하는지
(DB 초기화, API 왕복까지) 확인하는 스모크 테스트도 있습니다:

```bash
python scripts/docker_smoke_test.py
```

## 더 자세한 내용

DB 설계 근거(DDL/View/Trigger/Index), Flask 계층 구조, ATM 프로젝트와의 도메인
대응 설계, 개발하며 겪은 버그와 트러블슈팅 기록, 배포 과정, 그리고 이번 MQTT
확장 기록까지 전부 정리한 심화 문서는 [`docs/DEVLOG.md`](docs/DEVLOG.md)에 있습니다.
