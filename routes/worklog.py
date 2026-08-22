# =============================================================================
# worklog.py
# 역할: 작업 로그 관련 API 엔드포인트(URL) 정의
# - service 계층을 호출해서 결과를 받아옴
# - 받은 결과를 JSON으로 변환해서 클라이언트에 반환
# - 파라미터가 1개면 URL 경로(path parameter), 2개 이상이거나 선택적이면
#   쿼리 파라미터(query parameter, ?key=value 형태)로 설계함
# =============================================================================

from flask import Blueprint, jsonify, request
from service import worklog_service
from auth import login_required, get_current_admin, apply_scope   # 10단계

worklog_bp = Blueprint('worklog', __name__)


# -----------------------------------------------------------------------------
# GET /worklogs/robot/<robot_id>
# 특정 로봇의 작업 로그 조회
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/robot/<int:robot_id>')
def get_worklogs_by_robot(robot_id):
    """
    특정 로봇(robot_id)의 작업 로그 목록을 조회한다. (페이지네이션 적용)
    - page(기본 1), per_page(기본 100) 쿼리 파라미터로 페이지 조절 가능
    - 예: /worklogs/robot/5?page=2&per_page=50
    - 응답 형태: {"data": [...], "page": 1, "per_page": 100,
                 "total_count": 13421, "total_pages": 135}
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    result = worklog_service.get_worklogs_by_robot(robot_id, page=page, per_page=per_page)
    return jsonify(result)


# -----------------------------------------------------------------------------
# GET /worklogs/work_type/<work_type>
# 특정 작업 유형의 로그 조회
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/work_type/<work_type>')
def get_worklogs_by_work_type(work_type):
    """
    특정 작업 유형(work_type)의 작업 로그 목록을 조회한다.
    - 예: /worklogs/work_type/조립
    """
    worklogs = worklog_service.get_worklogs_by_work_type(work_type)
    return jsonify(worklogs)


# -----------------------------------------------------------------------------
# GET /worklogs/worker_type/<worker_type>
# 작업자 유형(HUMAN/ROBOT)별 로그 조회
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/worker_type/<worker_type>')
def get_worklogs_by_worker_type(worker_type):
    """
    작업자 유형(HUMAN 또는 ROBOT)별 작업 로그 목록을 조회한다.
    - 예: /worklogs/worker_type/ROBOT
    """
    worklogs = worklog_service.get_worklogs_by_worker_type(worker_type)
    return jsonify(worklogs)


# -----------------------------------------------------------------------------
# GET /worklogs/date?start=YYYY-MM-DD&end=YYYY-MM-DD
# 날짜 범위로 작업 로그 조회
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/date')
def get_worklogs_by_date():
    """
    날짜 범위(start ~ end)로 작업 로그를 조회한다.
    - 파라미터가 2개(start_date, end_date)이므로 쿼리 파라미터로 받음
    - 예: /worklogs/date?start=2026-01-01&end=2026-01-31
    - page(기본 1), per_page(기본 100) 쿼리 파라미터로 페이지 조절 가능
      (응답 형태는 /worklogs/robot/<id>와 동일)
    """
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    result = worklog_service.get_worklogs_by_date(start_date, end_date, page=page, per_page=per_page)
    return jsonify(result)


# -----------------------------------------------------------------------------
# GET /worklogs/recent?n=10
# 최근 N개 작업 로그 조회
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/recent')
def get_recent_worklogs():
    """
    최근 작업 로그 n개를 조회한다.
    - n은 선택적 값이므로 쿼리 파라미터로 받고, 기본값 10 설정
    - type=int : 쿼리 파라미터는 기본적으로 문자열이므로 정수로 변환
    - 예: /worklogs/recent (n=10, 기본값) 또는 /worklogs/recent?n=20
    """
    n = request.args.get('n', 10, type=int)
    worklogs = worklog_service.get_recent_worklogs(n)
    return jsonify(worklogs)


# -----------------------------------------------------------------------------
# GET /worklogs/long?min_minutes=60
# 기준 시간 초과 작업 로그 조회 (경고 대상)
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/long')
def get_long_worklogs():
    """
    작업 시간이 min_minutes를 초과한 작업 로그를 조회한다.
    - 각 로그에는 is_warning 플래그가 service 계층에서 계산되어 옴
    - min_minutes는 선택적 값이므로 쿼리 파라미터 + 기본값(60분) 처리
    - 예: /worklogs/long?min_minutes=90
    """
    min_minutes = request.args.get('min_minutes', 60, type=int)
    worklogs = worklog_service.get_long_worklogs(min_minutes)
    return jsonify(worklogs)


# -----------------------------------------------------------------------------
# GET /worklogs/stats/robot
# 로봇별 작업 통계 (집계 데이터)
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/stats/robot')
def get_worklog_stats_by_robot():
    """
    로봇별 작업 통계를 조회한다.
    - 이미 DB에서 GROUP BY로 집계된 결과이므로 파라미터 없이 바로 조회
    - service에서 추가 가공 없이 그대로 반환하는 데이터
    """
    worklogs = worklog_service.get_worklog_stats_by_robot()
    return jsonify(worklogs)


# -----------------------------------------------------------------------------
# GET /worklogs/stats/line
# 라인별 작업 통계 (집계 데이터)
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/stats/line')
def get_worklog_stats_by_line():
    """
    라인별 작업 통계를 조회한다.
    - stats/robot과 동일하게 이미 집계된 데이터를 그대로 반환
    - 각 항목에 total_energy_cost_won(추정 에너지 비용, 원)이 포함됨
    """
    worklogs = worklog_service.get_worklog_stats_by_line()
    return jsonify(worklogs)


# -----------------------------------------------------------------------------
# GET /worklogs/stats/work_type
# 작업 유형별 작업 통계 (집계 데이터, 신규 — 에너지 비용 포함)
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/stats/work_type')
def get_worklog_stats_by_work_type():
    """
    작업 유형(work_type)별 통계를 조회한다.
    - stats/robot, stats/line과 동일한 패턴, 집계 축만 work_type
    - 각 항목에 total_energy_cost_won(추정 에너지 비용, 원)이 포함됨
    - 예: /worklogs/stats/work_type
    """
    worklogs = worklog_service.get_worklog_stats_by_work_type()
    return jsonify(worklogs)


# -----------------------------------------------------------------------------
# GET /worklogs/details
# 로봇/라인 정보(JOIN)를 포함한 개별 작업 로그 조회
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/details')
def get_worklogs_with_details():
    """
    로봇명, 라인명 등 상세 정보(JOIN)가 포함된 작업 로그 목록을 조회한다.
    - stats류(집계 데이터)와 달리 개별 로그 원본 데이터이며,
      duration_minutes가 service 계층에서 계산되어 붙어 있음
    """
    worklogs = worklog_service.get_worklogs_with_details()
    return jsonify(worklogs)

# -----------------------------------------------------------------------------
# GET /worklogs/search?robot_id=&line_id=&work_type=&worker_type=&start=&end=&min_minutes=&page=&per_page=
# 여러 조건을 조합해서 작업 로그 검색 (통합 검색 API)
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/search')
@login_required
def search_worklogs():
    """
    로봇 / 라인 / 작업유형 / 작업주체 / 날짜범위 / 최소작업시간을
    자유롭게 조합해서 검색한다. 파라미터는 전부 선택적이며,
    넘어오지 않은 조건은 무시된다.

    - 예: /worklogs/search?robot_id=5&work_type=조립&start=2026-01-01&end=2026-01-07
    - 예: /worklogs/search?line_id=2&worker_type=HUMAN&page=2
    - 응답 형태: {"data": [...], "page": 1, "per_page": 50,
                 "total_count": 3241, "total_pages": 65}
      (/worklogs/robot/<id>, /worklogs/date와 동일한 페이지네이션 형태)

    [10단계 — 권한 스코프]
      robots/search와 동일하게, 로그인한 관리자의 role에 따라
      line_id/factory_id를 서버가 강제로 덮어쓴다 (apply_scope).
    """
    filters = {
        'robot_id': request.args.get('robot_id', type=int),
        'line_id': request.args.get('line_id', type=int),
        'factory_id': request.args.get('factory_id', type=int),
        'work_type': request.args.get('work_type'),
        'worker_type': request.args.get('worker_type'),
        'start_date': request.args.get('start'),
        'end_date': request.args.get('end'),
        'min_minutes': request.args.get('min_minutes', type=int),
    }
    apply_scope(get_current_admin(), filters)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    result = worklog_service.search_worklogs(page=page, per_page=per_page, **filters)
    return jsonify(result)


# =============================================================================
# 불량률 / 기간별 집계 (3순위 MES-lite 확장)
# =============================================================================

# -----------------------------------------------------------------------------
# GET /worklogs/stats/defect/robot
# 로봇별 불량률 통계
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/stats/defect/robot')
def get_defect_rate_by_robot():
    """로봇별 불량률 통계를 조회한다. stats/robot과 동일한 패턴, 축만 불량률."""
    result = worklog_service.get_defect_rate_by_robot()
    return jsonify(result)


# -----------------------------------------------------------------------------
# GET /worklogs/stats/defect/line
# 라인별 불량률 통계
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/stats/defect/line')
def get_defect_rate_by_line():
    """라인별 불량률 통계를 조회한다."""
    result = worklog_service.get_defect_rate_by_line()
    return jsonify(result)


# -----------------------------------------------------------------------------
# GET /worklogs/stats/defect/work_type
# 작업 유형별 불량률 통계
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/stats/defect/work_type')
def get_defect_rate_by_work_type():
    """작업 유형별 불량률 통계를 조회한다."""
    result = worklog_service.get_defect_rate_by_work_type()
    return jsonify(result)


# -----------------------------------------------------------------------------
# GET /worklogs/stats/period?period_type=DAILY&start=&end=&line_id=&factory_id=
# 기간별(일/주/월) 집계 API
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/stats/period')
def get_worklog_period_stats():
    """
    기간(일/주/월) 단위로 버킷팅한 작업 통계를 조회한다.
    - period_type: DAILY / WEEKLY / MONTHLY (필수)
    - start, end: 집계 대상 날짜 범위 (필수 — 조건 없이 100만 건 전체를
      그룹핑하는 걸 막기 위해 worklogs/search와 동일하게 강제함)
    - line_id, factory_id: 선택적으로 특정 라인/공장만 좁혀서 집계
    - 예: /worklogs/stats/period?period_type=MONTHLY&start=2026-01-01&end=2026-08-31
    - 응답: [{"period": "2026-01", "total_count": 12000, "defect_count": 360,
              "defect_rate": 3.0, "avg_minutes": 41.2}, ...]
    """
    period_type = request.args.get('period_type')
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    line_id = request.args.get('line_id', type=int)
    factory_id = request.args.get('factory_id', type=int)

    if period_type not in worklog_service.VALID_PERIOD_TYPES:
        return jsonify({"message": "period_type은 DAILY/WEEKLY/MONTHLY 중 하나여야 합니다."}), 400
    if not start_date or not end_date:
        return jsonify({"message": "start와 end는 필수입니다."}), 400

    result = worklog_service.get_worklog_period_stats(
        period_type, start_date, end_date, line_id=line_id, factory_id=factory_id
    )
    return jsonify(result)