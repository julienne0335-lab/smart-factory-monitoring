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
    """
    [페이지네이션 추가로 응답 형태가 바뀜]
    Locust 부하 테스트에서 로봇 1대 워크로그 응답이 평균 2.64MB, 14~20초씩
    걸리는 게 확인되어 LIMIT/OFFSET 페이지네이션을 추가함. 그 결과 반환값이
    배열 그 자체에서 {data, page, per_page, total_count, total_pages}
    객체로 바뀌었으므로, 아래 테스트들은 result["data"][...] 형태로 검증함.
    """

    @patch("service.worklog_service.worklog_dao.count_worklogs_by_robot")
    @patch("service.worklog_service.worklog_dao.get_worklogs_by_robot")
    def test_adds_duration_to_each_log(self, mock_get, mock_count):
        mock_count.return_value = 1
        mock_get.return_value = [
            _worklog(datetime(2026, 1, 1, 9, 0), datetime(2026, 1, 1, 9, 30))
        ]

        result = worklog_service.get_worklogs_by_robot(1)

        assert result["data"][0]["duration_minutes"] == 30.0

    @patch("service.worklog_service.worklog_dao.count_worklogs_by_robot")
    @patch("service.worklog_service.worklog_dao.get_worklogs_by_robot")
    def test_pagination_metadata_is_correct(self, mock_get, mock_count):
        """총 250건, per_page=100이면 offset=100(2페이지), total_pages=3(올림)이어야 함"""
        mock_count.return_value = 250
        mock_get.return_value = []

        result = worklog_service.get_worklogs_by_robot(1, page=2, per_page=100)

        mock_get.assert_called_once_with(1, limit=100, offset=100)
        assert result["page"] == 2
        assert result["per_page"] == 100
        assert result["total_count"] == 250
        assert result["total_pages"] == 3  # ceil(250/100)


# =============================================================================
# get_long_worklogs() — is_warning 플래그
# =============================================================================

class TestGetWorklogsByDate:
    """get_worklogs_by_robot과 동일한 페이지네이션 로직을 공유하므로 패턴도 동일"""

    @patch("service.worklog_service.worklog_dao.count_worklogs_by_date")
    @patch("service.worklog_service.worklog_dao.get_worklogs_by_date")
    def test_adds_duration_and_pagination_metadata(self, mock_get, mock_count):
        mock_count.return_value = 5
        mock_get.return_value = [
            _worklog(datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 9, 20))
        ]

        result = worklog_service.get_worklogs_by_date("2024-01-01", "2024-01-07")

        mock_get.assert_called_once_with("2024-01-01", "2024-01-07", limit=100, offset=0)
        assert result["data"][0]["duration_minutes"] == 20.0
        assert result["total_count"] == 5
        assert result["total_pages"] == 1


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


# =============================================================================
# get_worklog_period_stats() — 기간별 집계 (3순위 MES-lite 확장)
# =============================================================================

class TestGetWorklogPeriodStats:

    @patch("service.worklog_service.worklog_dao.get_worklog_period_stats")
    def test_delegates_with_all_filters(self, mock_dao):
        """line_id/factory_id까지 그대로 dao로 전달되는지 확인"""
        mock_dao.return_value = [{"period": "2026-08", "total_count": 100}]

        result = worklog_service.get_worklog_period_stats(
            "MONTHLY", "2026-01-01", "2026-08-31", line_id=2, factory_id=1
        )

        mock_dao.assert_called_once_with(
            "MONTHLY", "2026-01-01", "2026-08-31", line_id=2, factory_id=1
        )
        assert result == [{"period": "2026-08", "total_count": 100}]
