import pymysql
import random
from datetime import datetime, timedelta

# ─────────────────────────────────────────
# 1. DB 연결
#    - host: 로컬 MariaDB 서버
#    - charset: 한글 깨짐 방지
# ─────────────────────────────────────────
conn = pymysql.connect(
    host='127.0.0.1',
    user='root',           # MariaDB 유저명
    password='030609',     # 비밀번호
    database='smart_factory',
    charset='utf8mb4' 
)

cursor = conn.cursor()
print("DB 연결 성공!")


# ─────────────────────────────────────────
# 2. Factory 데이터 삽입
#    - 3개 공장 (서울/자동차, 부산/반도체, 인천/식품)
#    - executemany(): 리스트를 한 번에 INSERT
# ─────────────────────────────────────────
factories = [
    ('서울공장', '서울시 강남구'),
    ('부산공장', '부산시 해운대구'),
    ('인천공장', '인천시 남동구'),
]

cursor.executemany(
    "INSERT INTO factory (name, location) VALUES (%s, %s)",
    factories
)
conn.commit()
print(f"Factory {len(factories)}개 삽입 완료!")


# ─────────────────────────────────────────
# 3. Line 데이터 삽입
#    - 공장당 5개 라인, 총 15개
#    - factory_id: 1~3 (FK → factory 테이블)
#    - range(1, 4): 1, 2, 3 → 공장 3개
#    - range(1, 6): 1, 2, 3, 4, 5 → 라인 5개
# ─────────────────────────────────────────
lines = []
for factory_id in range(1, 4):      # 공장 1~3
    for i in range(1, 6):           # 라인 1~5
        lines.append((factory_id, f'{i}번 라인'))

cursor.executemany(
    "INSERT INTO line (factory_id, name) VALUES (%s, %s)",
    lines
)
conn.commit()
print(f"Line {len(lines)}개 삽입 완료!")


# ─────────────────────────────────────────
# 4. Robot 데이터 삽입
#    - 라인당 5개 로봇, 총 75개
#    - line_id: 1~15 (FK → line 테이블)
#    - battery_level: 50~100 (신규 로봇 기준)
#    - joint_wear: 0~50 (신규 로봇 기준)
#    - status, warning_threshold, installed_at → DEFAULT값 사용, 생략
# ─────────────────────────────────────────
robots = []
for line_id in range(1, 16):        # 라인 1~15
    for i in range(1, 6):           # 로봇 1~5
        robots.append((
            line_id,
            f'RB-{i}',
            random.randint(50, 100),  # battery_level
            random.randint(0, 50)     # joint_wear
        ))

cursor.executemany(
    "INSERT INTO robot (line_id, model_name, battery_level, joint_wear) VALUES (%s, %s, %s, %s)",
    robots
)
conn.commit()
print(f"Robot {len(robots)}개 삽입 완료!")


# ─────────────────────────────────────────
# 5. WorkLog 데이터 삽입 (100만 건)
#
#    [공장별 work_type 구분]
#    - robot_id  1~25 : 서울공장(자동차) 소속
#    - robot_id 26~50 : 부산공장(반도체) 소속
#    - robot_id 51~75 : 인천공장(식품)  소속
#
#    [배치 처리]
#    - 한 번에 100만 건을 메모리에 올리면 터질 수 있음
#    - BATCH_SIZE = 10,000건씩 나눠서 100번 INSERT
#    - 총 왕복 횟수: 100번 (단건 INSERT의 1/10000)
#
#    [변수 설명]
#    - work_types: 딕셔너리 {range: [작업목록]}
#      key = robot_id 범위(range), value = 작업 목록(list)
#    - worker_types: ROBOT 또는 HUMAN
#    - started_at: 2024년 중 랜덤 날짜
#    - ended_at: 작업 시작 후 10분~3시간 사이 랜덤 종료
# ─────────────────────────────────────────
work_types = {
    range(1, 26):  ['용접', '도장', '조립', '품질검사', '부품이송'],       # 서울(자동차)
    range(26, 51): ['웨이퍼절삭', '노광', '식각', '세정', '검사'],         # 부산(반도체)
    range(51, 76): ['원료투입', '가공', '포장', '살균', '출하검사'],        # 인천(식품)
}

worker_types = ['ROBOT', 'HUMAN']

BATCH_SIZE = 10000    # 한 번에 INSERT할 건수
TOTAL = 1000000       # 총 INSERT할 건수

for batch in range(TOTAL // BATCH_SIZE):   # 0~99, 총 100번 반복
    logs = []

    for _ in range(BATCH_SIZE):            # 언더스코어(_): 변수가 필요 없을 때 관례적으로 사용
        robot_id = random.randint(1, 75)

        # robot_id가 어느 공장 범위인지 찾아서 해당 work_type 선택
        for id_range, types in work_types.items():
            if robot_id in id_range:
                work_type = random.choice(types)
                break

        # 2024년 중 랜덤 날짜/시간
        started_at = datetime(2024, 1, 1) + timedelta(
            days=random.randint(0, 365),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )

        # 작업 시간: 10분 ~ 3시간(180분) 랜덤
        ended_at = started_at + timedelta(minutes=random.randint(10, 180))

        logs.append((
            robot_id,
            work_type,
            random.choice(worker_types),  # ROBOT or HUMAN
            started_at,
            ended_at
        ))

    # 1만 건씩 배치 INSERT
    cursor.executemany(
        "INSERT INTO worklog (robot_id, work_type, worker_type, started_at, ended_at) VALUES (%s, %s, %s, %s, %s)",
        logs
    )
    conn.commit()
    print(f"{(batch + 1) * BATCH_SIZE:,}건 삽입 완료...")  # :, → 천 단위 콤마 표시

print("WorkLog 100만 건 삽입 완료!")


# ─────────────────────────────────────────
# 6. 연결 종료
#    - cursor와 connection 모두 닫아야 함
#    - 안 닫으면 DB 연결이 계속 점유됨
# ─────────────────────────────────────────
cursor.close()
conn.close()
print("DB 연결 종료!")