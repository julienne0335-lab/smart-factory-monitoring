"""
test_worklog_service.py — service/worklog_service.py 단위 테스트
──────────────────────────────────────────────────────────────────────
[테스트 대상 로직]
  1. _calculate_duration(): started_at ~ ended_at 사이 시간을
     "분" 단위로 계산해서 duration_minutes에 채워 넣는 내부 함수
  2. get_long_worklogs(): 기준 시간(min_minutes)을 초과하면
     is_warning=True를 붙이는 로직

[Mock 방식]
  robot_service 테스트와 동일하게, dao 계층 함수를 가짜로 바꿔서
  "DB에서 이런 로그가 왔다고 치면 service가 duration/warning을
  올바르게 계산하는가"만 검증한다.
"""

from datetime import datetime
from unittest.mock import patch

from service import worklog_service


def _worklog(started_at=None, ended_at=None, **overrides):
    """테스트용 작업 로그 dict를 만드는 헬퍼 함수"""
    base = {
        "worklog_id": 1,
        "robot_id": 1,
        "work_type": "welding",
        "worker_type": "robot",
        "started_at": started_at,
        "ended_at": ended_at,
    }
    base.update(overrides)
    return base


# =============================================================================
# _calculate_duration() — 내부 헬퍼 함수 직접 테스트
# =============================================================================

class TestCalculateDuration:

    def test_calculates_minutes_correctly(self):
        """45분 차이가 나면 duration_minutes = 45.0이어야 한다"""
        log = _worklog(
            started_at=datetime(2026, 1, 1, 9, 0, 0),
            ended_at=datetime(2026, 1, 1, 9, 45, 0),
        )

        result = worklog_service._calculate_duration(log)

        assert result["duration_minutes"] == 45.0

    def test_rounds_to_one_decimal_place(self):
        """10분 30초 = 10.5분으로, 소수점 1자리까지 반올림되어야 한다"""
        log = _worklog(
            started_at=datetime(2026, 1, 1, 9, 0, 0),
            ended_at=datetime(2026, 1, 1, 9, 10, 30),
        )

        result = worklog_service._calculate_duration(log)

        assert result["duration_minutes"] == 10.5

    def test_missing_ended_at_returns_none(self):
        """작업이 아직 안 끝났으면(ended_at=None) duration_minutes도 None"""
        log = _worklog(started_at=datetime(2026, 1, 1, 9, 0, 0), ended_at=None)

        result = worklog_service._calculate_duration(log)

        assert result["duration_minutes"] is None

    def test_missing_started_at_returns_none(self):
        log = _worklog(started_at=None, ended_at=datetime(2026, 1, 1, 9, 0, 0))

        result = worklog_service._calculate_duration(log)

        assert result["duration_minutes"] is None


# =============================================================================
# get_worklogs_by_robot() — duration이 실제로 붙어서 나오는지
# =============================================================================

class TestGetWorklogsByRobot:

    @patch("service.worklog_service.worklog_dao.get_worklogs_by_robot")
    def test_adds_duration_to_each_log(self, mock_dao):
        mock_dao.return_value = [
            _worklog(datetime(2026, 1, 1, 9, 0), datetime(2026, 1, 1, 9, 30))
        ]

        result = worklog_service.get_worklogs_by_robot(1)

        assert result[0]["duration_minutes"] == 30.0


# =============================================================================
# get_long_worklogs() — is_warning 플래그
# =============================================================================

class TestGetLongWorklogs:

    @patch("service.worklog_service.worklog_dao.get_long_worklogs")
    def test_sets_warning_true_when_exceeded(self, mock_dao):
        """120분짜리 작업 + 기준 60분 → 기준 초과이므로 is_warning=True"""
        mock_dao.return_value = [
            _worklog(datetime(2026, 1, 1, 9, 0), datetime(2026, 1, 1, 11, 0))
        ]

        result = worklog_service.get_long_worklogs(60)

        assert result[0]["duration_minutes"] == 120.0
        assert result[0]["is_warning"] is True

    @patch("service.worklog_service.worklog_dao.get_long_worklogs")
    def test_sets_warning_false_when_under_threshold(self, mock_dao):
        """30분짜리 작업 + 기준 60분 → 기준 미달이므로 is_warning=False"""
        mock_dao.return_value = [
            _worklog(datetime(2026, 1, 1, 9, 0), datetime(2026, 1, 1, 9, 30))
        ]

        result = worklog_service.get_long_worklogs(60)

        assert result[0]["is_warning"] is False

    @patch("service.worklog_service.worklog_dao.get_long_worklogs")
    def test_missing_times_no_warning(self, mock_dao):
        """시간 정보가 없으면 duration_minutes=None, is_warning=False로 안전하게 처리"""
        mock_dao.return_value = [_worklog(started_at=None, ended_at=None)]

        result = worklog_service.get_long_worklogs(60)

        assert result[0]["duration_minutes"] is None
        assert result[0]["is_warning"] is False
