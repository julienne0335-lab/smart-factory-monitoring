"""
productiontarget_dao.py — ProductionTarget 테이블 DB 접근 계층 (DAO)
──────────────────────────────────────────────────────────────────────
[역할]
  라인별/기간별 목표 생산량(ProductionTarget) 등록·조회를 담당한다.
  (3순위 MES-lite 확장 — "목표 생산량 대비 달성률" 기능의 저장소)

[테이블 구조]
  ProductionTarget: target_id, line_id, period_type, period_start, target_count, created_at
  - period_type ENUM: 'DAILY' / 'WEEKLY' / 'MONTHLY'
  - period_start: 그 기간의 시작일 (DAILY면 그날, WEEKLY면 그 주의 월요일,
                   MONTHLY면 1일 — 어느 날짜를 넣든 service 계층이 그 기간의
                   마지막 날을 계산해서 실적 집계 범위를 정함)
  - (line_id, period_type, period_start) UNIQUE — 같은 라인/기간에 목표를
    중복 등록할 수 없고, 다시 등록하면 값을 덮어씀 (UPSERT)
"""

from db import get_connection


def line_exists(line_id):
    """
    라인이 실제로 존재하는지 확인한다.
    - robot_dao.get_factory_id_by_robot() 등과 동일한 원칙: 계층 역방향
      참조(다른 도메인 DAO를 끌어오는 것)를 피하기 위해 이 파일 안에
      직접 조회 쿼리를 둔다.

    [반환값]
      bool
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT line_id FROM Line WHERE line_id = %s", (line_id,))
        return cursor.fetchone() is not None
    finally:
        conn.close()


def create_target(line_id, period_type, period_start, target_count):
    """
    라인의 기간별 목표 생산량을 등록한다. 이미 같은 (line_id, period_type,
    period_start) 조합이 있으면 target_count를 덮어쓴다 (UPSERT).

    [반환값]
      int: 생성/갱신된 target_id
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ProductionTarget (line_id, period_type, period_start, target_count)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE target_count = VALUES(target_count)
            """,
            (line_id, period_type, period_start, target_count)
        )
        conn.commit()

        # INSERT/UPDATE 어느 분기를 탔든(ON DUPLICATE KEY UPDATE는 lastrowid가
        # 드라이버/엔진에 따라 다르게 나올 수 있음) target_id를 확실히 알기
        # 위해 다시 조회한다.
        cursor.execute(
            "SELECT target_id FROM ProductionTarget "
            "WHERE line_id = %s AND period_type = %s AND period_start = %s",
            (line_id, period_type, period_start)
        )
        return cursor.fetchone()['target_id']
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_target(line_id, period_type, period_start):
    """특정 라인/기간의 목표를 1건 조회한다. 없으면 None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ProductionTarget "
            "WHERE line_id = %s AND period_type = %s AND period_start = %s",
            (line_id, period_type, period_start)
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_targets_by_line(line_id):
    """특정 라인에 등록된 목표 전체를 최신순으로 반환한다."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ProductionTarget WHERE line_id = %s "
            "ORDER BY period_start DESC",
            (line_id,)
        )
        return cursor.fetchall()
    finally:
        conn.close()
