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

def get_worklogs_by_robot(robot_id):
    """
    특정 로봇의 작업 기록 전체를 반환한다.

    [파라미터]
      robot_id (int): 조회할 로봇의 ID

    [반환값]
      list of dict: 해당 로봇의 모든 작업 기록

    [사용 예시]
      get_worklogs_by_robot(5) → 5번 로봇의 작업 기록 전부 반환
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM WorkLog WHERE robot_id = %s", (robot_id,))
        return cursor.fetchall()
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


def get_worklogs_by_date(start_date, end_date):
    """
    특정 날짜 범위의 작업 기록을 반환한다.

    [파라미터]
      start_date (str): 시작 날짜 (예: "2024-01-01")
      end_date   (str): 종료 날짜 (예: "2024-12-31")

    [반환값]
      list of dict: 해당 기간의 작업 기록

    [참고]
      BETWEEN은 시작일과 종료일을 모두 포함함 (이상/이하)
      날짜 범위는 자유롭게 설정 가능 (하루치, 한달치, 1년치 등)

    [사용 예시]
      get_worklogs_by_date("2024-01-01", "2024-12-31") → 1년치
      get_worklogs_by_date("2024-01-01", "2024-01-31") → 1달치
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM WorkLog WHERE started_at BETWEEN %s AND %s",
            (start_date, end_date)
        )
        return cursor.fetchall()
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