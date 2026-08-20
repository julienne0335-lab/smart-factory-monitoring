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
from auth import login_required, get_current_admin, apply_scope   # 10단계

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
@login_required
def get_error_stats_by_robot():
    """
    로봇별 에러 통계를 조회한다.
    - 이미 DB에서 집계된 결과이므로 추가 가공 없이 그대로 반환

    [10단계 — 권한 스코프]
      robots/search 등과 동일하게, 로그인한 관리자의 role에 따라
      factory_id/line_id를 서버가 강제로 적용한다 (apply_scope).
      이전엔 이 라우트에 로그인 보호 자체가 빠져 있어서, 누가 로그인했든
      75대 로봇 통계 전체가 그대로 노출되던 버그가 있었음 — 이번에 수정.
    """
    filters = {'factory_id': None, 'line_id': None}
    apply_scope(get_current_admin(), filters)

    errors = error_service.get_error_stats_by_robot(**filters)
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


# -----------------------------------------------------------------------------
# POST /errors/robot
# 새 로봇 에러 등록 + 실시간 알림(socketio) 발송
# -----------------------------------------------------------------------------
@error_bp.route('/errors/robot', methods=['POST'])
def create_robot_error():
    """
    새 로봇 에러를 등록한다.
    - 필수 body: robot_id, error_type
    - 선택 body: detail
    - robot_id가 존재하지 않으면 404
    - 성공하면 201 + 생성된 error_id 반환
    """
    data = request.get_json(silent=True) or {}
    robot_id = data.get('robot_id')
    error_type = data.get('error_type')
    detail = data.get('detail')

    if robot_id is None or not error_type:
        return jsonify({"message": "robot_id와 error_type은 필수입니다."}), 400

    error_id = error_service.create_robot_error(robot_id, error_type, detail)

    if error_id is None:
        return jsonify({"message": f"robot_id={robot_id}에 해당하는 로봇이 없습니다."}), 404

    return jsonify({
        "error_id": error_id,
        "robot_id": robot_id,
        "error_type": error_type,
    }), 201


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


# =============================================================================
# 통합 검색 (9단계 신규 — 로봇/워크로그 페이지와 동일한 패턴)
# =============================================================================

# -----------------------------------------------------------------------------
# GET /errors/robot/search?robot_id=&line_id=&error_type=&status=&start=&end=&page=&per_page=
# 여러 조건을 조합해서 로봇 에러 검색 (통합 검색 API)
# -----------------------------------------------------------------------------
@error_bp.route('/errors/robot/search')
@login_required
def search_robot_errors():
    """
    로봇ID / 라인 / 공장 / 에러유형 / 상태 / 발생일 범위를 조합해서 로봇 에러를 검색한다.
    - 예: /errors/robot/search?line_id=2&status=미처리
    - 예: /errors/robot/search?error_type=센서이상&start=2026-01-01&end=2026-01-07
    - 예: /errors/robot/search?factory_id=1
    - 응답 형태: {"data": [...], "page": 1, "per_page": 20,
                 "total_count": 42, "total_pages": 3}
      (robots/search, worklogs/search와 동일한 페이지네이션 응답 형태)

    [10단계 — 권한 스코프]
      robots/search와 동일하게, 로그인한 관리자의 role에 따라
      line_id/factory_id를 서버가 강제로 덮어쓴다 (apply_scope).
    """
    filters = {
        'robot_id': request.args.get('robot_id', type=int),
        'line_id': request.args.get('line_id', type=int),
        'factory_id': request.args.get('factory_id', type=int),
        'error_type': request.args.get('error_type'),
        'status': request.args.get('status'),
        'start_date': request.args.get('start'),
        'end_date': request.args.get('end'),
    }
    apply_scope(get_current_admin(), filters)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    result = error_service.search_robot_errors(page=page, per_page=per_page, **filters)
    return jsonify(result)


# -----------------------------------------------------------------------------
# GET /errors/line/search?line_id=&factory_id=&error_type=&status=&start=&end=&page=&per_page=
# 여러 조건을 조합해서 라인 에러 검색 (통합 검색 API)
# -----------------------------------------------------------------------------
@error_bp.route('/errors/line/search')
@login_required
def search_line_errors():
    """
    라인ID / 공장 / 에러유형 / 상태 / 발생일 범위를 조합해서 라인 에러를 검색한다.
    - 예: /errors/line/search?factory_id=1&status=미처리
    - 예: /errors/line/search?line_id=2&error_type=설비고장
    - 응답 형태: {"data": [...], "page": 1, "per_page": 20,
                 "total_count": 12, "total_pages": 1}

    [10단계 — 권한 스코프]
      robots/search와 동일하게, 로그인한 관리자의 role에 따라
      line_id/factory_id를 서버가 강제로 덮어쓴다 (apply_scope).
    """
    filters = {
        'line_id': request.args.get('line_id', type=int),
        'factory_id': request.args.get('factory_id', type=int),
        'error_type': request.args.get('error_type'),
        'status': request.args.get('status'),
        'start_date': request.args.get('start'),
        'end_date': request.args.get('end'),
    }
    apply_scope(get_current_admin(), filters)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    result = error_service.search_line_errors(page=page, per_page=per_page, **filters)
    return jsonify(result)