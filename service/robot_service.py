# =============================================================================
# robot_service.py
# 역할: 로봇 관련 비즈니스 로직 처리
# - DAO에서 데이터를 받아와서 가공 (is_alert 플래그 추가 등)
# - routes 계층에서 이 service를 호출함
# =============================================================================

from dao import robot_dao, worklog_dao


def get_all_robots():
    """
    전체 로봇 목록 조회
    - 모든 로봇에 is_alert 플래그 추가
    - status가 'error'인 로봇은 is_alert = True
    """
    robots = robot_dao.get_all_robots()
    for robot in robots:
        robot['is_alert'] = robot['status'] == '오류정지'
    return robots


def get_robot_by_id(robot_id):
    """
    특정 로봇 1개 조회
    - 로봇이 존재하지 않으면 None 반환
    - 존재하면 is_alert 플래그 추가 후 반환
    """
    robot = robot_dao.get_robot_by_id(robot_id)

    # 로봇이 없으면 None 반환 (routes에서 404 처리)
    if robot is None:
        return None

    robot['is_alert'] = robot['status'] == '오류정지'
    return robot


def get_robots_by_line(line_id):
    """
    특정 라인의 로봇 목록 조회
    - 해당 라인의 모든 로봇에 is_alert 플래그 추가
    """
    robots = robot_dao.get_robots_by_line(line_id)
    for robot in robots:
        robot['is_alert'] = robot['status'] == '오류정지'
    return robots


def get_robots_by_status(status):
    """
    특정 상태의 로봇 목록 조회
    - 이미 status로 필터링된 데이터지만
      routes/프론트에서 is_alert 키가 일관되게 존재해야 하므로 플래그 추가
    """
    robots = robot_dao.get_robots_by_status(status)
    for robot in robots:
        robot['is_alert'] = robot['status'] == '오류정지'
    return robots 