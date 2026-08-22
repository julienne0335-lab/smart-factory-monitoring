"""
test_maintenance_service.py — service/maintenance_service.py 단위 테스트
──────────────────────────────────────────────────────────────────────
[테스트 방식]
  test_error_service.py의 TestCreateRobotError와 동일한 방식 — 실제 DB에는
  붙지 않고 dao/socketio를 Mock으로 바꿔치기해서 "서비스 계층이 올바른
  순서로, 올바른 인자로 호출하는가"만 검증한다.

[핵심 검증 포인트 1 — robot_id 존재 확인이 먼저다]
  create_maintenance()는 "공장 조회(=robot_id 존재 확인) → DB 저장 →
  joint_wear 리셋 → emit" 순서로 동작해야 한다. robot_id가 없으면 DB에
  아무것도 쓰지 않고 None을 반환해야 한다(error_service.create_robot_error()와
  동일한 원칙).

[핵심 검증 포인트 2 — joint_wear가 실제로 리셋되는가]
  19장 확장의 핵심은 "정비 등록 시 joint_wear를 0으로 초기화한다"는
  것이었다. robot_dao.reset_joint_wear()가 정확히 그 robot_id로
  호출되는지 검증한다.
"""

from unittest.mock import patch

from service import maintenance_service


class TestCreateMaintenance:

    @patch("service.maintenance_service.socketio")
    @patch("service.maintenance_service.robot_dao")
    @patch("service.maintenance_service.maintenance_dao")
    def test_returns_none_when_robot_not_found(self, mock_maint_dao, mock_robot_dao, mock_socketio):
        """존재하지 않는 robot_id면 DB에 저장/리셋/emit 전부 시도하면 안 된다"""
        mock_robot_dao.get_factory_id_by_robot.return_value = None

        result = maintenance_service.create_maintenance(
            robot_id=999, part_name="배터리", maint_type="정기점검"
        )

        assert result is None
        mock_maint_dao.create_maintenance.assert_not_called()
        mock_robot_dao.reset_joint_wear.assert_not_called()
        mock_socketio.emit.assert_not_called()

    @patch("service.maintenance_service.socketio")
    @patch("service.maintenance_service.robot_dao")
    @patch("service.maintenance_service.maintenance_dao")
    def test_success_resets_joint_wear_and_emits(self, mock_maint_dao, mock_robot_dao, mock_socketio):
        """정상 등록 시: INSERT → joint_wear 리셋 → 올바른 공장 room에 emit"""
        mock_robot_dao.get_factory_id_by_robot.return_value = 3
        mock_maint_dao.create_maintenance.return_value = 301

        maint_id = maintenance_service.create_maintenance(
            robot_id=1, part_name="관절 모터", maint_type="부품교체"
        )

        assert maint_id == 301

        mock_maint_dao.create_maintenance.assert_called_once_with(1, "관절 모터", "부품교체")
        mock_robot_dao.reset_joint_wear.assert_called_once_with(1)

        mock_socketio.emit.assert_called_once_with(
            "robot_maintenance",
            {
                "maint_id": 301,
                "robot_id": 1,
                "part_name": "관절 모터",
                "maint_type": "부품교체",
                "joint_wear": 0,
            },
            room="factory_3",
        )

    @patch("service.maintenance_service.socketio")
    @patch("service.maintenance_service.robot_dao")
    @patch("service.maintenance_service.maintenance_dao")
    def test_uses_correct_robot_id_for_factory_lookup(self, mock_maint_dao, mock_robot_dao, mock_socketio):
        mock_robot_dao.get_factory_id_by_robot.return_value = 2
        mock_maint_dao.create_maintenance.return_value = 1

        maintenance_service.create_maintenance(robot_id=7, part_name="그리퍼", maint_type="사고후점검")

        mock_robot_dao.get_factory_id_by_robot.assert_called_once_with(7)


class TestGetMaintenanceByRobot:

    @patch("service.maintenance_service.maintenance_dao.get_maintenance_by_robot")
    def test_delegates_to_dao(self, mock_dao):
        mock_dao.return_value = [{"maint_id": 1, "robot_id": 1}]

        result = maintenance_service.get_maintenance_by_robot(1)

        assert result == [{"maint_id": 1, "robot_id": 1}]
        mock_dao.assert_called_once_with(1)
