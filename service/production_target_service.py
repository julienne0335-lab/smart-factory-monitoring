# =============================================================================
# production_target_service.py
# 역할: 목표 생산량(ProductionTarget) 등록 + 달성률 계산 비즈니스 로직
# - maintenance_service.py가 maintenance_dao와 robot_dao를 함께 쓰는 것과
#   동일하게, 이 서비스도 production_target_dao(자기 도메인)와
#   worklog_dao(실적 집계)를 함께 사용한다.
# - (3순위 MES-lite 확장 — "목표 생산량 대비 달성률")
# =============================================================================

import calendar
from datetime import date, timedelta

from dao import productiontarget_dao, worklog_dao


def create_target(line_id, period_type, period_start, target_count):
    """
    라인의 기간별 목표 생산량을 등록(또는 갱신)한다.

    [반환값]
      int: 생성/갱신된 target_id
      None: line_id가 존재하지 않는 경우
    """
    if not productiontarget_dao.line_exists(line_id):
        return None

    return productiontarget_dao.create_target(line_id, period_type, period_start, target_count)


def get_targets_by_line(line_id):
    """특정 라인에 등록된 목표 이력 전체를 조회한다."""
    return productiontarget_dao.get_targets_by_line(line_id)


def _period_end_date(period_type, period_start):
    """
    period_type과 period_start(그 기간의 시작일)로부터 기간의 마지막 날짜를 계산한다.
    - DAILY   : 같은 날
    - WEEKLY  : period_start로부터 6일 뒤 (period_start를 그 주의 시작일로 간주)
    - MONTHLY : period_start가 속한 달의 마지막 날

    [파라미터]
      period_start (str | date): "YYYY-MM-DD" 문자열 또는 date 객체
    """
    if isinstance(period_start, str):
        period_start = date.fromisoformat(period_start)

    if period_type == 'DAILY':
        return period_start
    if period_type == 'WEEKLY':
        return period_start + timedelta(days=6)
    if period_type == 'MONTHLY':
        last_day = calendar.monthrange(period_start.year, period_start.month)[1]
        return period_start.replace(day=last_day)
    raise ValueError(f"알 수 없는 period_type: {period_type}")


def get_achievement_rate(line_id, period_type, period_start):
    """
    특정 라인/기간의 목표 생산량 대비 실제 달성률을 계산한다.

    [실적(actual_count) 정의]
      해당 라인·기간 범위에 started_at이 속하는 WorkLog 건수
      (worklog_dao.count_search_worklogs()를 그대로 재사용 — 기존 로봇별/
       라인별 통계도 동일하게 "작업 건수"를 COUNT(*)로 세는 것과 같은 기준)

    [기간 범위 계산 — 왜 문자열 BETWEEN을 그대로 안 썼나]
      search_worklogs류가 쓰는 날짜 문자열 BETWEEN은 "YYYY-MM-DD" 형태를
      그대로 넘기면 종료일 자정(00:00:00) 이전까지만 잡혀서 종료일 하루가
      통째로 누락된다. 특히 DAILY 기간은 시작일=종료일이라 이 방식으로는
      그날 실적이 거의 0으로 집계되는 치명적인 문제가 생기므로, 종료일에
      "23:59:59"를 붙여 그날 전체가 포함되게 한다.

    [반환값]
      dict: {line_id, period_type, period_start, period_end,
             target_count, actual_count, achievement_rate}
      None: 해당 라인/기간에 등록된 목표가 없는 경우
    """
    target = productiontarget_dao.get_target(line_id, period_type, period_start)
    if target is None:
        return None

    period_end = _period_end_date(period_type, period_start)
    end_datetime = f"{period_end.isoformat()} 23:59:59"

    actual_count = worklog_dao.count_search_worklogs(
        line_id=line_id, start_date=period_start, end_date=end_datetime
    )

    target_count = target['target_count']
    achievement_rate = round(actual_count / target_count * 100, 2) if target_count else None

    return {
        "line_id": line_id,
        "period_type": period_type,
        "period_start": str(period_start),
        "period_end": period_end.isoformat(),
        "target_count": target_count,
        "actual_count": actual_count,
        "achievement_rate": achievement_rate,
    }
