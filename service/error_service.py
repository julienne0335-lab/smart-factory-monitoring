# =============================================================================
# error_service.py
# 역할: 에러 관련 비즈니스 로직 처리
# - DAO에서 데이터를 받아와서 가공 (is_pending 플래그 추가 등)
# - routes 계층에서 이 service를 호출함
# =============================================================================

from dao import error_dao
from extensions import socketio   # from app import socketio → 이걸로 교체


# -----------------------------------------------------------------------------
# 내부용 헬퍼 함수 (파일 외부에서 직접 호출하지 않음)
# _로 시작하는 함수는 파이썬 관례상 "내부용"을 의미
# -----------------------------------------------------------------------------

def _add_pending_flag(error):
    """
    에러 1개에 is_pending 플래그 추가
    - status가 '미처리'이면 is_pending = True (미해결)
    - status가 '완료'이면 is_pending = False (해결됨)
    """
    error['is_pending'] = error['status'] == '미처리'   # ✅
    return error


# -----------------------------------------------------------------------------
# 로봇 에러 조회 함수들
# -----------------------------------------------------------------------------

def get_errors_by_robot(robot_id):
    """특정 로봇의 에러 목록 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_errors_by_robot(robot_id)
    return [_add_pending_flag(e) for e in errors]


def get_errors_by_type(error_type):
    """특정 에러 유형의 목록 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_errors_by_type(error_type)
    return [_add_pending_flag(e) for e in errors]


def get_errors_by_status(status):
    """
    특정 상태의 에러 목록 조회 + 미해결 플래그 추가
    - 이미 status로 필터링된 데이터지만
      routes/프론트에서 is_pending 키가 일관되게 존재해야 하므로 플래그 추가
    """
    errors = error_dao.get_errors_by_status(status)
    return [_add_pending_flag(e) for e in errors]


def get_recent_errors(n):
    """최근 n개 에러 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_recent_errors(n)
    return [_add_pending_flag(e) for e in errors]


def get_errors_by_date(start_date, end_date):
    """날짜 범위로 에러 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_errors_by_date(start_date, end_date)
    return [_add_pending_flag(e) for e in errors]


# -----------------------------------------------------------------------------
# 라인 에러 조회 함수들
# -----------------------------------------------------------------------------

def get_line_errors_by_line(line_id):
    """특정 라인의 에러 목록 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_line_errors_by_line(line_id)
    return [_add_pending_flag(e) for e in errors]


def get_line_errors_by_type(error_type):
    """특정 유형의 라인 에러 목록 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_line_errors_by_type(error_type)
    return [_add_pending_flag(e) for e in errors]


# -----------------------------------------------------------------------------
# 통계 및 기타
# -----------------------------------------------------------------------------

def get_error_stats_by_robot():
    """
    로봇별 에러 통계 조회
    - 이미 집계된 통계 데이터이므로 가공 없이 그대로 반환
    """
    return error_dao.get_error_stats_by_robot()


def get_unresolved_errors():
    """미해결 에러 전체 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_unresolved_errors()
    return [_add_pending_flag(e) for e in errors]


def get_errors_with_robot_info():
    """로봇 정보 포함 에러 목록 조회 + 미해결 플래그 추가"""
    errors = error_dao.get_errors_with_robot_info()
    return [_add_pending_flag(e) for e in errors]


def create_robot_error(robot_id, error_type, detail=None):
    """
    새 로봇 에러를 등록하고, 해당 로봇이 속한 공장에 실시간 알림을 보낸다.

    [처리 순서 — 순서를 바꾼 이유]
      1. 먼저 robot_id가 속한 공장(factory_id)부터 조회한다.
         이게 None이면 "존재하지 않는 로봇"이라는 뜻이므로,
         DB에 에러를 저장하지도 않고 바로 None을 반환해서
         routes 계층이 404를 내려줄 수 있게 한다.
      2. 로봇이 존재하면 그때 DAO를 통해 DB에 에러 저장
      3. socketio.emit()으로 해당 공장 room에 실시간 알림 전송

    [반환값]
      int: 새로 생성된 error_id
      None: robot_id가 존재하지 않는 경우
    """
    factory_id = error_dao.get_factory_id_by_robot(robot_id)
    if factory_id is None:
        return None

    error_id = error_dao.create_robot_error(robot_id, error_type, detail)

    socketio.emit('robot_error', {
        'error_id': error_id,
        'robot_id': robot_id,
        'error_type': error_type,
    }, room=f"factory_{factory_id}")

    return error_id 