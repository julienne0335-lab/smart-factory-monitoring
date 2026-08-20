"""
admin_dao.py — Admin 테이블 DB 접근 계층 (DAO) — 10단계(로그인/권한) 신규
──────────────────────────────────────────────────────────────────────
[역할]
  Admin 테이블에 대한 모든 DB 쿼리를 담당함.

[Admin 테이블은 이미 존재함 — 새로 만드는 게 아님]
  Stage 1 DDL 설계 당시 이미 정의되어 있었고(DDL 문서 참고),
  fix_case.sql로 대소문자까지 정리되어 실제 DB에 이미 있는 테이블임.
  지금까지 애플리케이션 코드(dao/service/routes)에서 한 번도 안 썼을 뿐.

[테이블 구조]
  Admin: admin_id, factory_id(NULL 허용), line_id(NULL 허용),
         name, login_id(UNIQUE), password(해시 저장), role(ENUM '슈퍼'/'일반'),
         created_at

[역할(role) ↔ 스코프 매핑 — DDL 설계 당시 정해진 규칙]
  role='슈퍼' (공장 반장) → factory_id에 값 있음, line_id는 NULL
  role='일반' (라인 반장) → line_id에 값 있음,    factory_id는 NULL
  (한 사람이 공장 전체를 보거나, 딱 한 라인만 보거나 — 딱 하나만 해당)

[비밀번호 저장 방식]
  평문 저장 절대 금지. werkzeug.security.generate_password_hash()로
  해시된 값만 password 컬럼에 저장한다 (admin_service.py에서 처리).
  이 DAO 파일은 해시가 이미 된 문자열을 그대로 저장/조회만 할 뿐,
  해싱 자체는 모른다 (계층 분리 — DB 접근과 보안 로직은 별개).
"""

from db import get_connection


def get_admin_by_login_id(login_id):
    """
    로그인 아이디로 관리자 1명을 조회한다. (로그인 시 사용)

    [파라미터]
      login_id (str): 로그인 아이디

    [반환값]
      dict: 해당 관리자 정보 (password 해시 포함 — 검증은 service 계층이 함)
      None: 존재하지 않는 login_id인 경우
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM Admin WHERE login_id = %s",
            (login_id,)
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_admin_by_id(admin_id):
    """
    admin_id로 관리자 1명을 조회한다.

    [파라미터]
      admin_id (int): 조회할 관리자의 ID

    [반환값]
      dict: 해당 관리자 정보
      None: 존재하지 않는 admin_id인 경우
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM Admin WHERE admin_id = %s",
            (admin_id,)
        )
        return cursor.fetchone()
    finally:
        conn.close()


def create_admin(name, login_id, password_hash, role, factory_id=None, line_id=None):
    """
    새 관리자 계정을 1건 등록한다.
    (지금 당장은 프론트에 "회원가입" 화면이 없어서 시드 스크립트/DB 콘솔에서
     직접 호출하는 용도. 나중에 관리자용 계정 생성 화면을 만들면 그때 재사용됨)

    [파라미터]
      name          (str): 표시용 이름
      login_id      (str): 로그인 아이디 (UNIQUE)
      password_hash (str): 이미 해싱된 비밀번호 문자열 (평문 절대 금지)
      role          (str): '슈퍼' 또는 '일반'
      factory_id    (int, 선택): 슈퍼(공장 반장)일 때만 값 전달
      line_id       (int, 선택): 일반(라인 반장)일 때만 값 전달

    [반환값]
      int: 새로 생성된 admin_id
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO Admin (factory_id, line_id, name, login_id, password, role)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (factory_id, line_id, name, login_id, password_hash, role)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
