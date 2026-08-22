"""
maintenance_dao.py — Maintenance 테이블 DB 접근 계층 (DAO)
──────────────────────────────────────────────────────────────────────
[역할]
  정비 이력(Maintenance) 등록/조회를 담당한다.

[테이블 구조]
  Maintenance: maint_id, robot_id, part_name, maint_type, performed_at
  - maint_type ENUM: '정기점검' / '부품교체' / '사고후점검'
"""

from db import get_connection


def create_maintenance(robot_id, part_name, maint_type):
    """
    새 정비 이력을 1건 등록한다.

    [파라미터]
      robot_id   (int): 정비 대상 로봇 ID
      part_name  (str): 정비한 부품명
      maint_type (str): '정기점검' / '부품교체' / '사고후점검' 중 하나

    [반환값]
      int: 새로 생성된 maint_id
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Maintenance (robot_id, part_name, maint_type) VALUES (%s, %s, %s)",
            (robot_id, part_name, maint_type)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_maintenance_by_robot(robot_id):
    """
    특정 로봇의 정비 이력 전체를 반환한다. (최근순 정렬)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM Maintenance WHERE robot_id = %s ORDER BY performed_at DESC",
            (robot_id,)
        )
        return cursor.fetchall()
    finally:
        conn.close()
