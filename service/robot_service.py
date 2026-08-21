# =============================================================================
# robot_service.py
# 역할: 로봇 관련 비즈니스 로직 처리
# - DAO에서 데이터를 받아와서 가공 (is_alert 플래그 추가 등)
# - routes 계층에서 이 service를 호출함
# =============================================================================

import math

from dao import robot_dao, worklog_dao
from extensions import socketio


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

# -----------------------------------------------------------------------------
# 페이지네이션 공통 헬퍼
# - worklog_service.py의 _paginate()와 동일한 응답 형태로 통일함
#   (프론트에서 워크로그/로봇 페이지네이션 처리 코드를 똑같은 패턴으로 짤 수 있게)
# -----------------------------------------------------------------------------

def _paginate(data, page, per_page, total_count):
    """
    페이지네이션 응답 형태로 감싸는 공통 헬퍼.
    data 배열만 반환하던 걸 { data, page, per_page, total_count, total_pages }
    형태의 객체로 감싸서, 프론트가 "지금 몇 페이지/전체 몇 페이지"를 알 수 있게 함.
    """
    total_pages = math.ceil(total_count / per_page) if per_page else 1
    return {
        "data": data,
        "page": page,
        "per_page": per_page,
        "total_count": total_count,
        "total_pages": total_pages,
    }


def search_robots(robot_id=None, line_id=None, factory_id=None, status=None,
                   max_battery=None, min_joint_wear=None,
                   page=1, per_page=25):
    """
    여러 조건을 조합해서 로봇을 검색 + is_alert 플래그 + 페이지네이션 정보까지 포함해서 반환.

    - 예: search_robots(line_id=2, status='오류정지')
    - 예: search_robots(factory_id=1, max_battery=20)
    """
    offset = (page - 1) * per_page

    total_count = robot_dao.count_search_robots(
        robot_id=robot_id, line_id=line_id, factory_id=factory_id,
        status=status, max_battery=max_battery, min_joint_wear=min_joint_wear,
    )
    robots = robot_dao.search_robots(
        robot_id=robot_id, line_id=line_id, factory_id=factory_id,
        status=status, max_battery=max_battery, min_joint_wear=min_joint_wear,
        limit=per_page, offset=offset,
    )

    for robot in robots:
        robot['is_alert'] = robot['status'] == '오류정지'

    return _paginate(robots, page, per_page, total_count)


# -----------------------------------------------------------------------------
# 14.2절 확장: MQTT 센서 시뮬레이터가 발행한 값을 반영하는 진입점
# - mqtt_bridge.py의 on_message 콜백이 이 함수를 호출한다.
# - error_service.create_robot_error()(5단계)와 동일한 3단계 패턴:
#     ① DAO로 DB 반영  ② 소속 공장 조회  ③ 그 공장 room에만 emit
# -----------------------------------------------------------------------------

def apply_sensor_reading(robot_id, battery_level, joint_wear):
    """
    센서(MQTT) 한 건을 로봇 상태에 반영하고, 소속 공장에 실시간으로 알린다.

    [파라미터]
      robot_id       (int)   : 센서값을 보낸 로봇
      battery_level  (float) : 0~100
      joint_wear     (float) : 0~100

    [반환값]
      dict | None: 갱신 결과 요약(반영에 성공했을 때) / robot_id가 없으면 None
        예) {"robot_id": 5, "battery_level": 18.4, "joint_wear": 42.1,
             "status": "충전중"}

    [주의]
      status는 여기서 계산하지 않는다 — DAO의 UPDATE가 실행되는 순간
      battery_status_update 트리거가 DB에서 이미 재계산해뒀으므로,
      갱신 후 다시 조회해서 "트리거가 실제로 반영한 값"을 그대로 돌려준다.
      (프론트도, 여기도 status 판정 로직을 따로 갖지 않는다는 0.6절 원칙과 동일)
    """
    robot_dao.update_robot_sensors(robot_id, battery_level, joint_wear)

    # UPDATE 자체의 rowcount로는 "robot_id가 존재하는가"를 믿을 수 없다
    # (robot_dao.update_robot_sensors 참고) — 갱신 후 다시 조회해서
    # 존재 여부를 판단한다. 3.4절과 동일한 "없으면 None" 패턴.
    robot = robot_dao.get_robot_by_id(robot_id)
    if robot is None:
        return None  # 존재하지 않는 robot_id — mqtt_bridge에서 로그만 남기고 무시

    factory_id = robot_dao.get_factory_id_by_robot(robot_id)

    payload = {
        "robot_id": robot_id,
        "battery_level": robot['battery_level'],
        "joint_wear": robot['joint_wear'],
        "status": robot['status'],
    }

    socketio.emit('robot_sensor_update', payload, room=f"factory_{factory_id}")
    return payload