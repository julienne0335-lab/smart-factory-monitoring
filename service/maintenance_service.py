# =============================================================================
# maintenance_service.py
# 역할: 정비(Maintenance) 등록 비즈니스 로직
# - error_service.create_robot_error()와 동일한 3단계 패턴:
#     ① 소속 공장 조회(없으면 None)  ② DAO로 DB 반영  ③ 그 공장 room에 emit
# - joint_wear(관절 마모도)가 시뮬레이터에서 계속 누적만 되고 리셋되지
#   않는다는 게 14.2절 확장의 "알려진 한계"였음 — 정비 등록을 그 리셋
#   지점으로 연결한다.
# =============================================================================

from dao import maintenance_dao, robot_dao
from extensions import socketio


def create_maintenance(robot_id, part_name, maint_type):
    """
    정비 이력을 등록하고, 로봇의 joint_wear를 0으로 초기화한 뒤
    해당 로봇이 속한 공장에 실시간 알림을 보낸다.

    [반환값]
      int: 새로 생성된 maint_id
      None: robot_id가 존재하지 않는 경우
    """
    factory_id = robot_dao.get_factory_id_by_robot(robot_id)
    if factory_id is None:
        return None

    maint_id = maintenance_dao.create_maintenance(robot_id, part_name, maint_type)
    robot_dao.reset_joint_wear(robot_id)

    socketio.emit('robot_maintenance', {
        'maint_id': maint_id,
        'robot_id': robot_id,
        'part_name': part_name,
        'maint_type': maint_type,
        'joint_wear': 0,
    }, room=f"factory_{factory_id}")

    return maint_id


def get_maintenance_by_robot(robot_id):
    """특정 로봇의 정비 이력 전체를 조회한다."""
    return maintenance_dao.get_maintenance_by_robot(robot_id)
