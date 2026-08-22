"""
test_production_target_service.py — service/production_target_service.py 단위 테스트
──────────────────────────────────────────────────────────────────────
[테스트 방식]
  test_maintenance_service.py와 동일한 방식 — 실제 DB에는 붙지 않고
  dao 계층 함수를 가짜로 바꿔치기해서 "서비스 계층이 올바른 순서로,
  올바른 인자로 호출하는가"만 검증한다.

[핵심 검증 포인트 1 — line_id 존재 확인이 먼저다]
  create_target()은 "라인 존재 확인 → DB 저장(UPSERT)" 순서로 동작해야
  한다. line_id가 없으면 DB에 아무것도 쓰지 않고 None을 반환해야 한다
  (maintenance_service.create_maintenance()와 동일한 원칙).

[핵심 검증 포인트 2 — 기간 마지막 날짜 계산(_period_end_date)]
  DAILY/WEEKLY/MONTHLY 각각 기간의 마지막 날짜를 정확히 계산하는지가
  달성률 집계 범위를 결정하는 핵심 로직이므로 별도로 검증한다.
  특히 WorkLog 실적 집계에 종료일 "23:59:59"를 붙이는 이유(문자열
  BETWEEN이 종료일 자정 이전까지만 잡는 문제)도 함께 검증한다.

[핵심 검증 포인트 3 — 달성률 계산]
  achievement_rate = actual_count / target_count * 100 (소수 2자리 반올림)
  목표가 등록돼 있지 않으면 None을 반환해야 한다.
"""

from datetime import date
from unittest.mock import patch

from service import production_target_service


# =============================================================================
# create_target()
# =============================================================================

class TestCreateTarget:

    @patch("service.production_target_service.productiontarget_dao")
    def test_returns_none_when_line_not_found(self, mock_dao):
        """존재하지 않는 line_id면 DB에 저장을 시도하면 안 된다"""
        mock_dao.line_exists.return_value = False

        result = production_target_service.create_target(
            line_id=999, period_type="MONTHLY", period_start="2026-08-01", target_count=8000
        )

        assert result is None
        mock_dao.create_target.assert_not_called()

    @patch("service.production_target_service.productiontarget_dao")
    def test_success_delegates_to_dao(self, mock_dao):
        mock_dao.line_exists.return_value = True
        mock_dao.create_target.return_value = 1

        target_id = production_target_service.create_target(
            line_id=1, period_type="MONTHLY", period_start="2026-08-01", target_count=8000
        )

        assert target_id == 1
        mock_dao.create_target.assert_called_once_with(1, "MONTHLY", "2026-08-01", 8000)


# =============================================================================
# _period_end_date() — 기간 마지막 날짜 계산
# =============================================================================

class TestPeriodEndDate:

    def test_daily_is_same_day(self):
        result = production_target_service._period_end_date("DAILY", "2026-08-20")
        assert result == date(2026, 8, 20)

    def test_weekly_is_six_days_later(self):
        result = production_target_service._period_end_date("WEEKLY", "2026-08-17")
        assert result == date(2026, 8, 23)

    def test_monthly_is_last_day_of_month(self):
        """8월은 31일까지 있으므로 마지막 날은 8월 31일"""
        result = production_target_service._period_end_date("MONTHLY", "2026-08-01")
        assert result == date(2026, 8, 31)

    def test_monthly_handles_february(self):
        """2026년은 윤년이 아니므로 2월은 28일까지"""
        result = production_target_service._period_end_date("MONTHLY", "2026-02-01")
        assert result == date(2026, 2, 28)

    def test_accepts_date_object_directly(self):
        result = production_target_service._period_end_date("DAILY", date(2026, 8, 20))
        assert result == date(2026, 8, 20)


# =============================================================================
# get_achievement_rate()
# =============================================================================

class TestGetAchievementRate:

    @patch("service.production_target_service.worklog_dao")
    @patch("service.production_target_service.productiontarget_dao")
    def test_returns_none_when_target_not_found(self, mock_target_dao, mock_worklog_dao):
        mock_target_dao.get_target.return_value = None

        result = production_target_service.get_achievement_rate(1, "MONTHLY", "2026-08-01")

        assert result is None
        mock_worklog_dao.count_search_worklogs.assert_not_called()

    @patch("service.production_target_service.worklog_dao")
    @patch("service.production_target_service.productiontarget_dao")
    def test_calculates_rate_correctly(self, mock_target_dao, mock_worklog_dao):
        mock_target_dao.get_target.return_value = {"target_count": 8000}
        mock_worklog_dao.count_search_worklogs.return_value = 7624

        result = production_target_service.get_achievement_rate(1, "MONTHLY", "2026-08-01")

        assert result["target_count"] == 8000
        assert result["actual_count"] == 7624
        assert result["achievement_rate"] == 95.3   # round(7624/8000*100, 2)
        assert result["period_end"] == "2026-08-31"

    @patch("service.production_target_service.worklog_dao")
    @patch("service.production_target_service.productiontarget_dao")
    def test_passes_end_of_day_datetime_for_actual_count(self, mock_target_dao, mock_worklog_dao):
        """
        DAILY 기간은 시작일=종료일이라, 종료일에 '23:59:59'를 붙이지 않으면
        그날 00:00:00 이후에 시작된 작업이 전부 실적에서 누락된다.
        """
        mock_target_dao.get_target.return_value = {"target_count": 100}
        mock_worklog_dao.count_search_worklogs.return_value = 42

        production_target_service.get_achievement_rate(3, "DAILY", "2026-08-20")

        mock_worklog_dao.count_search_worklogs.assert_called_once_with(
            line_id=3, start_date="2026-08-20", end_date="2026-08-20 23:59:59"
        )

    @patch("service.production_target_service.worklog_dao")
    @patch("service.production_target_service.productiontarget_dao")
    def test_zero_target_count_returns_none_rate(self, mock_target_dao, mock_worklog_dao):
        """target_count가 0이면 나누기 대신 achievement_rate=None으로 안전하게 처리"""
        mock_target_dao.get_target.return_value = {"target_count": 0}
        mock_worklog_dao.count_search_worklogs.return_value = 0

        result = production_target_service.get_achievement_rate(1, "MONTHLY", "2026-08-01")

        assert result["achievement_rate"] is None
