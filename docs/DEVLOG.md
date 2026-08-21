# 스마트팩토리 로봇 모니터링 시스템 — 전체 설계 & 작업 기록

> 빠르게 훑어보려면 리포지토리 루트의 [`README.md`](../README.md)를 먼저
> 확인하세요. 이 문서는 그보다 훨씬 깊은 설계 근거와 개발 기록을 담은
> 심화 문서입니다.

이 문서는 프로젝트의 원래 설계(ATM 모니터링 시스템과의 도메인 대응 설계, DB
설계, Flask 애플리케이션 구조)부터, 2026-08-21에 진행한 포트폴리오 문서 대조
검증과 신규 기능 구현(라인장애 연쇄 처리, 에너지 비용 통계)까지를 이어서
정리합니다.

목차:

1. [시스템 개요와 설계 철학](#1-시스템-개요와-설계-철학)
2. [ATM ↔ 스마트팩토리 도메인 대응 설계](#2-atm--스마트팩토리-도메인-대응-설계)
3. [DB 설계 — DDL](#3-db-설계--ddl)
4. [VIEW](#4-view)
5. [TRIGGER (원본)](#5-trigger-원본)
6. [INDEX](#6-index)
7. [Flask 애플리케이션 구조](#7-flask-애플리케이션-구조)
8. [시스템 규모(더미 데이터)](#8-시스템-규모더미-데이터)
9. [검증 배경 — 포트폴리오 문서 재검증 (2026-08-21)](#9-검증-배경--포트폴리오-문서-재검증-2026-08-21)
10. [구현 1 — 라인장애 연쇄 처리](#10-구현-1--라인장애-연쇄-처리-지점장애--라인-전체-가동-중단)
11. [구현 2 — 에너지 비용 통계](#11-구현-2--에너지-비용-통계-수수료-통계--작업별-에너지-비용-집계)
12. [DB에 적용하기 (HeidiSQL 기준)](#12-db에-적용하기-heidisql-기준)
13. [로컬/Aiven 계정 로그인 아이디 불일치](#13-로컬aiven-계정-로그인-아이디-불일치)
14. [실제 검증 결과](#14-실제-검증-결과-2026-08-21-기준)
15. [Git 커밋](#15-git-커밋)
16. [배포 체크리스트](#16-배포-체크리스트)

---

## 1. 시스템 개요와 설계 철학

이 프로젝트는 이전에 만든 **ATM 모니터링 시스템**의 설계를 그대로 다른 도메인
(휴머노이드 로봇 스마트팩토리)에 대입해서 만든 것입니다. "설계의 본질은 도메인이
아니다"라는 원칙 아래, 아래 세 가지 패턴을 그대로 재사용했습니다.

- **계층 구조**: `ATM → 지점 → 은행` 패턴을 `로봇 → 생산라인 → 공장`으로 대입.
  하위 장애가 상위로, 상위 상태 변경이 하위 전체로 전파되는 구조를 DB 수준
  (FK + Trigger)에서 표현합니다.
- **트랜잭션 원자성**: "작업 개수"가 아니라 "결과가 항상 일치해야 하는가"를
  기준으로 하나의 트랜잭션으로 묶습니다. 예: 라인장애 등록은 라인장애로그 INSERT
  와 소속 로봇 전체 상태 반영이 하나라도 실패하면 전체 롤백되어야 합니다.
- **권한 분리**: 슈퍼관리자(공장장)는 전체 범위, 일반관리자(라인 반장)는 소속
  범위만. 프론트 버튼 숨김 + Service 계층 검증 + SQL WHERE 범위 제한, 세 곳에서
  이중삼중으로 검증합니다(프론트 숨김은 우회 가능하므로 서버 측 검증이 핵심).

Stack: **Flask + Flask-SocketIO(백엔드) / MySQL·MariaDB(DB, pymysql) / Claude API
(에러 로그 AI 분석) / 세션 기반 로그인**.

---

## 2. ATM ↔ 스마트팩토리 도메인 대응 설계

| ATM 시스템 | 휴머노이드 스마트팩토리 |
|---|---|
| ATM (개별 기기) | 휴머노이드 로봇 (개별 기체) |
| 지점 | 생산라인 (Line A, B, C…) |
| 은행 | 공장 전체 |
| 현금잔량 | 배터리 잔량 / 관절 마모도 |
| 경고임계값 | 배터리 20% 이하 → 충전 대기 |
| 현금보충 이력 | 배터리 교체 / 부품 교체 이력 |
| ATM 장애로그 | 로봇 오류 로그 (센서 이상·낙상·충돌) |
| 지점장애 | 라인 전체 가동 중단 |
| 은행장애 | 공장 전체 비상정지 (화재·정전) |
| 거래내역 | 작업 수행 이력 (조립·용접·이송) |
| 자행/타행 구분 | 로봇 작업 / 사람 작업 |
| 수수료 통계 | 작업별 에너지 비용·소요시간 집계 |
| 유지보수 이력 | 정기점검 / 사고후 점검 이력 |
| 슈퍼관리자 | 공장장 (전체 라인 접근) |
| 일반관리자 | 라인 반장 (담당 라인만 접근) |
| 정상 / 점검중 / 장애 | 가동중 / 충전중 / 오류정지 |

### 트랜잭션 패턴 대응

```
# ATM: 지점장애 등록
지점장애로그 INSERT + 소속 ATM 전체 장애로그 일괄 INSERT
→ 하나라도 실패 시 전체 rollback

# 스마트팩토리: 라인 가동 중단
라인장애로그 INSERT + 소속 로봇 전체 오류로그 일괄 INSERT
→ 하나라도 실패 시 전체 rollback   ← 코드 구조 동일
```

### 권한 분리 대응

```
# ATM        — 슈퍼관리자: 소속 은행 전체 ATM 접근 / 일반관리자: 소속 지점만
# 스마트팩토리 — 공장장: 전체 라인·로봇 접근 / 라인 반장: 담당 라인만  ← 검증 로직 동일
```

### ATM에는 없던, 스마트팩토리에서 새로 필요한 것들 (확장 포인트)

1. **실시간 센서 연동** — ATM은 관리자가 수동으로 상태를 바꾸는 방식이었지만,
   로봇은 센서가 이상을 감지하는 즉시 서버로 알려야 함 (`POST /api/robot/heartbeat`,
   `POST /api/robot/error` 같은 자동 전송 방식으로 구현 방향 설계).
2. **안전 이벤트(SafetyEvent)** — 사람과 로봇이 같은 공간에서 일하므로 일반
   장애와 분리해서 관리. 충돌 감지 시 "안전이벤트 INSERT + 로봇 즉시 오류정지
   UPDATE + 반경 내 작업자 경고 알림"을 하나의 트랜잭션으로 묶는 설계.
3. **WebSocket 실시간 반영** — ATM은 새로고침해야 갱신됐지만, 로봇이 쓰러지는
   순간 관리자 화면에 즉시 표시되어야 하므로 Flask-SocketIO로 `factory_{id}`
   room에 실시간 push (아래 7장 참고).
4. **로봇/사람 작업 비율(자동화율) 통계** — 저장하지 않고 조회 시 `SUM(CASE
   WHEN worker_type='ROBOT' THEN 1 ELSE 0 END)`으로 동적 계산하는 패턴.
5. **SQL 성능 — 날짜 조건은 범위 비교로**: `WHERE DATE(t.거래일시) >= ...`처럼
   컬럼에 함수를 씌우면 인덱스가 무력화됨. `WHERE t.발생시각 >= '2024-01-01
   00:00:00'`처럼 범위 비교로 작성해야 인덱스를 탐 (100만 건 기준 체감 가능한
   차이). WorkLog 관련 조회에 전부 이 원칙을 적용함.
6. **SQL 성능 — 동적 필터 패턴**: `WHERE (%s IS NULL OR col = %s)` 패턴은
   옵티마이저가 실행계획을 잡기 어렵게 만듦. `robot_dao._build_robot_search_conditions()`,
   `worklog_dao`의 검색 함수들처럼 조건이 있을 때만 Python에서 WHERE절을 동적으로
   조립하는 패턴을 사용함.
7. **뷰(View)로 반복 JOIN 제거**: 매 쿼리마다 `Robot JOIN Line JOIN Factory`를
   복붙하는 대신 `Robot_View`, `SafetyEvent_View`로 미리 정의(4장).
8. **트리거(Trigger)로 DB 레벨 상태 보정**: 어떤 경로(API/직접 쿼리/배치 작업)로
   데이터가 바뀌든 상태가 항상 일관되게 유지되도록 `battery_status_update`,
   `robot_error_status` 트리거로 구현(5장). — 이 원칙이 10장에서 라인장애
   연쇄 트리거를 추가로 만든 근거이기도 함.

---

## 3. DB 설계 — DDL

테이블 9개: `Factory`, `Line`, `Robot`, `Admin`, `WorkLog`, `RobotError`,
`LineError`, `Maintenance`, `SafetyEvent`. FK 계층은 `Robot → Line → Factory`
순서로 타고 올라가는 구조입니다 (SafetyEvent/WorkLog/RobotError/Maintenance는
모두 `robot_id`로 Robot을 참조).

```sql
CREATE TABLE Factory (
  factory_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  location VARCHAR(200),
  created_at DATETIME DEFAULT NOW()
);

CREATE TABLE Line (
  line_id INT AUTO_INCREMENT PRIMARY KEY,
  factory_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  status ENUM('가동중', '정지', '점검중') DEFAULT '가동중',
  created_at DATETIME DEFAULT NOW(),
  FOREIGN KEY (factory_id) REFERENCES Factory(factory_id)
);

CREATE TABLE Robot (
  robot_id INT AUTO_INCREMENT PRIMARY KEY,
  line_id INT NOT NULL,
  model_name VARCHAR(100) NOT NULL,
  battery_level INT NOT NULL,
  joint_wear INT NOT NULL,
  status ENUM('가동중', '충전중', '오류정지', '점검중') DEFAULT '가동중',
  warning_threshold INT NOT NULL DEFAULT 20,
  installed_at DATETIME DEFAULT NOW(),
  FOREIGN KEY (line_id) REFERENCES Line(line_id)
);

CREATE TABLE Admin (
  admin_id INT AUTO_INCREMENT PRIMARY KEY,
  factory_id INT,                 -- 슈퍼(공장장)일 때만 값, 일반이면 NULL
  line_id INT,                    -- 일반(라인 반장)일 때만 값, 슈퍼면 NULL
  name VARCHAR(100) NOT NULL,
  login_id VARCHAR(100) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL, -- 해시 저장 (pbkdf2:sha256, werkzeug)
  role ENUM('슈퍼', '일반') NOT NULL,
  created_at DATETIME DEFAULT NOW(),
  FOREIGN KEY (factory_id) REFERENCES Factory(factory_id),
  FOREIGN KEY (line_id) REFERENCES Line(line_id)
);

CREATE TABLE WorkLog (
  log_id INT AUTO_INCREMENT PRIMARY KEY,
  robot_id INT NOT NULL,
  work_type VARCHAR(100) NOT NULL,
  worker_type ENUM('ROBOT', 'HUMAN') NOT NULL,
  started_at DATETIME DEFAULT NOW(),
  ended_at DATETIME,              -- 시작 시점엔 NULL, 종료 시 UPDATE
  FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
);

CREATE TABLE RobotError (
  error_id INT AUTO_INCREMENT PRIMARY KEY,
  robot_id INT NOT NULL,
  error_type ENUM('센서이상', '충돌', '낙상', '과부하', '통신오류') NOT NULL,
  detail VARCHAR(100) NOT NULL,
  status ENUM('미처리', '완료') NOT NULL,
  occurred_at DATETIME DEFAULT NOW(),
  FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
);

CREATE TABLE LineError (
  error_id INT AUTO_INCREMENT PRIMARY KEY,
  line_id INT NOT NULL,
  cause ENUM('설비고장', '전력이상', '원자재부족', '안전사고', '기타') NOT NULL,
  status ENUM('미처리', '완료') NOT NULL DEFAULT '미처리',
  occurred_at DATETIME DEFAULT NOW(),
  FOREIGN KEY (line_id) REFERENCES Line(line_id)
);

CREATE TABLE Maintenance (
  maint_id INT AUTO_INCREMENT PRIMARY KEY,
  robot_id INT NOT NULL,
  part_name VARCHAR(100) NOT NULL,
  maint_type ENUM('정기점검', '부품교체', '사고후점검') NOT NULL,
  performed_at DATETIME DEFAULT NOW(),
  FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
);

CREATE TABLE SafetyEvent (
  event_id INT AUTO_INCREMENT PRIMARY KEY,
  robot_id INT NOT NULL,
  event_type ENUM('충돌감지', '낙상', '비상정지', '접근경고') NOT NULL,
  location VARCHAR(100) NOT NULL,
  nearby_workers INT NOT NULL DEFAULT 0,
  status ENUM('미처리', '완료') NOT NULL,
  occurred_at DATETIME DEFAULT NOW(),
  FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
);
```

설계 당시 자주 나온 실수와 원칙(면접에서 "설계하며 배운 것" 답변으로 쓸 수 있는
지점들):

- `INT(100)`은 "100짜리 정수"가 아니라 의미 없는 표시폭 — `INT`만 쓰고 값 범위
  제한(0~100)은 백엔드/CHECK 제약에서 처리.
- `role`처럼 값의 종류가 고정된 컬럼은 `VARCHAR`가 아니라 `ENUM`으로 — 오타로
  잘못된 값이 들어가는 걸 DB 레벨에서 원천 차단.
- `Admin.factory_id`/`line_id`는 서로 배타적으로 하나만 채워지므로 반드시
  `NOT NULL`을 빼야 함 — 안 그러면 슈퍼 계정 생성 시 없는 `line_id`를 강제로
  채워야 하는 모순이 생김.
- `login_id`엔 `UNIQUE` 필수(중복 계정 방지), `password`는 해시값(bcrypt/pbkdf2
  기준 60자 이상) 저장을 고려해 `VARCHAR(255)`.
- `occured_at`이 아니라 `occurred_at` (r 두 개) — 스펠링 실수 하나가 이후 모든
  쿼리·DAO 코드에 전파되므로 설계 단계에서 잡아야 함.

### ⚠️ 설계와 실제 DB의 차이 — `LineError.cause` (ENUM) vs `error_type` (VARCHAR)

위 DDL 문서(튜터링 단계)에는 `LineError.cause`가 `ENUM('설비고장', '전력이상',
'원자재부족', '안전사고', '기타')`로 설계되어 있습니다. 하지만 이번 검증 작업에서
실제 GitHub 저장소 코드와 실 DB를 확인한 결과, 배포된 스키마에는 이 컬럼이
**`error_type` (자유 문자열, VARCHAR)** 로 되어 있었습니다 — 설계 문서 작성 이후
실제 구현 단계에서 컬럼명·타입이 바뀐 것으로 보입니다. 9장 이후에서 작성한
`dao/error_dao.py`의 `create_line_error()`도 실제 스키마에 맞춰 `error_type`
컬럼을 사용합니다. (RobotError와 이름을 통일하려는 의도였을 가능성이 높음 —
면접에서 "설계와 구현이 갈린 지점"을 묻는다면 이 사례를 실제 예시로 들 수 있음.)

---

## 4. VIEW

반복되는 JOIN을 뷰로 미리 정의해서, 조회 코드를 단순화하고 JOIN 조건을 한 곳에서만
관리할 수 있게 함.

```sql
CREATE VIEW Robot_View AS
SELECT r.*, l.name AS line_name, l.status AS line_status,
       f.name AS factory_name, f.location AS factory_location
FROM Robot r
JOIN Line l ON r.line_id = l.line_id
JOIN Factory f ON l.factory_id = f.factory_id;

CREATE VIEW SafetyEvent_View AS
SELECT s.*, r.model_name, l.name AS line_name, f.name AS factory_name
FROM SafetyEvent s
JOIN Robot r ON s.robot_id = r.robot_id
JOIN Line l ON r.line_id = l.line_id
JOIN Factory f ON l.factory_id = f.factory_id;
```

JOIN 순서는 FK를 따라가는 것과 동일합니다: `SafetyEvent(robot_id) → Robot(line_id)
→ Line(factory_id) → Factory`. `ON` 뒤는 항상 "내 FK = 상대방 PK" 패턴.
`r.*` 처럼 전체 컬럼을 그대로 가져오면 `name` 같은 컬럼이 세 테이블에 중복으로
나오므로, Line/Factory 쪽은 필요한 컬럼만 `AS`로 별칭을 붙여 구분합니다.

`Robot_View` 사용 예:

```sql
SELECT * FROM Robot_View WHERE status = '오류정지';
```

한 줄로 로봇 정보 + 라인명/라인상태 + 공장명/공장위치까지 JOIN 없이 조회됩니다.

---

## 5. TRIGGER (원본)

DB 설계 단계에서 만들어진 원본 트리거 2개입니다 (10장에서 버그를 발견하고
수정한 `battery_status_update`의 **수정 전** 버전이 이것입니다).

```sql
CREATE TRIGGER battery_status_update
BEFORE UPDATE ON Robot
FOR EACH ROW
BEGIN
  IF NEW.battery_level <= NEW.warning_threshold THEN
    SET NEW.status = '충전중';
  ELSE
    SET NEW.status = '가동중';
  END IF;
END;

CREATE TRIGGER robot_error_status
AFTER INSERT ON RobotError
FOR EACH ROW
BEGIN
  UPDATE Robot
  SET status = '오류정지'
  WHERE robot_id = NEW.robot_id;
END;
```

설계 원칙:

- `battery_status_update`는 **같은 테이블(Robot) 안에서** 값을 바꾸므로
  `BEFORE UPDATE` + `SET NEW.컬럼 = ...` 패턴을 씀 (`AFTER UPDATE`에서 같은
  테이블을 다시 `UPDATE`하면 트리거가 스스로를 재귀 호출하며 무한루프에 빠짐).
- `robot_error_status`는 **다른 테이블(Robot)을 건드리므로** `AFTER INSERT` +
  일반 `UPDATE` 문을 씀 (자기 자신을 수정하는 게 아니라서 무한루프 걱정이 없음).
- `NEW.컬럼명`은 방금 들어온/바뀐 새 값, `OLD.컬럼명`은 바뀌기 전 값.

> **10장에서 다룰 문제**: `battery_status_update`가 Robot에 대한
> **모든** UPDATE에서 무조건 배터리 기준으로 status를 재계산해버리기 때문에,
> `robot_error_status`가 `status='오류정지'`로 바꿔도 곧바로 이 트리거가 덮어써서
> 되돌려버리는 상호작용 버그가 있었습니다. 이 트리거들이 서로 어떻게 얽혀있는지,
> 그리고 실제로 어떻게 고쳤는지는 10장에서 자세히 다룹니다.

---

## 6. INDEX

인덱스는 100만 건 규모로 쌓이는 `WorkLog` 테이블에 걸었습니다 (오류/안전이벤트는
가끔 생기지만, 작업 이력은 로봇 100대 × 하루 100번 작업 기준 연간 300만 건 이상
쌓이는 테이블이라 조회 성능이 가장 중요함).

```sql
CREATE INDEX idx_worklog_robot ON WorkLog(robot_id);
CREATE INDEX idx_worklog_date  ON WorkLog(started_at);
```

`work_type`에는 **의도적으로 인덱스를 걸지 않았습니다.** 이유는 카디널리티
(cardinality, 컬럼 값의 다양성)입니다.

- `robot_id`, `started_at` → 값의 종류가 매우 다양함 → 인덱스 효과 최고
- `work_type` → 값이 몇 개(조립/용접/이송 등 3~4개) 안 됨 → 인덱스를 타도 결국
  전체의 상당 부분을 스캔해야 해서 실효성이 낮음(SQLD에서 다루는 "낮은
  카디널리티 컬럼엔 인덱스 효과가 적다" 원칙)

`log_id`(PK)는 자동으로 인덱스가 생성되므로 별도로 만들 필요가 없습니다.

---

## 7. Flask 애플리케이션 구조

```
요청 → app.py가 URL 보고 Blueprint(robot/worklog/error/admin) 결정
     → routes/*.py (URL ↔ service 연결만, 비즈니스 로직 없음)
     → service/*.py (비즈니스 로직: 페이지네이션, 플래그 가공, socketio 발송 등)
     → dao/*.py (raw SQL, pymysql, try/finally로 연결 종료 보장)
     → DB
```

### 공통 인프라 파일

- **`app.py`** — `create_app()`에서 Flask 앱 생성, `socketio.init_app(app)`,
  `SECRET_KEY`(세션 서명용) 설정, Blueprint 4개 등록
  (`robot_bp`/`worklog_bp`/`error_bp`는 `url_prefix='/api'`, `admin_bp`는
  prefix 없이 루트 — HTML 로그인 폼을 반환하기 때문). `/`, `/errors`,
  `/worklogs` 페이지 라우트에 `@login_required` 적용.
- **`extensions.py`** — `socketio = SocketIO(async_mode='threading')`. 순환
  참조를 피하려고 `app.py`와 분리된 독립 파일로 둠.
- **`db.py`** — `get_connection()`이 매 호출마다 새 pymysql 연결을 반환.
  `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`/`DB_SSL_CA` 환경변수
  기반으로 로컬(MariaDB, SSL 불필요)과 Aiven(MySQL, SSL 필수)을 `.env` 파일
  하나만 바꿔서 전환. `DictCursor` 사용 — 조회 결과가 튜플이 아니라 `dict`로
  나와서 `row['robot_id']`처럼 접근 가능.
- **`auth.py`** (10단계, 로그인/권한) — `get_current_admin()`(세션에서 로그인
  정보 조회), `login_required`(비로그인 시 `/api`는 401 JSON, 페이지는 로그인
  폼으로 redirect — 요청 경로로 두 경우를 구분), `apply_scope(admin, filters)`
  (역할별로 `line_id`/`factory_id`를 서버가 강제로 덮어써서, 클라이언트가 쿼리
  파라미터를 조작해도 스코프 밖 데이터가 새어나가지 않게 함).

### 라우트 계층 (대표 엔드포인트)

| Blueprint | 대표 엔드포인트 | 비고 |
|---|---|---|
| `robot_bp` (`/api`) | `GET /robots`, `/robots/<id>`, `/robots/line/<id>`, `/robots/status/<status>`, `/robots/search` | `search`는 `@login_required` + `apply_scope` 적용, 페이지네이션 응답(`data/page/per_page/total_count/total_pages`) |
| `worklog_bp` (`/api`) | `GET /worklogs/robot/<id>`, `/worklogs/date`, `/worklogs/stats/robot`, `/worklogs/stats/line`, `/worklogs/search` | 통계류(`stats/*`)는 DB에서 이미 `GROUP BY`로 집계된 결과를 그대로 반환 |
| `error_bp` (`/api`) | `GET /errors/robot/<id>`, `POST /errors/robot`, `GET /errors/line/<id>`, `POST /errors/analyze/robot/<id>`, `POST /errors/analyze/batch` | `POST /errors/robot`은 등록 후 `robot_error_status` 트리거가 자동으로 로봇 상태를 반영 |
| `admin_bp` (prefix 없음) | `GET/POST /login`, `POST /logout` | HTML 폼을 반환하므로 `/api` prefix 밖에 별도 등록 |

- 페이지네이션 응답 형태(`{data, page, per_page, total_count, total_pages}`)를
  robot/worklog/error 세 도메인의 `search` 계열 API 전부 동일하게 통일함
  (`_paginate()` 헬퍼를 각 service 파일에 동일 패턴으로 둠).
- 검색류 API(`/robots/search`, `/worklogs/search`, `/errors/robot/search`,
  `/errors/line/search`)는 전부 조건이 있을 때만 WHERE절에 동적으로 추가하는
  패턴(`_build_robot_search_conditions()` 등)을 공유함 — `WHERE (%s IS NULL OR
  col=%s)` 같은 옵티마이저에 불리한 패턴 대신, Python에서 조건 리스트를 조립.

### Claude API 연동 — `service/claude_service.py` (AI 에러 로그 분석)

- **역할**: `RobotError` 데이터를 Claude API에 보내 원인 분석/심각도/권장 조치를
  JSON으로 받아 `ErrorAnalysis` 테이블에 저장. DB 접근은 여전히 `error_dao`가
  담당하고, 이 파일은 프롬프트 생성 + API 호출 + 응답 파싱만 담당.
- **두 가지 모드**:
  - `analyze_robot(robot_id)` — 로봇 1대의 에러 이력 전체를 분석 (individual)
  - `analyze_unresolved_batch(limit=30)` — 미해결 에러 전체(최근 N건)를 한 번에
    분석해서 전체 경향을 파악 (batch)
- 응답은 항상 `{summary, root_cause, severity, recommendation}` 형태의 순수
  JSON만 받도록 프롬프트에서 강제하고, 코드블록(` ```json `)이 섞여 와도
  `_parse_response()`에서 벗겨냄. 파싱 실패 시에도 서버가 죽지 않도록 원본
  텍스트를 `summary`에 방어적으로 채워서 반환.
- `ErrorAnalysis` 테이블(정확한 DDL 문서는 없고, `error_dao.create_error_analysis()`
  호출부 기준): `analysis_type`(individual/batch), `robot_id`(batch면 NULL),
  `target_count`, `summary`, `root_cause`, `severity`, `recommendation`,
  `raw_response`.

### 실시간 알림 — Flask-SocketIO

로봇 오류/라인장애가 발생하면 관리자 화면에 새로고침 없이 즉시 반영되도록
공장 단위 room(`factory_{factory_id}`)에 이벤트를 push합니다 (2장의 확장
포인트 3번 설계를 실제로 구현한 부분). 10장에서 추가한 `line_error` 이벤트도
이 패턴을 그대로 재사용했습니다.

---

## 8. 시스템 규모(더미 데이터)

`insert_dummy.py` / `insert_dummy_error.py` 기준 실제 생성되는 더미 데이터
규모입니다 (9장에서 포트폴리오 문서와 대조 검증해 전부 일치함을 확인함).

| 테이블 | 규모 |
|---|---|
| Factory | 3개 |
| Line | 15개 |
| Robot | 75대 |
| WorkLog | 약 100만 건 |
| RobotError | 500건 |
| LineError | 150건 |
| Maintenance | 300건 |
| SafetyEvent | 100건 |

---

## 9. 검증 배경 — 포트폴리오 문서 재검증 (2026-08-21)

여기까지가 원래 설계이고, 여기서부터는 그 설계가 실제로 얼마나 구현되어 있는지를
2026-08-21에 다시 검증하고 빠진 부분을 채운 기록입니다. ATM ↔ 스마트팩토리
도메인 대응표(2장)와 시스템 규모 표(8장)를 실제 GitHub 저장소
코드(`julienne0335-lab/smart-factory-monitoring`)와 대조 검증한 결과:

- **시스템 규모(공장 3개, 라인 15개, 로봇 75대, WorkLog 100만 건, RobotError
  500건, LineError 150건, Maintenance 300건, SafetyEvent 100건)** — 전부
  `insert_dummy.py` / `insert_dummy_error.py`의 실제 숫자와 정확히 일치함.
- **도메인 대응표 대부분** — 로봇/라인/공장 계층, 배터리·경고임계값 트리거,
  RobotError → 로봇 오류정지 자동 전환, WorkLog(작업 수행 이력·자행/타행
  구분), 슈퍼/일반 관리자 권한 분리(`auth.py`의 `apply_scope`), SafetyEvent
  등은 실제 코드로 확인됨.
- **다만 세 항목은 "설계만 있고 구현은 안 된" 상태였음**:
  1. 은행장애 ↔ 공장 전체 비상정지(화재·정전) — Factory 테이블에 상태
     컬럼 자체가 없어서 미구현 (이번 작업 범위에서 제외하기로 결정)
  2. 수수료 통계 ↔ 작업별 에너지 비용·소요시간 집계 — 소요시간은 있었지만
     에너지 비용은 전혀 없었음
  3. 지점장애 ↔ 라인 전체 가동 중단 — LineError를 "등록"하는 API 자체가
     없었고, 등록되더라도 라인/로봇 상태에 연쇄 반영되는 로직이 없었음

이 중 **2번(에너지 비용 통계)과 3번(라인장애 연쇄 처리)** 을 구현하기로
결정하고, 아래 내용을 실제로 만들어 로컬 DB에서 동작까지 검증했습니다.
1번(공장 비상정지)은 스키마 변경 폭 대비 실익이 낮다고 판단해 이번 범위에서
제외했습니다.

---

## 10. 구현 1 — 라인장애 연쇄 처리 ("지점장애 ↔ 라인 전체 가동 중단")

### 발견한 선행 버그 — battery_status_update 트리거

기존 `battery_status_update` 트리거는 Robot 테이블에 어떤 UPDATE가 오든
(배터리가 실제로 바뀌지 않았어도) 무조건 배터리 기준으로 status를
재계산해서 덮어쓰고 있었습니다. 그 결과 `robot_error_status` 트리거가
`UPDATE Robot SET status='오류정지'`를 실행해도, 이 BEFORE UPDATE 트리거가
곧바로 재실행되면서 배터리가 충분한 로봇은 status가 다시 `'가동중'`으로
되돌아가버리는 **silent failure**가 있었습니다. 즉 지금까지 RobotError를
등록해도 배터리가 낮은 로봇이 아니면 실제로는 오류정지 상태가 잘 안
됐을 가능성이 높습니다. (5장에 있는 원본 트리거와 비교하면 문제
지점이 바로 보입니다.)

새로 추가하는 라인장애 연쇄 트리거도 로봇 status를 직접 UPDATE하므로 이
버그를 고치지 않으면 똑같이 무력화됩니다. 그래서 `IF NEW.battery_level <>
OLD.battery_level` 조건을 추가해, **배터리 값 자체가 실제로 바뀔 때만**
배터리 기준 로직이 개입하도록 수정했습니다. (면접에서 "구현하다 발견한
버그가 있나요?"에 실제 사례로 쓸 수 있는 지점입니다.)

### 변경/추가 파일

| 파일 | 내용 |
|---|---|
| `sql/trigger_setup.sql` | 트리거 4개: `battery_status_update`(버그 수정), `robot_error_status`(기존 유지), `line_error_cascade`(신규), `line_error_resolve`(신규) |
| `dao/error_dao.py` | `create_line_error()`, `resolve_line_error()`, `get_factory_id_by_line()` 추가 |
| `service/error_service.py` | `create_line_error()`, `resolve_line_error()` 추가 (socketio `'line_error'` 이벤트 포함) |
| `routes/error.py` | `POST /api/errors/line`, `POST /api/errors/line/<id>/resolve` 추가 |

### 동작 방식

- `POST /api/errors/line` (body: `line_id`, `error_type`)로 라인 에러 등록
  → `line_error_cascade` 트리거가 같은 트랜잭션 안에서 자동으로
  `Line.status='정지'` + 그 라인 소속 로봇 전체를 `'오류정지'`로 반영
  (구조_.pdf 8절의 트랜잭션 원자성 패턴 그대로 구현 — AFTER INSERT
  트리거이므로 트리거 내부 실패 시 원본 INSERT도 롤백됨)
- `POST /api/errors/line/<error_id>/resolve`로 처리완료 표시
  → `line_error_resolve` 트리거가 `Line.status='가동중'`으로 복구, 오류정지
  상태였던 로봇을 배터리 기준으로 되돌림
- 로봇 개별 RobotError는 만들지 않음 — RobotError.error_type ENUM에
  "라인장애로 인한 연쇄정지"에 해당하는 값이 없고, 로봇이 스스로 감지한
  오류가 아니므로 Robot.status만 직접 반영하는 쪽이 의미상 더 정확하다고
  판단함
- 로봇 에러와 동일하게 socketio `'line_error'` 이벤트를 공장 room에 발송
  (프론트 `realtime.js`에 핸들러 추가는 이번 범위 밖 — 필요 시 추가 작업)

### 알려진 한계

Robot 테이블에는 "왜 오류정지가 됐는지"(개별 로봇 오류 vs 라인장애)를
구분하는 컬럼이 없어서, `line_error_resolve`는 그 라인에서 **현재
`'오류정지'`인 로봇 전체**를 복구 대상으로 봅니다. 같은 라인의 다른 로봇이
라인장애와 무관하게 개별 RobotError로 오류정지된 상태였다면, 라인장애가
처리완료될 때 그 로봇도 함께 복구되어버릴 수 있습니다. 더 정확히 하려면
Robot에 "정지 원인" 컬럼을 추가해야 하는데, 지금 스키마 범위 안에서는
이 정도가 현실적인 절충점으로 판단했습니다.

---

## 11. 구현 2 — 에너지 비용 통계 ("수수료 통계 ↔ 작업별 에너지 비용 집계")

### 변경 파일

| 파일 | 내용 |
|---|---|
| `dao/worklog_dao.py` | `WORK_TYPE_POWER_KW` / `COST_PER_KWH_WON` 상수, `_work_type_power_case_sql()` 추가. 기존 `get_worklog_stats_by_robot()` / `get_worklog_stats_by_line()`에 `total_energy_cost_won` 필드 추가. 신규 `get_worklog_stats_by_work_type()` 추가 |
| `service/worklog_service.py` | `get_worklog_stats_by_work_type()` 추가 |
| `routes/worklog.py` | `GET /api/worklogs/stats/work_type` 추가 |

### 계산 방식

작업시간(분) → 시간(h) 환산 후 work_type별 예상 kW를 곱해 kWh를 구하고,
`COST_PER_KWH_WON`(150원/kWh)을 곱해 원화로 환산 → SQL `SUM()`으로 집계.
`/api/worklogs/stats/robot`, `/api/worklogs/stats/line`,
`/api/worklogs/stats/work_type` 세 가지 축으로 각각 조회 가능.

### ⚠️ 중요 — 추정치입니다

로봇 전력 사용량을 재는 센서/계량 장비는 이 프로젝트에 없습니다.
`WORK_TYPE_POWER_KW`(작업 유형별 kW)와 `COST_PER_KWH_WON`은 산업용
로봇팔의 일반적인 소비전력 범위와 산업용 전력 요금대를 참고해서 **어림잡은
예시 값**입니다. 실제 계량 데이터가 아니라 "어떤 작업/로봇/라인이
상대적으로 전력을 많이 쓰는가"를 비교하기 위한 통계 목적의 근사치라는 점을
발표·이력서·면접에서 반드시 함께 밝혀야 합니다.

---

## 12. DB에 적용하기 (HeidiSQL 기준)

### ⚠️ HeidiSQL의 DELIMITER 이슈

`sql/trigger_setup.sql`을 통째로 "전체 실행"(F9)하면, HeidiSQL이 `DELIMITER`
지시어를 제대로 못 알아듣고 트리거 본문 안의 세미콜론(`;`)에서 문장을
잘라버려서 `SQL 오류 (1064)`가 발생합니다. (실제로 이 문제를 겪었고, 아래
방법으로 해결했습니다.)

그래서 `sql/trigger_setup.sql`은 `DELIMITER` 없이, 각 트리거를 일반 세미콜론
하나로 끝나는 완전한 문장으로 다시 작성했고, 파일 안에 **STEP 0~5**로
구간을 나눠뒀습니다.

**적용 순서:**
1. HeidiSQL에서 대상 DB(로컬 또는 Aiven) 연결
2. `sql/trigger_setup.sql`을 쿼리 탭에 로드
3. **STEP 0** (`DROP TRIGGER IF EXISTS` 4줄)을 마우스로 통째로 드래그 선택 → F9
4. **STEP 1 ~ STEP 4**를 각각 `CREATE TRIGGER ...`부터 그 아래 `END;`까지
   통째로 선택 → F9 (총 4번, 절대 전체 실행하지 말고 블록 단위로)
5. 확인:
   ```sql
   SHOW TRIGGERS FROM smart_factory;
   ```
   `battery_status_update`, `robot_error_status`, `line_error_cascade`,
   `line_error_resolve` 4개가 나오면 성공.

(터미널에서 `mysql -u root -p smart_factory < sql/trigger_setup.sql`로 실행하는
경우는 DELIMITER 없이도 문제없이 한 번에 실행됩니다 — mysql 클라이언트는
세미콜론 처리를 다르게 하기 때문.)

### 로컬 DB와 Aiven(배포 DB)은 완전히 별개

`git push`는 **코드**만 GitHub/배포 플랫폼(Render 등)에 반영할 뿐, DB
트리거처럼 데이터베이스 서버 안에 저장된 객체는 절대 건드리지 못합니다.
**로컬에 트리거를 적용한 것과 Aiven에 적용하는 것은 완전히 별개의 작업이며,
둘 다 각각 위 STEP 0~4 과정을 따로 실행해야 합니다.** 코드만 push하고
Aiven에 트리거를 안 넣으면, 배포된 앱에서 `POST /api/errors/line`은
성공하지만 Line/Robot 상태는 조용히 안 바뀌는 상황이 생깁니다.

---

## 13. 로컬/Aiven 계정 로그인 아이디 불일치

`scripts/insert_dummy_admin.py`는 대상 DB를 옵션으로 구분합니다.

```
python scripts/insert_dummy_admin.py           → 기본 .env 사용 (로컬 MariaDB)
python scripts/insert_dummy_admin.py --aiven   → .env.aiven 사용 (Aiven MySQL)
```

로컬 DB의 login_id가 `서울_super`처럼 한글로 저장돼 있던 건, 로그인
아이디를 로마자로 매핑하는 코드가 추가되기 **이전** 버전으로 로컬에
한 번 실행했었고, Aiven은 그 이후 고친 버전으로 `--aiven` 옵션을 붙여
따로 실행했기 때문입니다. 로컬을 Aiven과 맞추려면:

```sql
DELETE FROM Admin;
```
(로컬 DB에서 실행 — login_id가 UNIQUE라 기존 값이 남아있으면 재실행 시
IntegrityError 발생)

```
python scripts/insert_dummy_admin.py
```
(옵션 없이 — 로컬로 들어감)

---

## 14. 실제 검증 결과 (2026-08-21 기준)

- `SHOW TRIGGERS FROM smart_factory;` → 트리거 4개 전부 생성 확인
- `POST /api/errors/line {"line_id": 1, "error_type": "전력이상"}` →
  `error_id: 151`로 정상 등록 확인
- `Line.status`(line_id=1) → `'정지'`로 자동 전환 확인
- `Robot.status`(line_id=1 소속 로봇 전체) → `'오류정지'`로 자동 전환 확인
- `GET /api/worklogs/stats/robot` → `total_energy_cost_won` 필드 정상
  포함 확인 (예: robot_id 54 → 약 1,327만 원, 작업 13,276건, 평균
  94.75분/건)

라인장애 연쇄 처리(등록 → 연쇄 반영)와 에너지 비용 통계 모두 로컬
환경에서 실제 동작 검증이 끝난 상태입니다. (처리완료 → 복구 왕복,
Aiven 반영은 각자 환경에서 12~13장 절차대로 진행)

---

## 15. Git 커밋

```bash
git status
git add dao/error_dao.py dao/worklog_dao.py service/error_service.py service/worklog_service.py routes/error.py routes/worklog.py sql/trigger_setup.sql
git commit -m "라인장애 연쇄 처리(LineError cascade) + 에너지 비용 통계 추가, battery_status_update 트리거 버그 수정"
git push
```

## 16. 배포 체크리스트

- [ ] 로컬 DB에 `sql/trigger_setup.sql` 적용 (완료)
- [ ] Aiven DB에 `sql/trigger_setup.sql` 적용 (STEP 0~4, HeidiSQL Aiven 연결로)
- [ ] 위 커밋 push (Render 등 자동배포 트리거)
- [ ] 배포된 URL에서 로그인 → `POST /errors/line` 테스트로 최종 확인
- [ ] (선택) `realtime.js`에 `socket.on('line_error', ...)` 핸들러 추가
- [ ] (선택) 포트폴리오 문서(`포트폴리오_면접준비_최종본.md`)의 "구현 완료"
      목록에 이번 두 항목 반영

---

## 17. 확장 1 — MQTT 가상 센서 시뮬레이터 (2026-08-22)

포트폴리오 14장은 "진짜 스마트팩토리로 발전시킨다면"이라는 확장 방향을
설계 수준으로만 정리해두고, 실제로 구현·검증한 기록은 아니라고 스스로
밝혀둔 장이었습니다. 14.9절 우선순위표에서 난이도가 가장 낮다고 판단한
1번(가상 센서 시뮬레이터 + MQTT)을 실제로 로컬에서 구현하고 끝까지
검증한 기록입니다.

### 환경 준비

로컬에 Docker·Mosquitto가 전혀 없는 상태였습니다. winget으로 Eclipse
Mosquitto(v2.1.2)를 설치했는데, 설치 과정에서 Windows 서비스로 자동
등록되어 기본 설정 그대로 `localhost:1883`에서 익명 pub/sub을 즉시
허용한다는 걸 확인했습니다(`mosquitto_pub`/`mosquitto_sub`로 직접
확인). 그래서 프로젝트 전용 `mosquitto/mosquitto.conf`를 만들어두긴
했지만(브로커가 서비스로 안 떠 있는 환경을 위한 대비용), 실제 검증은
이미 떠 있는 Windows 서비스를 그대로 사용했습니다.

### 변경/추가 파일

| 파일 | 내용 |
|---|---|
| `mqtt_bridge.py` (신규) | MQTT 구독 클라이언트. `factory/robot/sensor` 토픽을 구독해 `robot_service.apply_sensor_reading()`으로 넘김 |
| `scripts/mqtt_sensor_simulator.py` (신규) | 로봇 75대의 배터리·관절마모 값을 점진적으로 변화시키며 1초 간격으로 발행하는 가상 센서 |
| `mosquitto/mosquitto.conf` (신규) | 로컬 브로커를 수동 실행해야 할 때를 위한 프로젝트 전용 설정 |
| `dao/robot_dao.py` | `update_robot_sensors()`, `get_factory_id_by_robot()` 추가 |
| `service/robot_service.py` | `apply_sensor_reading()` 추가 (5단계 `error_service.create_robot_error()`와 동일한 "DAO 반영 → 공장 조회 → 그 공장 room에만 emit" 3단계 패턴) |
| `app.py` | `__main__` 블록에서 reloader 자식 프로세스에만 MQTT 브리지를 시작하도록 연결 |
| `requirements.txt` | `paho-mqtt` 추가 |

### 동작 방식

```
scripts/mqtt_sensor_simulator.py (발행자)
  → MQTT 브로커(Mosquitto, localhost:1883)
    → mqtt_bridge.py (구독자, app.py 시작 시 백그라운드 스레드로 붙음)
      → robot_service.apply_sensor_reading(robot_id, battery, wear)
        ① robot_dao.update_robot_sensors() — Robot.battery_level/joint_wear UPDATE
           └─ battery_level이 실제로 바뀌면 battery_status_update 트리거가
              status를 '가동중'/'충전중'으로 자동 재계산 (15.2절에서 버그 수정된 그 트리거)
        ② robot_dao.get_factory_id_by_robot() — 어느 공장 room으로 보낼지 조회
        ③ socketio.emit('robot_sensor_update', {...}, room=f"factory_{factory_id}")
```

시뮬레이터는 로봇별로 배터리 상태를 들고 있다가 매 tick 1~4씩 깎고,
`warning_threshold`(20) 이하로 떨어지면 80~100으로 "재충전"시키는 방식으로
값을 만듭니다. 완전 랜덤이 아니라 이렇게 점진적으로 변화시킨 이유는, 배터리가
실제로 threshold를 넘나들어야 `battery_status_update` 트리거의 상태 전환을
눈으로 확인할 수 있기 때문입니다.

### 발견한 버그 1 — `python app.py`가 reloader 때문에 두 번 실행되는 문제

`app.py`는 `app = create_app()`을 모듈 최상단(= `if __name__` 가드 **밖**)에서
실행합니다. `socketio.run(app, debug=True)`가 Werkzeug reloader를 켜면, 이
reloader는 "감시하는 부모 프로세스"와 "실제로 서빙하는 자식 프로세스"를
따로 띄우는데, **부모 프로세스도 reloader가 켜지기 전에 이미 `create_app()`을
한 번 실행한 상태**입니다. `create_app()` 안에서 MQTT 구독을 시작해버리면
부모·자식 양쪽에서 각각 브로커에 붙어 센서값이 두 번씩 처리될 위험이
있습니다.

`WERKZEUG_RUN_MAIN` 환경변수만으로는 "reloader 없이 그냥 한 번 실행되는
경우"와 "reloader의 부모 프로세스(아직 자식을 못 띄운 시점)"를 구분할 수
없다는 게 까다로운 지점이었습니다(둘 다 이 값이 비어 있음). 그래서
MQTT 브리지 시작 코드를 `create_app()`에서 빼내 `if __name__ == '__main__':`
블록 안으로 옮기고, 거기서 `WERKZEUG_RUN_MAIN == 'true'`(reloader 자식)
이거나 `DEBUG`가 꺼져 있을 때(reloader 자체가 없는 경우)만 시작하도록
했습니다. 부수 효과로, gunicorn으로 배포하는 환경(Render)에서는
`__main__` 블록이 아예 안 돌기 때문에 MQTT 브리지가 시작되지 않는데 —
이건 의도된 동작입니다. 14장 전체가 "로컬에서 아키텍처를 검증한다"는
틀이었고, Render에는 애초에 로컬 브로커가 없습니다.

### 발견한 버그 2 — "로봇이 존재하지 않는다"는 오판 (rowcount 함정)

가장 값진 발견이었습니다. `update_robot_sensors()`가 `cursor.rowcount > 0`으로
"이 robot_id가 실제로 존재하는가"를 판단하게 짰는데, 시뮬레이터를 돌리자마자
`robot_id=13` 근처에서 실제로 존재하는 로봇을 "존재하지 않음"으로 오판하는
게 재현됐습니다.

원인은 MySQL(PyMySQL)의 `UPDATE` `rowcount` 의미론이었습니다.
**"조건에 매칭된 행 수"가 아니라 "실제로 값이 바뀐 행 수"** 입니다.
`battery_level`은 `INT` 컬럼인데 센서가 보내는 값은 float(예: 93.1)라서
DB에 저장되며 반올림되고, 그 반올림된 값이 우연히 직전 저장값과 같아지는
순간(예: 92.6 → 93 저장, 다음 tick에 93.4 → 93 저장) `rowcount`가 0이
되어버립니다. 이 로봇은 멀쩡히 존재하고 값도 정상적으로 반영됐는데도
"존재하지 않는다"고 오판한 것 — **3.7·6.4·15.2절에서 반복된 "조용히
실패하는 버그" 계보에 새로 추가된 사례**입니다(패턴은 다르지만 "값이
바뀌었는지"와 "행이 존재하는지"를 혼동했다는 점에서 근본적으로 같은
종류의 함정입니다).

수정: `update_robot_sensors()`는 존재 여부를 판단하지 않고 UPDATE만
수행하도록 단순화하고, `robot_service.apply_sensor_reading()`이 UPDATE
이후 `get_robot_by_id()`로 다시 조회해서 `None`이면 "존재하지 않음"으로
판단하도록 바꿨습니다. 3.4절에 이미 있던 "없으면 None" 패턴을 그대로
재사용한 것이라, 새로운 개념을 도입하지 않고 기존 관례로 되돌아가는 방식으로
고쳤습니다.

### 발견한 버그 3 — Windows 콘솔 인코딩이 백그라운드 스레드를 죽임

버그 2를 겪는 과정에서 더 심각한 2차 문제를 발견했습니다. "존재하지
않음" 로그 메시지에 쓴 em dash(`—`, U+2014) 문자를, `python app.py`를
표준출력을 파일로 리디렉션해 실행했을 때의 기본 인코딩(cp949, 한글
Windows)이 인코딩하지 못해 `UnicodeEncodeError`가 발생했습니다.

이 예외는 MQTT 콜백(`paho-mqtt`의 백그라운드 네트워크 스레드) 안에서
발생한 것이라 아무도 잡아주지 않았고, 그 스레드 자체가 죽어버렸습니다.
겉보기엔 Flask 앱도 멀쩡히 떠 있고 에러 traceback도 로그에 남지만,
**그 이후로 들어오는 모든 센서값이 조용히 유실**되는 상황이었습니다 —
버그 2(rowcount 오판)가 없었다면 이 문제는 한참 뒤에나 (실제로 존재하지
않는 robot_id가 들어왔을 때) 우연히 드러났을 잠재 버그였습니다.

수정: `mqtt_bridge.py`와 `mqtt_sensor_simulator.py` 양쪽 모두 시작 부분에서
`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`를 호출해,
콘솔이 표현 못 하는 문자를 만나도 예외 대신 대체 문자로 흘려보내도록
했습니다. 백그라운드 스레드의 로그 한 줄 때문에 파이프라인 전체가
말없이 멈추는 것보다는, 문자가 깨져 보이더라도 계속 동작하는 쪽이
안전하다고 판단했습니다.

### 실제 검증 결과 (2026-08-22, 로컬 환경 기준)

- `mosquitto_pub`/`mosquitto_sub`로 로컬 브로커 익명 pub/sub 직접 확인
- `python app.py` 실행 → `mqtt_bridge.py`가 정확히 한 번만 구독 시작
  (Werkzeug reloader로 4번 재시작해봐도 매번 한 번씩만 재구독됨 — 중복 없음)
- `scripts/mqtt_sensor_simulator.py` 실행 → 로봇 1~12 등 다수의
  `battery_level`/`joint_wear`가 DB에 실시간 반영됨을 직접 조회로 확인
- `mosquitto_pub`으로 `robot_id=1`에 `battery_level=15`(threshold 이하)
  발행 → 이어서 `battery_level=90` 발행 → 최종 조회 결과
  `{'robot_id': 1, 'battery_level': 90, 'joint_wear': 41, 'status': '가동중'}`
  으로, `battery_status_update` 트리거가 두 값 모두에 대해 올바르게
  상태를 재계산했음을 확인
- `robot_id=9999`(존재하지 않음) 발행 → 예외 없이
  `[mqtt] robot_id=9999 존재하지 않음 — 무시` 로그만 남기고 다음
  메시지 계속 처리됨을 확인 (버그 3 수정 검증)

### 알려진 한계

- `robot_sensor_update` socketio 이벤트를 프론트(`realtime.js`, 대시보드)가
  아직 구독하지 않습니다 — 지금은 DB 반영과 이벤트 발송까지만 검증했고,
  화면에 실시간으로 배터리 그래프를 그리는 건 이번 범위 밖입니다.
- `joint_wear`(관절 마모도)는 시뮬레이터에서 계속 누적만 되고 리셋되지
  않습니다. 실제로는 `Maintenance`(정비 이력) 등록 시 마모도가 초기화돼야
  하는데, 이번 확장은 그 연결까지는 만들지 않았습니다.
- 이 파이프라인은 `python app.py`로 로컬 실행할 때만 동작하며, Render
  배포 환경에는 연결하지 않았습니다(위 "발견한 버그 1" 참고) — 14장이
  원래 "하드웨어 없이 로컬에서 아키텍처를 검증한다"고 밝힌 범위 그대로입니다.

### Git 커밋

```bash
git add mqtt_bridge.py scripts/mqtt_sensor_simulator.py mosquitto/ \
        dao/robot_dao.py service/robot_service.py app.py requirements.txt \
        README.md docs/DEVLOG.md
git commit -m "MQTT 가상 센서 시뮬레이터 추가 (14.2절 확장) — battery_status_update 트리거 연동, rowcount 오판/콘솔 인코딩 크래시 버그 수정"
git push
```
