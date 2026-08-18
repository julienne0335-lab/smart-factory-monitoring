"""
insert_dummy_error.py — RobotError / LineError / Maintenance / SafetyEvent 더미 데이터 생성
──────────────────────────────────────────────────────────────────────────────
[역할]
  6단계(Claude API 에러 로그 분석)를 위한 재료용 더미 데이터를 생성한다.
  WorkLog(100만 건)처럼 대량이 아니라, 분석 프롬프트에 넣을 "적당한 분량"만 생성한다.

[전제]
  - Factory(3) / Line(15) / Robot(75)까지는 insert_dummy.py로 이미 생성되어 있어야 함
  - HeidiSQL DESCRIBE 결과 기준으로 실제 컬럼/ENUM 값에 맞춤:
      RobotError  : error_id, robot_id, error_type(ENUM), detail(VARCHAR, NULL 허용),
                    status(ENUM '미처리'/'완료', 기본 '미처리'), occurred_at
      LineError   : error_id, line_id, error_type(VARCHAR),
                    status(ENUM '미처리'/'완료'), occurred_at
      Maintenance : maint_id, robot_id, part_name(VARCHAR),
                    maint_type(ENUM), performed_at
      SafetyEvent : event_id, robot_id, event_type(ENUM), location(VARCHAR),
                    nearby_workers(INT), status(ENUM '미처리'/'완료'), occurred_at

[중요 — status 값 주의]
  실제 DB ENUM은 '미처리' / '완료' 임 (error_dao.py 안의 'pending'과 다름!).
  더미 데이터는 반드시 '미처리' / '완료'로 넣는다.
  → DAO/Service의 영어 status 문자열은 6단계에서 별도로 맞춰야 함 (여기서는 안 건드림).

[트리거 참고]
  RobotError INSERT 시 robot_error_status 트리거가 Robot.status를 건드리려 하지만,
  같은 UPDATE가 battery_status_update(BEFORE UPDATE) 트리거를 재발동시켜
  battery_level 기준으로 status가 다시 계산됨. 즉 이 스크립트에서 Robot.status를
  별도로 보정해줄 필요는 없음 (트리거끼리 알아서 상호작용함).
"""

import pymysql
import random
from datetime import datetime, timedelta

# ─────────────────────────────────────────
# 1. DB 연결 (insert_dummy.py와 동일한 설정)
# ─────────────────────────────────────────
conn = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='030609',     # ← 본인 비밀번호로 변경
    database='smart_factory',
    charset='utf8mb4'
)
cursor = conn.cursor()
print("DB 연결 성공!")

# ─────────────────────────────────────────
# 공통: 최근 6개월 범위 안에서 랜덤 datetime 생성
#   - WorkLog(2024년 전체)와 달리, 에러/점검 데이터는
#     "최근 모니터링 데이터"라는 컨셉이라 최근 180일로 한정
# ─────────────────────────────────────────
NOW = datetime(2026, 8, 17)


def random_recent_datetime(days_back=180):
    delta_days = random.randint(0, days_back)
    delta_seconds = random.randint(0, 86399)
    return NOW - timedelta(days=delta_days, seconds=delta_seconds)


# 상태값: 완료가 더 많고 미처리가 적은 게 현실적 (70% 완료 / 30% 미처리)
def random_status():
    return random.choices(['완료', '미처리'], weights=[70, 30], k=1)[0]


# ─────────────────────────────────────────
# 2. RobotError 더미 데이터 (500건)
#    - error_type별로 그럴듯한 detail 문구를 매칭해서 현실감 부여
#    - robot_id: 1~75 (FK → Robot)
# ─────────────────────────────────────────
ROBOT_ERROR_COUNT = 500

robot_error_types = ['센서이상', '충돌', '낙상', '과부하', '통신오류']

robot_error_details = {
    '센서이상': ['근접 센서 값 이상 감지', '온도 센서 응답 없음', '비전 센서 초점 불량'],
    '충돌':     ['라인 A 구간 장애물 충돌', '반대편 로봇과 경로 간섭', '컨베이어 벨트 접촉 충돌'],
    '낙상':     ['균형 제어 실패로 넘어짐', '바닥 단차에서 낙상 감지'],
    '과부하':   ['관절 모터 과부하 감지', '허용 하중 초과 적재', '연속 작업으로 인한 과열'],
    '통신오류': ['제어 서버와 통신 타임아웃', 'CAN 통신 패킷 유실', '네트워크 응답 지연'],
}

robot_errors = []
for _ in range(ROBOT_ERROR_COUNT):
    robot_id = random.randint(1, 75)
    error_type = random.choice(robot_error_types)
    detail = random.choice(robot_error_details[error_type])
    status = random_status()
    occurred_at = random_recent_datetime()

    robot_errors.append((robot_id, error_type, detail, status, occurred_at))

cursor.executemany(
    """INSERT INTO RobotError (robot_id, error_type, detail, status, occurred_at)
       VALUES (%s, %s, %s, %s, %s)""",
    robot_errors
)
conn.commit()
print(f"RobotError {len(robot_errors)}건 삽입 완료!")


# ─────────────────────────────────────────
# 3. LineError 더미 데이터 (150건)
#    - error_type은 VARCHAR라 자유롭게 넣되, 의미 있는 값으로 통일
#    - line_id: 1~15 (FK → Line)
# ─────────────────────────────────────────
LINE_ERROR_COUNT = 150

line_error_types = ['설비고장', '전력이상', '원자재부족', '안전사고', '기타']

line_errors = []
for _ in range(LINE_ERROR_COUNT):
    line_id = random.randint(1, 15)
    error_type = random.choice(line_error_types)
    status = random_status()
    occurred_at = random_recent_datetime()

    line_errors.append((line_id, error_type, status, occurred_at))

cursor.executemany(
    """INSERT INTO LineError (line_id, error_type, status, occurred_at)
       VALUES (%s, %s, %s, %s)""",
    line_errors
)
conn.commit()
print(f"LineError {len(line_errors)}건 삽입 완료!")


# ─────────────────────────────────────────
# 4. Maintenance 더미 데이터 (300건)
#    - part_name: 로봇 부품 후보 중 랜덤
#    - maint_type: ENUM('정기점검','부품교체','사고후점검')
#    - robot_id: 1~75 (FK → Robot)
# ─────────────────────────────────────────
MAINTENANCE_COUNT = 300

part_names = ['배터리', '관절 모터', '근접 센서', '비전 카메라', '그리퍼', '팔 액추에이터', '컨트롤 보드']
maint_types = ['정기점검', '부품교체', '사고후점검']

maintenances = []
for _ in range(MAINTENANCE_COUNT):
    robot_id = random.randint(1, 75)
    part_name = random.choice(part_names)
    maint_type = random.choice(maint_types)
    performed_at = random_recent_datetime()

    maintenances.append((robot_id, part_name, maint_type, performed_at))

cursor.executemany(
    """INSERT INTO Maintenance (robot_id, part_name, maint_type, performed_at)
       VALUES (%s, %s, %s, %s)""",
    maintenances
)
conn.commit()
print(f"Maintenance {len(maintenances)}건 삽입 완료!")


# ─────────────────────────────────────────
# 5. SafetyEvent 더미 데이터 (100건)
#    - event_type: ENUM('충돌감지','낙상','비상정지','접근경고')
#    - nearby_workers: 0~5명
#    - robot_id: 1~75 (FK → Robot)
# ─────────────────────────────────────────
SAFETY_EVENT_COUNT = 100

event_types = ['충돌감지', '낙상', '비상정지', '접근경고']
locations = ['A구역', 'B구역', 'C구역', '컨베이어 인근', '적재 구역', '출하 게이트']

safety_events = []
for _ in range(SAFETY_EVENT_COUNT):
    robot_id = random.randint(1, 75)
    event_type = random.choice(event_types)
    location = random.choice(locations)
    nearby_workers = random.randint(0, 5)
    status = random_status()
    occurred_at = random_recent_datetime()

    safety_events.append((
        robot_id, event_type, location, nearby_workers, status, occurred_at
    ))

cursor.executemany(
    """INSERT INTO SafetyEvent
       (robot_id, event_type, location, nearby_workers, status, occurred_at)
       VALUES (%s, %s, %s, %s, %s, %s)""",
    safety_events
)
conn.commit()
print(f"SafetyEvent {len(safety_events)}건 삽입 완료!")


# ─────────────────────────────────────────
# 6. 연결 종료
# ─────────────────────────────────────────
cursor.close()
conn.close()
print("DB 연결 종료! 더미 데이터 생성 완료 🎉")