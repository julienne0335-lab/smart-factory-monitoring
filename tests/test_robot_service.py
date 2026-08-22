"""
test_robot_service.py — service/robot_service.py 단위 테스트
──────────────────────────────────────────────────────────────────────
[테스트 방식: Mock]
  실제 DB(dao 계층)에는 연결하지 않는다. dao 함수가 "이런 값을
  돌려줬다고 치자"라고 가짜로 흉내(mock)만 낸다. 그렇게 하면:
    - DB 없이도 언제 어디서나 즉시 실행 가능
    - service 계층의 "가공 로직"만 순수하게 검증 가능
  실제 DB까지 포함한 검증은 다음 단계(Thunder Client API 테스트)에서 한다.

[@patch 사용법 한 줄 설명]
  robot_service.py 안에는 `from dao import robot_dao, worklog_dao`로
  가져온 robot_dao가 있다. 이 robot_dao의 "실제 DB에 붙는 함수"를
  테스트 실행 중에만 가짜 함수로 바꿔치기하는 게 @patch다.
  patch 경로는 항상 "그 함수를 실제로 가져다 쓰는 위치" 기준으로 쓴다.
  → "dao.robot_dao.get_all_robots"가 아니라
     "service.robot_service.robot_dao.get_all_robots"

[핵심 검증 포인트 — ENUM 회귀 테스트]
  is_alert 플래그는 로봇 status가 정확히 '오류정지'(한글)일 때만
  True가 되어야 한다. 프로젝트 초반에 영어값('error')과 비교하다가
  항상 False만 나오는 버그가 있었기 때문에, 이 값을 테스트로
  고정해서 같은 실수가 반복돼도 바로 잡아낼 수 있게 한다.
"""

from unittest.mock import patch

from service import robot_service


def _robot(status, **overrides):
    """테스트용 로봇 dict를 만드는 헬퍼 함수 (매 테스트마다 새로 조립)"""
    base = {
        "robot_id": 1,
        "line_id": 1,
        "status": status,
        "battery_level": 80,
        "joint_wear": 10,
    }
    base.update(overrides)
    return base


# =============================================================================
# get_all_robots()
# =============================================================================

class TestGetAllRobots:

    @patch("service.robot_service.robot_dao.get_all_robots")
    def test_error_status_sets_alert_true(self, mock_get_all):
        """status가 '오류정지'면 is_alert가 True여야 한다 (핵심 회귀 테스트)"""
        mock_get_all.return_value = [_robot("오류정지")]

        result = robot_service.get_all_robots()

        assert result[0]["is_alert"] is True

    @patch("service.robot_service.robot_dao.get_all_robots")
    def test_normal_status_sets_alert_false(self, mock_get_all):
        """'오류정지'가 아닌 상태는 is_alert가 False여야 한다"""
        mock_get_all.return_value = [_robot("가동중")]

        result = robot_service.get_all_robots()

        assert result[0]["is_alert"] is False

    @patch("service.robot_service.robot_dao.get_all_robots")
    def test_english_error_value_does_not_trigger_alert(self, mock_get_all):
        """
        회귀 방지 테스트: 실수로 다시 영어값('error')과 비교하는 코드로
        바뀌면, DB에는 실제로 한글 ENUM만 들어오므로 이 테스트가
        (의도와 다르게) is_alert=False를 반환해 문제를 드러낸다.
        """
        mock_get_all.return_value = [_robot("error")]

        result = robot_service.get_all_robots()

        assert result[0]["is_alert"] is False  # '오류정지'가 아니므로 False가 맞음

    @patch("service.robot_service.robot_dao.get_all_robots")
    def test_multiple_robots_flagged_independently(self, mock_get_all):
        """여러 로봇이 섞여 있어도 각자 올바르게 플래그가 붙어야 한다"""
        mock_get_all.return_value = [
            _robot("오류정지", robot_id=1),
            _robot("가동중", robot_id=2),
        ]

        result = robot_service.get_all_robots()

        assert result[0]["is_alert"] is True
        assert result[1]["is_alert"] is False


# =============================================================================
# get_robot_by_id()
# =============================================================================

class TestGetRobotById:

    @patch("service.robot_service.robot_dao.get_robot_by_id")
    def test_returns_none_when_not_found(self, mock_get_one):
        """존재하지 않는 로봇이면 None을 그대로 반환해야 한다 (routes에서 404 처리)"""
        mock_get_one.return_value = None

        result = robot_service.get_robot_by_id(999)

        assert result is None

    @patch("service.robot_service.robot_dao.get_robot_by_id")
    def test_adds_alert_flag_when_found(self, mock_get_one):
        """로봇이 존재하면 is_alert 플래그가 추가되어야 한다"""
        mock_get_one.return_value = _robot("오류정지")

        result = robot_service.get_robot_by_id(1)

        assert result is not None
        assert result["is_alert"] is True


# =============================================================================
# get_robots_by_line()
# =============================================================================

class TestGetRobotsByLine:

    @patch("service.robot_service.robot_dao.get_robots_by_line")
    def test_adds_alert_flag_to_all_robots_in_line(self, mock_get_by_line):
        mock_get_by_line.return_value = [_robot("오류정지"), _robot("가동중")]

        result = robot_service.get_robots_by_line(1)

        assert result[0]["is_alert"] is True
        assert result[1]["is_alert"] is False


# =============================================================================
# get_robots_by_status()
# =============================================================================

class TestGetRobotsByStatus:

    @patch("service.robot_service.robot_dao.get_robots_by_status")
    def test_adds_consistent_alert_flag(self, mock_get_by_status):
        """
        이미 status로 필터링된 결과라도, 응답 형식 일관성을 위해
        is_alert 키가 항상 존재해야 한다.
        """
        mock_get_by_status.return_value = [_robot("오류정지")]

        result = robot_service.get_robots_by_status("오류정지")

        assert "is_alert" in result[0]
        assert result[0]["is_alert"] is True


# =============================================================================
# apply_sensor_reading() — 14.2절 MQTT 확장 (지금까지 테스트가 없던 함수)
# =============================================================================

class TestApplySensorReading:
    """
    [핵심 검증 포인트 1 — 없는 robot_id는 None]
      update 자체는 항상 시도하지만(rowcount로 존재 여부를 판단하지 않는다는
      15.2절의 이유 그대로), 그 뒤 get_robot_by_id()가 None이면 이 함수도
      None을 반환하고 emit을 호출하면 안 된다.

    [핵심 검증 포인트 2 — status는 트리거가 정한 값을 그대로 돌려준다]
      이 함수는 status를 직접 계산하지 않는다 — DB 트리거가 반영한 값을
      갱신 후 재조회해서 그대로 전달해야 한다는 게 원래 설계 의도였다.
    """

    @patch("service.robot_service.socketio")
    @patch("service.robot_service.robot_dao")
    def test_returns_none_when_robot_not_found(self, mock_dao, mock_socketio):
        mock_dao.get_robot_by_id.return_value = None

        result = robot_service.apply_sensor_reading(robot_id=999, battery_level=50, joint_wear=10)

        assert result is None
        mock_socketio.emit.assert_not_called()

    @patch("service.robot_service.socketio")
    @patch("service.robot_service.robot_dao")
    def test_updates_sensors_before_checking_existence(self, mock_dao, mock_socketio):
        """
        3.7·15.2절에서 확인된 이유대로, update_robot_sensors()는 항상
        먼저 호출돼야 한다(rowcount로 존재 여부를 판단하지 않으므로).
        """
        mock_dao.get_robot_by_id.return_value = None

        robot_service.apply_sensor_reading(robot_id=13, battery_level=18.4, joint_wear=42.1)

        mock_dao.update_robot_sensors.assert_called_once_with(13, 18.4, 42.1)

    @patch("service.robot_service.socketio")
    @patch("service.robot_service.robot_dao")
    def test_emits_trigger_recalculated_status_to_correct_room(self, mock_dao, mock_socketio):
        # 트리거가 이미 재계산해서 DB에 반영해둔 값을 재조회한 것이라고 가정
        mock_dao.get_robot_by_id.return_value = _robot("충전중", battery_level=18, joint_wear=42)
        mock_dao.get_factory_id_by_robot.return_value = 3

        result = robot_service.apply_sensor_reading(robot_id=1, battery_level=18.4, joint_wear=42.1)

        assert result == {
            "robot_id": 1,
            "battery_level": 18,
            "joint_wear": 42,
            "status": "충전중",
        }
        mock_socketio.emit.assert_called_once_with(
            "robot_sensor_update",
            {"robot_id": 1, "battery_level": 18, "joint_wear": 42, "status": "충전중"},
            room="factory_3",
        )
