"""
error_dao.py — RobotError / LineError / ErrorAnalysis 테이블 DB 접근 계층 (DAO)
──────────────────────────────────────────────────────────────────────
[역할]
  RobotError, LineError, ErrorAnalysis 테이블에 대한 모든 DB 쿼리를 담당함.

[테이블 구조]
  RobotError: error_id, robot_id, error_type, detail, status, occurred_at
  LineError:  error_id, line_id, error_type, status, occurred_at
  ErrorAnalysis: analysis_id, analysis_type, robot_id, target_count,
                 summary, root_cause, severity, recommendation,
                 raw_response, created_at

[status 값 정의 — 중요!]
  실제 DB ENUM 값은 한글임: '미처리' / '완료'
  ※ 예전 버전에서 'pending' / 'resolved' 영어 문자열로 쿼리하던 버그가 있었음.
     (is_alert 버그와 동일한 패턴 — ENUM 값과 코드 문자열 불일치로 인한 silent failure)
     이 파일에서는 전부 '미처리' / '완료'로 통일함.
"""

from db import get_connection


# ── RobotError 조회 함수 ─────────────────────────────────────────────

def get_errors_by_robot(robot_id):
    """
    특정 로봇의 에러 기록 전체를 반환한다. (최근순 정렬)

    [파라미터]
      robot_id (int): 조회할 로봇의 ID

    [반환값]
      list of dict: 해당 로봇의 모든 에러 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM RobotError WHERE robot_id = %s ORDER BY occurred_at DESC",
            (robot_id,)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_errors_by_type(error_type):
    """
    특정 에러 타입의 에러 기록을 반환한다.

    [파라미터]
      error_type (str): 조회할 에러 종류
        예) "센서이상", "충돌", "낙상", "과부하", "통신오류"

    [반환값]
      list of dict: 해당 error_type의 에러 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM RobotError WHERE error_type = %s", (error_type,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_errors_by_status(status):
    """
    특정 상태의 에러 기록을 반환한다.

    [파라미터]
      status (str): '미처리' 또는 '완료'

    [반환값]
      list of dict: 해당 status의 에러 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM RobotError WHERE status = %s", (status,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_recent_errors(n):
    """
    최근 N건의 에러 기록을 반환한다.

    [파라미터]
      n (int): 가져올 에러 기록 건수

    [반환값]
      list of dict: 최근 순으로 정렬된 N건의 에러 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM RobotError ORDER BY occurred_at DESC LIMIT %s",
            (n,)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_errors_by_date(start_date, end_date):
    """
    특정 날짜 범위의 에러 기록을 반환한다.

    [파라미터]
      start_date (str): 시작 날짜 (예: "2026-01-01")
      end_date   (str): 종료 날짜 (예: "2026-12-31")

    [반환값]
      list of dict: 해당 기간에 발생한 에러 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM RobotError WHERE occurred_at BETWEEN %s AND %s",
            (start_date, end_date)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def create_robot_error(robot_id, error_type, detail=None):
    """
    새 로봇 에러를 1건 등록한다.

    [파라미터]
      robot_id   (int): 에러가 발생한 로봇 ID
      error_type (str): '센서이상' / '충돌' / '낙상' / '과부하' / '통신오류' 중 하나
      detail     (str, 선택): 상세 설명. 안 주면 NULL로 저장됨

    [주의]
      status는 여기서 안 넣음 → DB 기본값 '미처리'가 자동으로 들어감 (DDL 참고)

    [반환값]
      int: 새로 생성된 error_id (AUTO_INCREMENT로 DB가 채번한 값)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO RobotError (robot_id, error_type, detail) VALUES (%s, %s, %s)",
            (robot_id, error_type, detail)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_factory_id_by_robot(robot_id):
    """
    로봇이 소속된 공장(factory_id)을 조회한다.
    - Robot.line_id → Line.factory_id를 조인해서 알아냄
      (Robot 테이블 자체엔 factory_id 컬럼이 없음, ERD 참고)
    - socketio 알림을 "그 로봇이 속한 공장 room"으로만 보내기 위해 필요함

    [반환값]
      int: factory_id
      None: 존재하지 않는 robot_id인 경우
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
            (robot_id,)
        )
        row = cursor.fetchone()
        return row['factory_id'] if row else None
    finally:
        conn.close()


def get_error_stats_by_robot(factory_id=None, line_id=None):
    """
    로봇별 에러 발생 횟수 통계를 반환한다.

    [파라미터] (10단계 신규 — 둘 다 선택적, None이면 전체 집계)
      factory_id (int) : 이 공장 소속 로봇만 집계 (Robot+Line JOIN 필요)
      line_id    (int) : 이 라인 소속 로봇만 집계 (Robot JOIN 필요)

    [반환값]
      list of dict: 로봇별 에러 총 발생 건수
      예) [{"robot_id": 1, "total_count": 5}, ...]

    [10단계 이전 버그]
      원래 필터가 아예 없어서, 누가 로그인했든 이 함수는 항상 75대 로봇
      전체를 집계해서 돌려줬음 — 로그인/검색 API 4개(robots/search 등)만
      apply_scope로 보호하고 이 통계 API는 빠뜨려서 생긴 구멍.
      (공장 반장이 다른 공장 로봇 통계까지, 라인 반장이 다른 라인 로봇
       통계까지 보이던 원인이 바로 이거였음)
    """
    conditions = []
    params = []

    if line_id is not None:
        conditions.append("r.line_id = %s")
        params.append(line_id)

    if factory_id is not None:
        conditions.append("l.factory_id = %s")
        params.append(factory_id)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    if factory_id is not None:
        from_clause = (
            "FROM RobotError e "
            "JOIN Robot r ON e.robot_id = r.robot_id "
            "JOIN Line l ON r.line_id = l.line_id"
        )
    elif line_id is not None:
        from_clause = "FROM RobotError e JOIN Robot r ON e.robot_id = r.robot_id"
    else:
        from_clause = "FROM RobotError e"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT e.robot_id,
                   COUNT(*) AS total_count
            {from_clause}
            {where_clause}
            GROUP BY e.robot_id
        """, params)
        return cursor.fetchall()
    finally:
        conn.close()


def get_unresolved_errors(limit=30):
    """
    미해결 상태의 에러 기록을 반환한다. (최근순, limit건까지)

    [파라미터]
      limit (int): 최대 반환 건수 (기본 30)
        - Claude API 배치 분석 프롬프트에 그대로 들어가기 때문에
          너무 많으면 토큰 낭비 + 응답 품질 저하로 이어짐.
          그래서 "미해결 전체"가 아니라 "최근 미해결 N건"으로 제한함.

    [반환값]
      list of dict: status가 '미처리'인 에러 기록 (최근순)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM RobotError WHERE status = '미처리' "
            "ORDER BY occurred_at DESC LIMIT %s",
            (limit,)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_errors_with_robot_info():
    """
    RobotError + Robot + Line 정보를 JOIN하여 반환한다.

    [반환값]
      list of dict: 에러 정보 + 해당 로봇 정보 + 라인 정보

    [참고]
      RobotError(e) → Robot(r): e.robot_id = r.robot_id
      Robot(r)      → Line(l) : r.line_id  = l.line_id
      r.status vs l.status처럼 같은 컬럼명이 있을 수 있어서
      테이블 별칭(e, r, l)으로 명확히 구분하여 SELECT함.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.error_id, e.robot_id, e.error_type, e.detail, e.status,
                   r.battery_level, r.joint_wear, r.status AS robot_status,
                   l.line_id, l.name, l.status AS line_status
            FROM RobotError e
            JOIN Robot r ON r.robot_id = e.robot_id
            JOIN Line l ON l.line_id = r.line_id
        """)
        return cursor.fetchall()
    finally:
        conn.close()


# ── LineError 조회 함수 ──────────────────────────────────────────────

def get_line_errors_by_line(line_id):
    """
    특정 라인의 에러 기록 전체를 반환한다.

    [파라미터]
      line_id (int): 조회할 라인의 ID

    [반환값]
      list of dict: 해당 라인의 모든 에러 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM LineError WHERE line_id = %s", (line_id,))
        return cursor.fetchall()
    finally:
        conn.close()


def get_line_errors_by_type(error_type):
    """
    특정 에러 타입의 라인 에러 기록을 반환한다.

    [파라미터]
      error_type (str): 조회할 에러 종류
        예) "설비고장", "전력이상", "원자재부족", "안전사고", "기타"

    [반환값]
      list of dict: 해당 error_type의 라인 에러 기록
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM LineError WHERE error_type = %s", (error_type,))
        return cursor.fetchall()
    finally:
        conn.close()


# ── ErrorAnalysis 저장/조회 함수 (6단계 신규) ─────────────────────────

def create_error_analysis(analysis_type, robot_id, target_count, summary,
                           root_cause, severity, recommendation, raw_response):
    """
    Claude API 분석 결과를 ErrorAnalysis 테이블에 저장한다.

    [파라미터]
      analysis_type (str): 'individual' 또는 'batch'
      robot_id (int | None): individual일 때만 값 존재, batch면 None
      target_count (int): 분석에 사용된 에러 건수
      summary (str): 전체 요약
      root_cause (str): 추정 원인
      severity (str): '낮음' / '보통' / '높음' / '긴급'
      recommendation (str): 권장 조치
      raw_response (str): Claude 원본 응답 (디버깅용 원문 보관)

    [반환값]
      int: 새로 생성된 analysis_id (cursor.lastrowid)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO ErrorAnalysis
               (analysis_type, robot_id, target_count, summary,
                root_cause, severity, recommendation, raw_response)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (analysis_type, robot_id, target_count, summary,
             root_cause, severity, recommendation, raw_response)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_recent_analyses(n=10):
    """
    최근 분석 이력 N건을 반환한다. (individual + batch 모두 포함)

    [파라미터]
      n (int): 가져올 건수 (기본 10)

    [반환값]
      list of dict: 최근 순으로 정렬된 분석 이력
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ErrorAnalysis ORDER BY created_at DESC LIMIT %s",
            (n,)
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_analyses_by_robot(robot_id, n=10):
    """
    특정 로봇에 대한 분석 이력을 반환한다. (individual 분석만 해당)

    [파라미터]
      robot_id (int): 조회할 로봇의 ID
      n (int): 가져올 건수 (기본 10)

    [반환값]
      list of dict: 해당 로봇의 분석 이력 (최근순) 
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ErrorAnalysis WHERE robot_id = %s "
            "ORDER BY created_at DESC LIMIT %s", 
            (robot_id, n)
        )
        return cursor.fetchall()
    finally:
        conn.close() 

# ── 통합 검색 함수 (로봇 에러) — 여러 필터 조합 + 페이지네이션 ──────────────

def search_robot_errors(robot_id=None, line_id=None, factory_id=None, error_type=None,
                         status=None, start_date=None, end_date=None, limit=20, offset=0):
    """
    여러 조건을 동시에 조합해서 로봇 에러(RobotError)를 페이지 단위로 검색한다.
    (robot_dao.search_robots() / worklog_dao.search_worklogs()와 동일한 설계:
     조건절을 동적으로 조립하는 헬퍼를 따로 빼서 search/count가 공유함)

    [파라미터] (전부 선택적 — None/빈값이면 해당 조건은 무시됨)
      robot_id   (int) : 특정 로봇 하나만
      line_id    (int) : 특정 라인으로 좁히기 (Robot 테이블과 JOIN 필요)
      factory_id (int) : 특정 공장으로 좁히기 (Robot+Line 둘 다 JOIN 필요)
      error_type (str) : '센서이상' / '충돌' / '낙상' / '과부하' / '통신오류'
      status     (str) : '미처리' / '완료'
      start_date (str) : 시작 날짜 (end_date와 "함께" 넘겨야 조건이 걸림)
      end_date   (str) : 종료 날짜
      limit, offset     : 페이지네이션

    [반환값]
      list of dict — 조건에 맞는 로봇 에러 목록 (이번 페이지 분량만)
      전체 건수는 count_search_robot_errors()로 별도 조회

    [참고]
      line_id/factory_id는 RobotError 테이블에 없는 컬럼이라
      Robot(→line_id) / Line(→factory_id)과 JOIN해야만 필터링 가능.
      (RobotError → robot_id → Robot → line_id → Line → factory_id)
      10단계(관리자 권한) 기준: 공장 반장(factory_id 스코프)이 로봇 에러를
      볼 때도 필요해서 line_error 검색과 동일하게 factory_id까지 지원함.
    """
    where_clause, from_clause, params = _build_robot_error_search_conditions(
        robot_id, line_id, factory_id, error_type, status, start_date, end_date
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = f"""
            SELECT e.* {from_clause} {where_clause}
            ORDER BY e.occurred_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        return cursor.fetchall()
    finally:
        conn.close()


def count_search_robot_errors(robot_id=None, line_id=None, factory_id=None, error_type=None,
                               status=None, start_date=None, end_date=None):
    """search_robot_errors()와 동일한 조건의 전체 건수를 반환한다 (total_pages 계산용)"""
    where_clause, from_clause, params = _build_robot_error_search_conditions(
        robot_id, line_id, factory_id, error_type, status, start_date, end_date
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) AS cnt {from_clause} {where_clause}", params)
        return cursor.fetchone()['cnt']
    finally:
        conn.close()


def _build_robot_error_search_conditions(robot_id, line_id, factory_id, error_type,
                                          status, start_date, end_date):
    """
    search_robot_errors() / count_search_robot_errors()가 공통으로 쓰는
    WHERE절 조립 로직. (robot_dao._build_robot_search_conditions()와 동일한 패턴)
    조건절 문자열 조립 코드가 두 함수에 중복되지 않도록 여기로 뺐다.

    [반환값]
      (where_clause, from_clause, params) 튜플
    """
    conditions = []
    params = []

    if robot_id is not None:
        conditions.append("e.robot_id = %s")
        params.append(robot_id)

    if line_id is not None:
        conditions.append("r.line_id = %s")
        params.append(line_id)

    if factory_id is not None:
        conditions.append("l.factory_id = %s")
        params.append(factory_id)

    if error_type:
        conditions.append("e.error_type = %s")
        params.append(error_type)

    if status:
        conditions.append("e.status = %s")
        params.append(status)

    # 날짜는 start/end 둘 다 있을 때만 BETWEEN 조건을 건다
    if start_date and end_date:
        conditions.append("e.occurred_at BETWEEN %s AND %s")
        params.append(start_date)
        params.append(end_date)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # factory_id가 있으면 Robot+Line 둘 다, line_id만 있으면 Robot만 JOIN.
    # (factory_id 조건에는 l.factory_id가 필요하므로 Line까지 반드시 필요함)
    if factory_id is not None:
        from_clause = (
            "FROM RobotError e "
            "JOIN Robot r ON e.robot_id = r.robot_id "
            "JOIN Line l ON r.line_id = l.line_id"
        )
    elif line_id is not None:
        from_clause = "FROM RobotError e JOIN Robot r ON e.robot_id = r.robot_id"
    else:
        from_clause = "FROM RobotError e"

    return where_clause, from_clause, params


# ── 통합 검색 함수 (라인 에러) — 여러 필터 조합 + 페이지네이션 ──────────────

def search_line_errors(line_id=None, factory_id=None, error_type=None, status=None,
                        start_date=None, end_date=None, limit=20, offset=0):
    """
    여러 조건을 동시에 조합해서 라인 에러(LineError)를 페이지 단위로 검색한다.
    (search_robot_errors()와 동일한 설계, 대상 테이블만 다름)

    [파라미터] (전부 선택적 — None/빈값이면 해당 조건은 무시됨)
      line_id    (int) : 특정 라인 하나만
      factory_id (int) : 특정 공장으로 좁히기 (Line 테이블과 JOIN 필요)
      error_type (str) : '설비고장' / '전력이상' / '원자재부족' / '안전사고' / '기타'
      status     (str) : '미처리' / '완료'
      start_date (str) : 시작 날짜 (end_date와 "함께" 넘겨야 조건이 걸림)
      end_date   (str) : 종료 날짜
      limit, offset     : 페이지네이션

    [반환값]
      list of dict — 조건에 맞는 라인 에러 목록 (이번 페이지 분량만)
      전체 건수는 count_search_line_errors()로 별도 조회

    [참고]
      factory_id는 LineError 테이블에 없는 컬럼이라 Line과 JOIN해야만 필터링 가능.
      (LineError → line_id → Line → factory_id)
    """
    where_clause, from_clause, params = _build_line_error_search_conditions(
        line_id, factory_id, error_type, status, start_date, end_date
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = f"""
            SELECT le.* {from_clause} {where_clause}
            ORDER BY le.occurred_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        return cursor.fetchall()
    finally:
        conn.close()


def count_search_line_errors(line_id=None, factory_id=None, error_type=None, status=None,
                              start_date=None, end_date=None):
    """search_line_errors()와 동일한 조건의 전체 건수를 반환한다 (total_pages 계산용)"""
    where_clause, from_clause, params = _build_line_error_search_conditions(
        line_id, factory_id, error_type, status, start_date, end_date
    )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) AS cnt {from_clause} {where_clause}", params)
        return cursor.fetchone()['cnt']
    finally:
        conn.close()


def _build_line_error_search_conditions(line_id, factory_id, error_type, status,
                                         start_date, end_date):
    """
    search_line_errors() / count_search_line_errors()가 공통으로 쓰는
    WHERE절 조립 로직.

    [반환값]
      (where_clause, from_clause, params) 튜플
    """
    conditions = []
    params = []

    if line_id is not None:
        conditions.append("le.line_id = %s")
        params.append(line_id)

    if factory_id is not None:
        conditions.append("l.factory_id = %s")
        params.append(factory_id)

    if error_type:
        conditions.append("le.error_type = %s")
        params.append(error_type)

    if status:
        conditions.append("le.status = %s")
        params.append(status)

    if start_date and end_date:
        conditions.append("le.occurred_at BETWEEN %s AND %s")
        params.append(start_date)
        params.append(end_date)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # factory_id 필터가 있을 때만 Line과 JOIN
    if factory_id is not None:
        from_clause = "FROM LineError le JOIN Line l ON le.line_id = l.line_id"
    else:
        from_clause = "FROM LineError le"

    return where_clause, from_clause, params