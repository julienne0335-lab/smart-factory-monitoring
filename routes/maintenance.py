# =============================================================================
# maintenance.py
# 역할: 정비(Maintenance) 관련 API 엔드포인트(URL) 정의
# - error.py의 POST /errors/robot과 동일한 구조/보호 수준 (로그인 보호 없음 —
#   현장 정비 등록도 에러 등록처럼 자동화 도구가 호출할 수 있다고 보고 통일함)
# =============================================================================

from flask import Blueprint, jsonify, request

from service import maintenance_service

maintenance_bp = Blueprint('maintenance', __name__)


# -----------------------------------------------------------------------------
# POST /maintenance
# 새 정비 이력 등록 (+ joint_wear 초기화, 실시간 알림)
# -----------------------------------------------------------------------------
@maintenance_bp.route('/maintenance', methods=['POST'])
def create_maintenance():
    """
    새 정비 이력을 등록한다.
    - 필수 body: robot_id, part_name, maint_type('정기점검'/'부품교체'/'사고후점검')
    - robot_id가 존재하지 않으면 404
    - 성공하면 201 + 생성된 maint_id 반환
    - 로봇의 joint_wear를 0으로 초기화하고 'robot_maintenance' 소켓 이벤트를 보낸다
    """
    data = request.get_json(silent=True) or {}
    robot_id = data.get('robot_id')
    part_name = data.get('part_name')
    maint_type = data.get('maint_type')

    if robot_id is None or not part_name or not maint_type:
        return jsonify({"message": "robot_id, part_name, maint_type은 필수입니다."}), 400

    maint_id = maintenance_service.create_maintenance(robot_id, part_name, maint_type)

    if maint_id is None:
        return jsonify({"message": f"robot_id={robot_id}에 해당하는 로봇이 없습니다."}), 404

    return jsonify({
        "maint_id": maint_id,
        "robot_id": robot_id,
        "part_name": part_name,
        "maint_type": maint_type,
    }), 201


# -----------------------------------------------------------------------------
# GET /maintenance/robot/<robot_id>
# 특정 로봇의 정비 이력 조회
# -----------------------------------------------------------------------------
@maintenance_bp.route('/maintenance/robot/<int:robot_id>')
def get_maintenance_by_robot(robot_id):
    """특정 로봇(robot_id)의 정비 이력 목록을 조회한다."""
    records = maintenance_service.get_maintenance_by_robot(robot_id)
    return jsonify(records)
