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