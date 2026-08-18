# =============================================================================
# worklog_service.py
# 역할: 작업 로그 관련 비즈니스 로직 처리
# - DAO에서 데이터를 받아와서 가공 (duration_minutes, is_warning 추가 등)
# - routes 계층에서 이 service를 호출함
# =============================================================================

from dao import worklog_dao


# -----------------------------------------------------------------------------
# 내부용 헬퍼 함수 (파일 외부에서 직접 호출하지 않음)
# _로 시작하는 함수는 파이썬 관례상 "내부용"을 의미
# -----------------------------------------------------------------------------

def _calculate_duration(log):
    """
    작업 로그 1개에 duration_minutes(작업시간, 분) 추가
    - started_at, ended_at 둘 다 있을 때만 계산
    - 하나라도 None이면 duration_minutes = None
    - total_seconds() / 60 으로 분 단위 변환
    - round(duration, 1) 소수점 1자리로 반올림
    """
    if log['started_at'] and log['ended_at']:
        duration = (log['ended_at'] - log['started_at']).total_seconds() / 60
        log['duration_minutes'] = round(duration, 1)
    else:
        log['duration_minutes'] = None
    return log


# -----------------------------------------------------------------------------
# 작업 로그 조회 함수들
# -----------------------------------------------------------------------------

def get_worklogs_by_robot(robot_id):
    """특정 로봇의 작업 로그 조회 + 작업시간(분) 추가"""
    worklogs = worklog_dao.get_worklogs_by_robot(robot_id)
    return [_calculate_duration(log) for log in worklogs]


def get_worklogs_by_work_type(work_type):
    """특정 작업 유형의 로그 조회 + 작업시간(분) 추가"""
    worklogs = worklog_dao.get_worklogs_by_work_type(work_type)
    return [_calculate_duration(log) for log in worklogs]


def get_worklogs_by_worker_type(worker_type):
    """특정 작업자 유형(HUMAN/ROBOT)의 로그 조회 + 작업시간(분) 추가"""
    worklogs = worklog_dao.get_worklogs_by_worker_type(worker_type)
    return [_calculate_duration(log) for log in worklogs]


def get_worklogs_by_date(start_date, end_date):
    """날짜 범위로 작업 로그 조회 + 작업시간(분) 추가"""
    worklogs = worklog_dao.get_worklogs_by_date(start_date, end_date)
    return [_calculate_duration(log) for log in worklogs]


def get_recent_worklogs(n):
    """최근 n개 작업 로그 조회 + 작업시간(분) 추가"""
    worklogs = worklog_dao.get_recent_worklogs(n)
    return [_calculate_duration(log) for log in worklogs]


def get_worklog_stats_by_robot():
    """
    로봇별 작업 통계 조회
    - 이미 집계된 통계 데이터이므로 가공 없이 그대로 반환
    """
    return worklog_dao.get_worklog_stats_by_robot()


def get_worklog_stats_by_line():
    """
    라인별 작업 통계 조회
    - 이미 집계된 통계 데이터이므로 가공 없이 그대로 반환
    """
    return worklog_dao.get_worklog_stats_by_line()


def get_worklogs_with_details():
    """상세 정보 포함 작업 로그 조회 + 작업시간(분) 추가"""
    worklogs = worklog_dao.get_worklogs_with_details()
    return [_calculate_duration(log) for log in worklogs]


def get_long_worklogs(min_minutes):
    """
    기준 시간 초과 작업 로그 조회 + 작업시간(분) + 경고 플래그 추가
    - duration_minutes가 min_minutes 초과면 is_warning = True
    - started_at/ended_at이 없으면 is_warning = False
    """
    worklogs = worklog_dao.get_long_worklogs(min_minutes)

    for log in worklogs:
        if log['started_at'] and log['ended_at']:
            duration = (log['ended_at'] - log['started_at']).total_seconds() / 60
            log['duration_minutes'] = round(duration, 1)
            log['is_warning'] = duration > min_minutes  # 기준 초과 여부 (True/False)
        else:
            log['duration_minutes'] = None
            log['is_warning'] = False

    return worklogs