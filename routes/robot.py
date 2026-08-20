# =============================================================================
# robot.py
# 역할: 로봇 관련 API 엔드포인트(URL) 정의
# - service 계층을 호출해서 결과를 받아옴
# - 받은 결과를 JSON으로 변환해서 클라이언트(브라우저/프론트)에 반환
# - routes 계층은 "URL ↔ service 함수" 연결만 담당하고, 비즈니스 로직은 없음
# =============================================================================

from flask import Blueprint, jsonify, request
from service import robot_service

# Blueprint 생성
# - 'robot'이라는 이름으로 라우트들을 묶어서 관리
# - app.py에서 register_blueprint()로 등록해야 실제로 동작함
robot_bp = Blueprint('robot', __name__)


# -----------------------------------------------------------------------------
# GET /robots
# 전체 로봇 목록 조회
# -----------------------------------------------------------------------------
@robot_bp.route('/robots')
def get_all_robots():
    """
    전체 로봇 목록을 조회한다.
    - robot_service.get_all_robots() 호출
    - 각 로봇에는 is_alert 플래그가 이미 붙어서 옴 (service 계층에서 가공)
    - 결과가 없어도 빈 리스트([])가 정상 응답이므로 별도 예외 처리 불필요
    """
    robots = robot_service.get_all_robots()
    return jsonify(robots)


# -----------------------------------------------------------------------------
# GET /robots/<robot_id>
# 특정 로봇 1개 조회
# -----------------------------------------------------------------------------
@robot_bp.route('/robots/<int:robot_id>')
def get_robot_by_id(robot_id):
    """
    로봇 ID로 로봇 1개를 조회한다.
    - <int:robot_id> : URL 경로에서 정수형 값을 받아옴 (예: /robots/7 → robot_id=7)
    - 단건 조회이므로 "존재하지 않는 경우"를 별도로 처리해야 함
    - service에서 robot_dao 조회 결과가 없으면 None을 반환하도록 설계되어 있음
    - None이면 404 Not Found 응답 (요청한 리소스가 없다는 의미)
    - 존재하면 200 OK(jsonify 기본값) + 데이터 반환
    """
    robot = robot_service.get_robot_by_id(robot_id)

    if robot is None:
        # 튜플로 (응답 데이터, 상태코드) 형태로 반환하면 상태코드를 지정할 수 있음
        return jsonify({"error": "로봇을 찾을 수 없습니다"}), 404

    return jsonify(robot)


# -----------------------------------------------------------------------------
# GET /robots/line/<line_id>
# 특정 라인에 속한 로봇 목록 조회
# -----------------------------------------------------------------------------
@robot_bp.route('/robots/line/<int:line_id>')
def get_robots_by_line(line_id):
    """
    특정 라인(line_id)에 속한 로봇 목록을 조회한다.
    - 예: /robots/line/3 → line_id=3인 라인의 로봇 전체
    - 리스트 조회이므로 결과가 없어도 빈 리스트를 그대로 반환 (404 처리 없음)
    """
    robots = robot_service.get_robots_by_line(line_id)
    return jsonify(robots)


# -----------------------------------------------------------------------------
# GET /robots/status/<status>
# 특정 상태의 로봇 목록 조회
# -----------------------------------------------------------------------------
@robot_bp.route('/robots/status/<status>')
def get_robots_by_status(status):
    """
    특정 상태(status)의 로봇 목록을 조회한다.
    - 예: /robots/status/error → status가 'error'인 로봇 전체
    - status는 타입 지정 없이 문자열(str)로 그대로 받음 (<status>는 기본이 string)
    - 리스트 조회이므로 결과가 없어도 빈 리스트 반환
    """
    robots = robot_service.get_robots_by_status(status)
    return jsonify(robots)

# -----------------------------------------------------------------------------
# GET /robots/search?robot_id=&line_id=&factory_id=&status=&max_battery=&min_joint_wear=&page=&per_page=
# 여러 조건을 조합해서 로봇 검색 (통합 검색 API)
# -----------------------------------------------------------------------------
@robot_bp.route('/robots/search')
def search_robots():
    """
    로봇ID / 라인 / 공장 / 상태 / 배터리 하한 / 마모도 상한을 조합해서 검색한다.
    - 예: /robots/search?line_id=2&status=오류정지
    - 예: /robots/search?factory_id=1&max_battery=20
    - 예: /robots/search?min_joint_wear=80&page=2
    - 응답 형태: {"data": [...], "page": 1, "per_page": 25,
                 "total_count": 42, "total_pages": 2}
      (worklogs.py의 페이지네이션 응답과 형태를 통일함)
    """
    robot_id = request.args.get('robot_id', type=int)
    line_id = request.args.get('line_id', type=int)
    factory_id = request.args.get('factory_id', type=int)
    status = request.args.get('status')
    max_battery = request.args.get('max_battery', type=int)
    min_joint_wear = request.args.get('min_joint_wear', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    result = robot_service.search_robots(
        robot_id=robot_id, line_id=line_id, factory_id=factory_id,
        status=status, max_battery=max_battery, min_joint_wear=min_joint_wear,
        page=page, per_page=per_page,
    )
    return jsonify(result)