"""
worklog_dao.py — WorkLog 테이블 DB 접근 계층 (DAO)
──────────────────────────────────────────────────────────────────────
[역할]
  WorkLog 테이블에 대한 모든 DB 쿼리를 담당함.
  WorkLog는 100만 건의 작업 기록을 가지고 있으며,
  기본 조회 함수와 집계/JOIN 등 복잡한 쿼리 함수로 나뉨.

[WorkLog 테이블 주요 컬럼]
  - robot_id     : 작업한 로봇 ID (FK)
  - work_type    : 작업 종류 (공장별로 다름)
  - worker_type  : 작업 주체 ("robot" or "human")
  - started_at   : 작업 시작 시간
  - ended_at     : 작업 종료 시간

[참고]
  robot_id가 있어도 worker_type이 "human"일 수 있음
  → 로봇 오류 시 사람이 개입하거나 협업하는 경우
"""

from db import get_connection


# ── 기본 조회 함수 ──────────────────────────────────────────────────

def get_worklogs_by_robot(robot_id, limit=100, offset=0):
    """
    특정 로봇의 작업 기록을 페이지 단위로 반환한다.

    [페이지네이션을 왜 추가했나 — Locust 부하 테스트에서 발견]
      원래는 LIMIT 없이 전체를 다 반환했음. 로봇 1대의 작업 기록이
      평균 13,000건이 넘어서(100만 건 ÷ 75대), 응답 크기가 평균 2.64MB나
      나왔고, 무료 티어 서버에서 이걸 만들어서 보내는 데만 14~20초가
      걸렸음(Locust 측정 결과). LIMIT/OFFSET으로 "한 번에 최대 limit건만"
      가져오도록 바꿔서, 응답 크기와 시간을 확 줄임.

    [파라미터]
      robot_id (int): 조회할 로봇의 ID
      limit    (int): 한 페이지에 가져올 최대 건수 (기본 100)
      offset   (int): 몇 번째 행부터 시작할지 (기본 0 = 처음부터)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM WorkLog
            WHERE robot_id = %s
            ORDER BY started_at DESC
            LIMIT %s OFFSET %s
            """,
            (robot_id, limit, offset)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def count_worklogs_by_robot(robot_id):
    """
    특정 로봇의 작업 기록 전체 건수를 반환한다.
    - 페이지네이션 응답에 total_count / total_pages를 계산해서
      넣어주기 위해 필요함
    - SELECT * 대신 COUNT(*)만 쓰면 실제 행 데이터를 안 가져오므로 훨씬 빠름
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM WorkLog WHERE robot_id = %s",
            (robot_id,)
        )
        return cursor.fetchone()['cnt']
    finally:
        conn.close()

def get_worklogs_by_work_type(work_type):
    """
    특정 작업 종류의 작업 기록을 반환한다.

    [파라미터]
      work_type (str): 조회할 작업 종류
        예) "welding", "assembly", "inspection" 등

    [반환값]
      list of dict: 해당 work_type의 작업 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM WorkLog WHERE work_type = %s", (work_type,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_worklogs_by_worker_type(worker_type):
    """
    특정 작업 주체의 작업 기록을 반환한다.

    [파라미터]
      worker_type (str): 조회할 작업 주체
        - "robot" : 로봇이 수행한 작업
        - "human" : 사람이 개입한 작업

    [반환값]
      list of dict: 해당 worker_type의 작업 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM WorkLog WHERE worker_type = %s", (worker_type,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_worklogs_by_date(start_date, end_date, limit=100, offset=0):
    """
    특정 날짜 범위의 작업 기록을 페이지 단위로 반환한다.
    - 이유는 get_worklogs_by_robot과 동일 (1주일치만 조회해도 평균 3.77MB, 15~24초)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM WorkLog
            WHERE started_at BETWEEN %s AND %s
            ORDER BY started_at DESC
            LIMIT %s OFFSET %s
            """,
            (start_date, end_date, limit, offset)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def count_worklogs_by_date(start_date, end_date):
    """특정 날짜 범위의 작업 기록 전체 건수를 반환한다 (total_pages 계산용)"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM WorkLog WHERE started_at BETWEEN %s AND %s",
            (start_date, end_date)
        )
        return cursor.fetchone()['cnt']
    finally:
        conn.close()


def get_recent_worklogs(n):
    """
    최근 N건의 작업 기록을 반환한다.

    [파라미터]
      n (int): 가져올 작업 기록 건수

    [반환값]
      list of dict: 최근 순으로 정렬된 N건의 작업 기록

    [참고]
      ORDER BY started_at DESC → 최근 순(내림차순) 정렬
      LIMIT %s → 상위 N건만 반환

    [사용 예시]
      get_recent_worklogs(10)  → 최근 10건
      get_recent_worklogs(100) → 최근 100건
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM WorkLog ORDER BY started_at DESC LIMIT %s",
            (n,)
        )
        return cursor.fetchall()
    finally:
        conn.close()


# ── 복잡한 쿼리 함수 (집계/JOIN) ────────────────────────────────────

def get_worklog_stats_by_robot():
    """
    로봇별 작업 통계를 반환한다.

    [반환값]
      list of dict: 로봇별 총 작업 건수 + 평균 작업시간(분)
      예) [{"robot_id": 1, "total_count": 150, "avg_minutes": 45.0}, ...]

    [활용]
      모니터링 대시보드에서 어떤 로봇이 가장 많이/적게 일했는지,
      작업시간이 비정상적으로 긴 로봇은 없는지 파악할 때 사용.

    [참고]
      COUNT(*)                          → 작업 건수
      AVG(TIMESTAMPDIFF(...))           → 평균 작업시간 (분 단위)
      TIMESTAMPDIFF(MINUTE, a, b)       → a~b 사이의 분 단위 차이
      GROUP BY robot_id                 → 로봇별로 집계
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT robot_id,
                   COUNT(*) AS total_count,
                   AVG(TIMESTAMPDIFF(MINUTE, started_at, ended_at)) AS avg_minutes
            FROM WorkLog
            GROUP BY robot_id
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def get_worklog_stats_by_line():
    """
    라인별 작업 통계를 반환한다.

    [반환값]
      list of dict: 라인별 총 작업 건수 + 평균 작업시간(분)
      예) [{"line_id": 1, "total_count": 500, "avg_minutes": 38.0}, ...]

    [활용]
      어느 라인이 가장 바쁜지, 라인별 작업 효율을 비교할 때 사용.

    [참고]
      WorkLog에는 line_id가 없어서 Robot 테이블과 JOIN 필요!
      WorkLog → robot_id → Robot → line_id 순서로 연결
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.line_id,
                   COUNT(*) AS total_count,
                   AVG(TIMESTAMPDIFF(MINUTE, w.started_at, w.ended_at)) AS avg_minutes
            FROM WorkLog w
            JOIN Robot r ON w.robot_id = r.robot_id
            GROUP BY r.line_id
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def get_worklogs_with_details():
    """
    WorkLog + Robot + Line 정보를 JOIN하여 반환한다.

    [반환값]
      list of dict: 작업 기록 + 로봇 이름 + 라인 이름
      예) [{"worklog_id": 1, "robot_name": "Robot-01",
            "line_name": "Line-A", "work_type": "welding", ...}, ...]

    [활용]
      작업 기록 상세 조회 시 로봇/라인 정보를 함께 보여줄 때 사용.
      robot_id만 있으면 "몇 번 라인 로봇인지" 또 찾아야 하므로
      JOIN으로 한번에 가져오는 게 효율적.

    [참고]
      WorkLog(w) → Robot(r): w.robot_id = r.robot_id
      Robot(r)   → Line(l) : r.line_id  = l.line_id
      r.status vs l.status처럼 같은 컬럼명이 있을 수 있어서
      테이블 별칭(w, r, l)으로 명확히 구분함.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT w.worklog_id, r.robot_name, l.line_name,
                   w.work_type, w.started_at, w.ended_at
            FROM WorkLog w
            JOIN Robot r ON w.robot_id = r.robot_id
            JOIN Line l ON l.line_id = r.line_id
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def get_long_worklogs(min_minutes):
    """
    작업시간이 N분 이상인 작업 기록을 반환한다.

    [파라미터]
      min_minutes (int): 최소 작업시간 (분 단위)

    [반환값]
      list of dict: 작업시간이 min_minutes 이상인 작업 기록

    [활용]
      비정상적으로 오래 걸린 작업을 감지할 때 사용.
      예) 평균 30분짜리 작업이 2시간 넘으면 → 이상 징후!

    [사용 예시]
      get_long_worklogs(120) → 2시간 이상 걸린 작업 조회
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM WorkLog
            WHERE TIMESTAMPDIFF(MINUTE, started_at, ended_at) >= %s
        """, (min_minutes,))
        return cursor.fetchall()
    finally:
        conn.close()

# ── 통합 검색 함수 (여러 필터 조합 + 페이지네이션) ──────────────────

def search_worklogs(robot_id=None, line_id=None, factory_id=None, work_type=None,
                     worker_type=None, start_date=None, end_date=None, min_minutes=None,
                     limit=100, offset=0):
    """
    여러 조건을 동시에 조합해서 작업 로그를 페이지 단위로 검색한다.
    (get_worklogs_by_robot()/get_worklogs_by_date()와 동일하게 limit/offset 방식)

    [파라미터] (전부 선택적 — None/빈값이면 해당 조건은 무시됨)
      robot_id     (int) : 특정 로봇으로 좁히기
      line_id      (int) : 특정 라인으로 좁히기
      factory_id   (int) : 특정 공장으로 좁히기
      work_type    (str) : 작업 유형 (예: "조립")
      worker_type  (str) : 작업 주체 ("ROBOT" 또는 "HUMAN")
      start_date   (str) : 시작 날짜 (end_date와 "함께" 넘겨야 조건이 걸림)
      end_date     (str) : 종료 날짜
      min_minutes  (int) : 이 시간(분) 이상 걸린 작업만
      limit, offset       : 페이지네이션

    [반환값]
      list of dict — 조건에 맞는 작업 로그 (이번 페이지 분량만).
      Robot/Line을 항상 JOIN하므로 line_id/factory_id가 결과에 항상
      같이 찍혀서, 필터가 실제로 걸렸는지 응답만 보고 검증할 수 있음.
      전체 건수는 count_search_worklogs()로 별도 조회

    [주의: SQL 인젝션 안전성]
      아래 f-string은 컬럼명/테이블명 같은 "고정된 SQL 조각"만 조립하고,
      실제 값(robot_id, work_type 등)은 전부 %s 자리표시자를 통해
      pymysql이 안전하게 이스케이프 처리함. 사용자 입력값이 f-string
      안에 직접 들어가는 일은 없음.
    """
    where_clause, from_clause, params = _build_worklog_search_conditions(
        robot_id, line_id, factory_id, work_type, worker_type,
        start_date, end_date, min_minutes
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = f"""
            SELECT w.*, r.line_id, l.factory_id {from_clause} {where_clause}
            ORDER BY w.started_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        return cursor.fetchall()
    finally:
        conn.close()


def count_search_worklogs(robot_id=None, line_id=None, factory_id=None, work_type=None,
                           worker_type=None, start_date=None, end_date=None, min_minutes=None):
    """search_worklogs()와 동일한 조건의 전체 건수를 반환한다 (total_pages 계산용)"""
    where_clause, from_clause, params = _build_worklog_search_conditions(
        robot_id, line_id, factory_id, work_type, worker_type,
        start_date, end_date, min_minutes
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) AS cnt {from_clause} {where_clause}", params)
        return cursor.fetchone()['cnt']
    finally:
        conn.close()


def _build_worklog_search_conditions(robot_id, line_id, factory_id, work_type, worker_type,
                                      start_date, end_date, min_minutes):
    """
    search_worklogs() / count_search_worklogs()가 공통으로 쓰는 WHERE절 조립 로직.
    조건절 문자열 조립 코드가 두 함수에 중복되지 않도록 여기로 뺐다.

    [반환값]
      (where_clause, from_clause, params) 튜플
    """
    conditions = []
    params = []

    if robot_id is not None:
        conditions.append("w.robot_id = %s")
        params.append(robot_id)

    if line_id is not None:
        conditions.append("r.line_id = %s")
        params.append(line_id)

    if factory_id is not None:
        conditions.append("l.factory_id = %s")
        params.append(factory_id)

    if work_type:
        conditions.append("w.work_type = %s")
        params.append(work_type)

    if worker_type:
        conditions.append("w.worker_type = %s")
        params.append(worker_type)

    # 날짜는 start/end 둘 다 있을 때만 BETWEEN 조건을 건다
    if start_date and end_date:
        conditions.append("w.started_at BETWEEN %s AND %s")
        params.append(start_date)
        params.append(end_date)

    if min_minutes is not None:
        conditions.append("TIMESTAMPDIFF(MINUTE, w.started_at, w.ended_at) >= %s")
        params.append(min_minutes)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # 항상 Robot, Line 둘 다 JOIN한다 (line_id/factory_id 조건 여부와 무관하게).
    # 예전엔 line_id 조건이 있을 때만 Robot을 JOIN해서 응답에 line_id가
    # 안 찍혔고, factory_id는 아예 가져올 방법이 없었음. Robot(75행),
    # Line(3행) 둘 다 아주 작은 테이블이라 JOIN 비용이 무시할 수준이라,
    # 항상 두 단계(WorkLog→Robot→Line)까지 JOIN해서 결과에 line_id와
    # factory_id를 같이 포함시키는 쪽으로 통일함. (로봇 검색의
    # search_robots()와 동일한 설계)
    from_clause = (
        "FROM WorkLog w "
        "JOIN Robot r ON w.robot_id = r.robot_id "
        "JOIN Line l ON r.line_id = l.line_id"
    )

    return where_clause, from_clause, params