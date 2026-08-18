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

worklog_bp = Blueprint('worklog', __name__)


# -----------------------------------------------------------------------------
# GET /worklogs/robot/<robot_id>
# 특정 로봇의 작업 로그 조회
# -----------------------------------------------------------------------------
@worklog_bp.route('/worklogs/robot/<int:robot_id>')
def get_worklogs_by_robot(robot_id):
    """
    특정 로봇(robot_id)의 작업 로그 목록을 조회한다.
    - 각 로그에는 duration_minutes(작업시간, 분)가 service 계층에서 계산되어 옴
    """
    worklogs = worklog_service.get_worklogs_by_robot(robot_id)
    return jsonify(worklogs)


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
    - request.args.get('키') : 쿼리 파라미터 값을 문자열로 꺼냄 (없으면 None)
    - 날짜는 타입 변환 없이 문자열 그대로 service/DAO로 넘김
      (DAO의 SQL에서 BETWEEN %s AND %s 형태로 처리)
    """
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    worklogs = worklog_service.get_worklogs_by_date(start_date, end_date)
    return jsonify(worklogs)


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
    """
    worklogs = worklog_service.get_worklog_stats_by_line()
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