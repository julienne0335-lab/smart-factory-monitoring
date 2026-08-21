"""
test_error_service.py — service/error_service.py 단위 테스트
──────────────────────────────────────────────────────────────────────
[핵심 검증 포인트 1 — ENUM 회귀 테스트]
  is_pending 플래그는 status가 정확히 '미처리'(한글)일 때만 True다.
  프로젝트 진행 중 영어값('pending')과 비교해서 항상 False가 나오는
  버그가 최소 3번 발생했었다. 이 테스트는 그 값을 고정해서
  같은 실수가 반복돼도 즉시 실패하게 만든다.

[핵심 검증 포인트 2 — 실시간 알림(socketio) 테스트]
  create_robot_error()는 에러를 저장한 뒤, 해당 로봇이 속한 공장
  room으로 socketio.emit()을 호출해야 한다. 실제 소켓 서버를 켜지
  않고도, "emit이 올바른 이벤트명 / 데이터 / room으로 호출됐는가"만
  검증할 수 있다 (Mock의 assert_called_once_with 사용).
"""

from unittest.mock import patch

from service import error_service


def _error(status, **overrides):
    """테스트용 로봇 에러 dict를 만드는 헬퍼 함수"""
    base = {
        "error_id": 1,
        "robot_id": 1,
        "error_type": "sensor_failure",
        "status": status,
        "occurred_at": "2026-01-01 09:00:00",
    }
    base.update(overrides)
    return base


# =============================================================================
# _add_pending_flag() — 내부 헬퍼 함수 직접 테스트
# =============================================================================

class TestAddPendingFlag:

    def test_korean_pending_status_sets_true(self):
        """status가 '미처리'면 is_pending=True (핵심 회귀 테스트)"""
        error = _error("미처리")

        result = error_service._add_pending_flag(error)

        assert result["is_pending"] is True

    def test_resolved_status_sets_false(self):
        error = _error("해결됨")

        result = error_service._add_pending_flag(error)

        assert result["is_pending"] is False

    def test_english_pending_value_does_not_match(self):
        """
        회귀 방지 테스트: 코드가 실수로 다시 'pending'(영어)과
        비교하도록 바뀌면, 실제 DB 값('미처리')과는 매칭되지 않으므로
        이 테스트가 그 차이를 드러내야 한다.
        """
        error = _error("pending")

        result = error_service._add_pending_flag(error)

        assert result["is_pending"] is False  # '미처리'가 아니므로 False가 맞음


# =============================================================================
# get_errors_by_robot() — 목록 전체에 플래그가 붙는지
# =============================================================================

class TestGetErrorsByRobot:

    @patch("service.error_service.error_dao.get_errors_by_robot")
    def test_adds_pending_flag_to_each_error(self, mock_dao):
        mock_dao.return_value = [_error("미처리"), _error("해결됨")]

        result = error_service.get_errors_by_robot(1)

        assert result[0]["is_pending"] is True
        assert result[1]["is_pending"] is False


# =============================================================================
# create_robot_error() — DB 저장 + 실시간 알림(socketio.emit) 검증
# =============================================================================

class TestCreateRobotError:
    """
    [구현이 바뀐 부분]
    처음 버전은 "먼저 저장 → 나중에 공장 조회" 순서였는데,
    존재하지 않는 robot_id로 저장을 시도하면 FK 제약 때문에 DB 에러가 나는 게
    더 늦게(더 안 좋게) 발견되는 구조였음. 그래서 순서를 뒤집어서
    "먼저 공장부터 조회(=존재 확인) → 있을 때만 저장"으로 바꿈.
    아래 테스트들은 이 순서 변경을 전제로 작성됨.
    """

    @patch("service.error_service.socketio")
    @patch("service.error_service.error_dao")
    def test_emits_to_correct_factory_room(self, mock_dao, mock_socketio):
        # 이 로봇(robot_id=1)은 3번 공장 소속이라고 가정
        mock_dao.get_factory_id_by_robot.return_value = 3
        # dao.create_robot_error()가 새로 생긴 error_id(42)를 반환한다고 가정
        mock_dao.create_robot_error.return_value = 42

        error_id = error_service.create_robot_error(
            robot_id=1, error_type="motor_error"
        )

        # 1) 반환값이 dao가 만든 error_id 그대로 전달되는지
        assert error_id == 42

        # 2) socketio.emit이 "정확히 한 번", "정확히 이 인자들로" 호출됐는지
        mock_socketio.emit.assert_called_once_with(
            "robot_error",
            {"error_id": 42, "robot_id": 1, "error_type": "motor_error"},
            room="factory_3",
        )

    @patch("service.error_service.socketio")
    @patch("service.error_service.error_dao")
    def test_uses_correct_robot_id_for_factory_lookup(self, mock_dao, mock_socketio):
        """factory_id를 조회할 때 올바른 robot_id로 조회하는지 확인"""
        mock_dao.get_factory_id_by_robot.return_value = 5
        mock_dao.create_robot_error.return_value = 1

        error_service.create_robot_error(robot_id=7, error_type="battery_critical")

        mock_dao.get_factory_id_by_robot.assert_called_once_with(7)

    @patch("service.error_service.socketio")
    @patch("service.error_service.error_dao")
    def test_returns_none_when_robot_not_found(self, mock_dao, mock_socketio):
        """
        존재하지 않는 robot_id면 DB에 저장을 시도조차 하지 않고 None을 반환해야
        한다 (routes 계층은 이 None을 보고 404를 내려줌).
        """
        mock_dao.get_factory_id_by_robot.return_value = None

        result = error_service.create_robot_error(robot_id=999, error_type="센서이상")

        assert result is None
        mock_dao.create_robot_error.assert_not_called()  # 저장 시도조차 하면 안 됨
        mock_socketio.emit.assert_not_called()            # 알림도 보내면 안 됨
