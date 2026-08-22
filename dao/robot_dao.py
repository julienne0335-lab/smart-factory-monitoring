"""
robot_dao.py — Robot 테이블 DB 접근 계층 (DAO)
──────────────────────────────────────────────────────────────────────
[역할]
  DAO(Data Access Object): DB에 직접 쿼리를 날려 데이터를 가져오거나
  수정하는 계층. 비즈니스 로직은 service 계층에서 처리하고,
  여기서는 오직 DB 쿼리만 담당함.

[패턴]
  모든 함수는 아래 패턴을 따름:
    1. get_connection()으로 DB 연결
    2. try 블록에서 쿼리 실행
    3. finally 블록에서 연결 종료 (예외가 발생해도 반드시 닫힘)

[참고]
  - fetchall(): 여러 행을 리스트로 반환
  - fetchone(): 한 행만 반환
  - %s: pymysql 플레이스홀더 (값을 SQL에 안전하게 삽입)
  - (robot_id,): 값이 하나인 튜플 (쉼표 필수!)
"""

from db import get_connection


def get_all_robots():
    """
    전체 로봇 목록을 반환한다.

    [반환값]
      list of dict: 모든 로봇 정보
      예) [{"robot_id": 1, "status": "active", ...}, ...]
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Robot")
        return cursor.fetchall()
    finally:
        conn.close()


def get_robot_by_id(robot_id):
    """
    특정 로봇 하나의 상세 정보를 반환한다.

    [파라미터]
      robot_id (int): 조회할 로봇의 ID

    [반환값]
      dict: 해당 로봇의 정보 (없으면 None)
      예) {"robot_id": 1, "status": "active", "battery_level": 80, ...}

    [참고]
      WHERE robot_id = %s → 특정 로봇 하나만 필터링
      fetchone() → 결과가 하나이므로 단건 반환
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Robot WHERE robot_id = %s", (robot_id,))
        return cursor.fetchone()
    finally:
        conn.close()


def get_robots_by_line(line_id):
    """
    특정 라인에 속한 로봇 목록을 반환한다.

    [파라미터]
      line_id (int): 조회할 라인의 ID

    [반환값]
      list of dict: 해당 라인의 로봇 목록
      예) [{"robot_id": 1, "line_id": 2, ...}, ...]

    [참고]
      라인당 로봇 5대이므로 최대 5개 반환
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Robot WHERE line_id = %s", (line_id,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_robots_by_status(status):
    """
    특정 상태의 로봇 목록을 반환한다.

    [파라미터]
      status (str): 조회할 상태값
        - "active"  : 정상 가동 중
        - "idle"    : 대기 중
        - "error"   : 오류 발생

    [반환값]
      list of dict: 해당 상태의 로봇 목록

    [사용 예시]
      get_robots_by_status("error")  → 현재 오류 상태인 로봇 전체 조회
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Robot WHERE status = %s", (status,))
        return cursor.fetchall()
    finally:
        conn.close()

# ── 통합 검색 함수 (여러 필터 조합 + 페이지네이션) ──────────────────

def search_robots(robot_id=None, line_id=None, factory_id=None, status=None,
                   max_battery=None, min_joint_wear=None,
                   limit=25, offset=0):
    """
    여러 조건을 동시에 조합해서 로봇을 페이지 단위로 검색한다.
    (worklog_dao.search_worklogs()와 동일한 설계: 조건절을 동적으로 조립)

    [파라미터] (전부 선택적 — None이면 해당 조건은 무시됨)
      robot_id       (int) : 특정 로봇 하나만
      line_id        (int) : 특정 라인으로 좁히기
      factory_id     (int) : 특정 공장으로 좁히기 (Line 테이블과 JOIN 필요)
      status         (str) : '가동중' / '충전중' / '오류정지' / '점검중'
      max_battery    (int) : 이 값 이하 배터리만 (예: 20 → 배터리 부족 로봇)
      min_joint_wear (int) : 이 값 이상 마모도만 (예: 80 → 점검 필요 로봇)
      limit, offset         : 페이지네이션 (다른 DAO 함수들과 이름 통일)

    [반환값]
      list of dict — 조건에 맞는 로봇 목록 (이번 페이지 분량만)
      전체 건수는 count_search_robots()로 별도 조회

    [참고]
      factory_id는 Robot 테이블에 없는 컬럼이라 Line과 JOIN해야만 필터링 가능.
      (Robot → line_id → Line → factory_id)
      다른 조건과 마찬가지로, factory_id가 안 넘어오면 JOIN 자체를 생략함.
    """
    where_clause, from_clause, params = _build_robot_search_conditions(
        robot_id, line_id, factory_id, status, max_battery, min_joint_wear
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = f"""
            SELECT r.* {from_clause} {where_clause}
            ORDER BY r.robot_id ASC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        return cursor.fetchall()
    finally:
        conn.close()


def count_search_robots(robot_id=None, line_id=None, factory_id=None, status=None,
                         max_battery=None, min_joint_wear=None):
    """search_robots()와 동일한 조건의 전체 건수를 반환한다 (total_pages 계산용)"""
    where_clause, from_clause, params = _build_robot_search_conditions(
        robot_id, line_id, factory_id, status, max_battery, min_joint_wear
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) AS cnt {from_clause} {where_clause}", params)
        return cursor.fetchone()['cnt']
    finally:
        conn.close()


def _build_robot_search_conditions(robot_id, line_id, factory_id, status,
                                    max_battery, min_joint_wear):
    """
    search_robots() / count_search_robots()가 공통으로 쓰는 WHERE절 조립 로직.
    조건절 문자열 조립 코드가 두 함수에 중복되지 않도록 여기로 뺐다.

    [반환값]
      (where_clause, from_clause, params) 튜플
    """
    conditions = []
    params = []

    if robot_id is not None:
        conditions.append("r.robot_id = %s")
        params.append(robot_id)

    if line_id is not None:
        conditions.append("r.line_id = %s")
        params.append(line_id)

    if factory_id is not None:
        conditions.append("l.factory_id = %s")
        params.append(factory_id)

    if status:
        conditions.append("r.status = %s")
        params.append(status)

    if max_battery is not None:
        conditions.append("r.battery_level <= %s")
        params.append(max_battery)

    if min_joint_wear is not None:
        conditions.append("r.joint_wear >= %s")
        params.append(min_joint_wear)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # factory_id 필터가 있을 때만 Line과 JOIN
    if factory_id is not None:
        from_clause = "FROM Robot r JOIN Line l ON r.line_id = l.line_id"
    else:
        from_clause = "FROM Robot r"

    return where_clause, from_clause, params


# ── 14.2절 확장: 센서 시뮬레이터(MQTT)가 보낸 값 반영 ──────────────────

def update_robot_sensors(robot_id, battery_level, joint_wear):
    """
    센서(시뮬레이터)가 보낸 battery_level/joint_wear 값을 Robot에 반영한다.

    [참고 1]
      status는 여기서 직접 건드리지 않는다 — battery_level이 이번 UPDATE로
      실제로 바뀌면 battery_status_update 트리거(15.2절에서 버그 수정됨)가
      BEFORE UPDATE 시점에 NEW.status를 알아서 재계산해 끼워넣는다.
      즉 이 함수는 "센서값만 갱신"하고, 상태 전환은 DB에 위임한다.

    [참고 2 — robot_id 존재 여부는 여기서 판단하지 않는다]
      처음엔 cursor.rowcount > 0으로 "존재하는 robot_id였는지"를 판단하려
      했으나, MySQL/PyMySQL의 UPDATE rowcount는 "조건에 매칭된 행 수"가
      아니라 "실제로 값이 바뀐 행 수"다. battery_level은 INT 컬럼이라 센서
      값(float)이 반올림되면서 직전 값과 우연히 같아지는 순간 rowcount가
      0이 되어, 로봇이 멀쩡히 존재하는데도 "없다"고 오판하는 반복 재현
      가능한 버그였다(3.7·6.4·15.2절의 "조용히 실패하는 버그" 계보에
      새로 추가된 사례). 그래서 존재 여부 판단은 이 함수가 하지 않고,
      호출자(robot_service.apply_sensor_reading)가 UPDATE 이후 다시
      get_robot_by_id()로 조회해서 판단한다 — 3.4절에 이미 있는
      "없으면 None" 패턴을 그대로 재사용하는 쪽이 더 안전하다.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE Robot
            SET battery_level = %s, joint_wear = %s
            WHERE robot_id = %s
            """,
            (battery_level, joint_wear, robot_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 정비(Maintenance) 등록 시 마모도 초기화 ─────────────────────────

def reset_joint_wear(robot_id):
    """
    정비 완료로 joint_wear(관절 마모도)를 0으로 초기화한다.
    - battery_level은 건드리지 않으므로 battery_status_update 트리거가
      끼어들어 status를 덮어쓰지 않는다 (14.2절 확장에서 같은 이유로
      확인된 패턴).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Robot SET joint_wear = 0 WHERE robot_id = %s",
            (robot_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_factory_id_by_robot(robot_id):
    """
    로봇이 소속된 공장(factory_id)을 조회한다.
    (error_dao.get_factory_id_by_robot()과 동일한 쿼리 — 센서 갱신 알림도
     "그 로봇이 속한 공장 room"으로만 보내야 해서 robot_dao에도 둔다.
     robot_service가 error_dao를 가져다 쓰는 계층 역방향 참조를 피하기
     위한 선택이며, 8.2절에서 이미 "약간의 중복 vs 계층 간 참조" 트레이드
     오프를 같은 방식으로 받아들인 전례가 있다.)

    [반환값]
      int: factory_id / None: 존재하지 않는 robot_id인 경우
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT l.factory_id
            FROM Robot r
            JOIN Line l ON r.line_id = l.line_id
            WHERE r.robot_id = %s
            """,
            (robot_id,),
        )
        row = cursor.fetchone()
        return row['factory_id'] if row else None
    finally:
        conn.close()