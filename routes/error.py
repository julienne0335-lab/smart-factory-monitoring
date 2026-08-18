# =============================================================================
# error.py
# 역할: 에러(로봇 에러 / 라인 에러) 관련 API 엔드포인트(URL) 정의
# - service 계층을 호출해서 결과를 받아옴
# - 받은 결과를 JSON으로 변환해서 클라이언트에 반환
# - 로봇 에러와 라인 에러는 URL이 겹치지 않도록
#   각각 /errors/robot/... , /errors/line/... prefix로 구분함
# - 6단계: Claude API 분석 라우트(/errors/analyze/...) 추가
# =============================================================================

from flask import Blueprint, jsonify, request

from service import error_service
from service import claude_service

error_bp = Blueprint('error', __name__)


# =============================================================================
# 로봇 에러 (RobotError)
# =============================================================================

# -----------------------------------------------------------------------------
# GET /errors/robot/<robot_id>
# 특정 로봇의 에러 목록 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/robot/<int:robot_id>')
def get_errors_by_robot(robot_id):
    """
    특정 로봇(robot_id)의 에러 목록을 조회한다.
    - 각 에러에는 is_pending 플래그가 service 계층에서 계산되어 옴
      (status가 '미처리'이면 True = 미해결)
    """
    errors = error_service.get_errors_by_robot(robot_id)
    return jsonify(errors)


# -----------------------------------------------------------------------------
# GET /errors/robot/type/<error_type>
# 특정 유형의 로봇 에러 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/robot/type/<error_type>')
def get_errors_by_type(error_type):
    """
    특정 에러 유형(error_type)의 로봇 에러 목록을 조회한다.
    - 예: /errors/robot/type/센서이상
    """
    errors = error_service.get_errors_by_type(error_type)
    return jsonify(errors)


# -----------------------------------------------------------------------------
# GET /errors/robot/status/<status>
# 특정 상태의 로봇 에러 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/robot/status/<status>')
def get_errors_by_status(status):
    """
    특정 상태(status)의 로봇 에러 목록을 조회한다.
    - 예: /errors/robot/status/미처리
    """
    errors = error_service.get_errors_by_status(status)
    return jsonify(errors)


# -----------------------------------------------------------------------------
# GET /errors/robot/recent?n=10
# 최근 N개 로봇 에러 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/robot/recent')
def get_recent_errors():
    """
    최근 로봇 에러 n개를 조회한다.
    - n은 선택적 값이므로 쿼리 파라미터 + 기본값(10) 처리
    - 예: /errors/robot/recent?n=5
    """
    n = request.args.get('n', 10, type=int)
    errors = error_service.get_recent_errors(n)
    return jsonify(errors)


# -----------------------------------------------------------------------------
# GET /errors/robot/date?start=YYYY-MM-DD&end=YYYY-MM-DD
# 날짜 범위로 로봇 에러 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/robot/date')
def get_errors_by_date():
    """
    날짜 범위(start ~ end)로 로봇 에러를 조회한다.
    - 파라미터가 2개이므로 쿼리 파라미터로 받음
    - 예: /errors/robot/date?start=2026-01-01&end=2026-01-31
    """
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    errors = error_service.get_errors_by_date(start_date, end_date)
    return jsonify(errors)


# =============================================================================
# 라인 에러 (LineError)
# =============================================================================

# -----------------------------------------------------------------------------
# GET /errors/line/<line_id>
# 특정 라인의 에러 목록 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/line/<int:line_id>')
def get_line_errors_by_line(line_id):
    """
    특정 라인(line_id)의 에러 목록을 조회한다.
    - 로봇 에러와 동일하게 is_pending 플래그가 붙어서 옴
    """
    errors = error_service.get_line_errors_by_line(line_id)
    return jsonify(errors)


# -----------------------------------------------------------------------------
# GET /errors/line/type/<error_type>
# 특정 유형의 라인 에러 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/line/type/<error_type>')
def get_line_errors_by_type(error_type):
    """
    특정 에러 유형(error_type)의 라인 에러 목록을 조회한다.
    - /errors/robot/type/<error_type>과 같은 이름의 함수처럼 보이지만
      대상 테이블(RobotError vs LineError)이 다르므로 URL prefix로 구분함
    """
    errors = error_service.get_line_errors_by_type(error_type)
    return jsonify(errors)


# =============================================================================
# 통계 및 기타
# =============================================================================

# -----------------------------------------------------------------------------
# GET /errors/stats/robot
# 로봇별 에러 통계 (집계 데이터)
# -----------------------------------------------------------------------------
@error_bp.route('/errors/stats/robot')
def get_error_stats_by_robot():
    """
    로봇별 에러 통계를 조회한다.
    - 이미 DB에서 집계된 결과이므로 추가 가공 없이 그대로 반환
    """
    errors = error_service.get_error_stats_by_robot()
    return jsonify(errors)


# -----------------------------------------------------------------------------
# GET /errors/unresolved
# 미해결 에러 전체 조회 (로봇 + 라인 통합일 수 있음)
# -----------------------------------------------------------------------------
@error_bp.route('/errors/unresolved')
def get_unresolved_errors():
    """
    미해결(status='미처리') 에러 전체를 조회한다.
    - 관리자 대시보드에서 "지금 당장 처리해야 할 에러 목록"으로 활용 가능
    - is_pending 플래그가 붙어서 오지만, 이 API 특성상 전부 True일 것으로 예상됨
    """
    errors = error_service.get_unresolved_errors()
    return jsonify(errors)


# -----------------------------------------------------------------------------
# GET /errors/details
# 로봇 정보(JOIN)를 포함한 에러 목록 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/details')
def get_errors_with_robot_info():
    """
    로봇명 등 상세 정보(JOIN)가 포함된 에러 목록을 조회한다.
    - stats(집계 데이터)와 달리 개별 에러 원본 + 부가정보
    """
    errors = error_service.get_errors_with_robot_info()
    return jsonify(errors)


# =============================================================================
# Claude API 에러 로그 분석 (6단계 신규)
# =============================================================================

# -----------------------------------------------------------------------------
# POST /errors/analyze/robot/<robot_id>
# 특정 로봇 1대의 에러 이력을 Claude API로 분석
# -----------------------------------------------------------------------------
@error_bp.route('/errors/analyze/robot/<int:robot_id>', methods=['POST'])
def analyze_robot_errors(robot_id):
    """
    특정 로봇(robot_id)의 전체 에러 이력을 Claude API로 분석한다.
    - GET이 아니라 POST인 이유: 외부 API를 호출하고 DB에 새 레코드(분석 결과)를
      생성하는 "부수효과가 있는" 작업이기 때문 (단순 조회가 아님)
    - 해당 로봇에 에러 이력이 하나도 없으면 404 반환
    """
    result = claude_service.analyze_robot(robot_id)

    if result is None:
        return jsonify({"message": f"robot_id={robot_id}의 에러 이력이 없습니다."}), 404

    return jsonify(result)


# -----------------------------------------------------------------------------
# POST /errors/analyze/batch?limit=30
# 미해결 에러 최근 N건을 한번에 분석
# -----------------------------------------------------------------------------
@error_bp.route('/errors/analyze/batch', methods=['POST'])
def analyze_batch_errors():
    """
    미해결(status='미처리') 에러 최근 N건을 Claude API로 한번에 분석한다.
    - limit은 선택 쿼리 파라미터 (기본 30) — 프롬프트 토큰 관리를 위해 제한
    - 미해결 에러가 하나도 없으면 404 반환
    """
    limit = request.args.get('limit', 30, type=int)
    result = claude_service.analyze_unresolved_batch(limit=limit)

    if result is None:
        return jsonify({"message": "현재 미해결 에러가 없습니다."}), 404

    return jsonify(result)


# -----------------------------------------------------------------------------
# GET /errors/analyze/history?n=10
# 최근 분석 이력 조회
# -----------------------------------------------------------------------------
@error_bp.route('/errors/analyze/history')
def get_analysis_history():
    """
    최근 분석 이력(individual + batch)을 조회한다.
    - n은 선택 쿼리 파라미터 (기본 10)
    """
    n = request.args.get('n', 10, type=int)
    history = claude_service.get_analysis_history(n)
    return jsonify(history)