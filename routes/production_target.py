# =============================================================================
# production_target.py
# 역할: 목표 생산량(ProductionTarget) 관련 API 엔드포인트(URL) 정의
# - maintenance.py와 동일한 보호 수준(로그인 보호 없음) — 목표 등록도
#   현장/배치 도구가 호출할 수 있다고 보고 통일함
# - (3순위 MES-lite 확장 — "목표 생산량 대비 달성률")
# =============================================================================

from flask import Blueprint, jsonify, request

from service import production_target_service

production_target_bp = Blueprint('production_target', __name__)


# -----------------------------------------------------------------------------
# POST /production-targets
# 라인의 기간별 목표 생산량 등록 (이미 있으면 갱신)
# -----------------------------------------------------------------------------
@production_target_bp.route('/production-targets', methods=['POST'])
def create_target():
    """
    라인의 기간별 목표 생산량을 등록한다.
    - 필수 body: line_id, period_type('DAILY'/'WEEKLY'/'MONTHLY'),
                 period_start('YYYY-MM-DD'), target_count
    - 이미 같은 (line_id, period_type, period_start) 조합이 있으면
      target_count를 덮어씀 (UPSERT)
    - line_id가 존재하지 않으면 404
    - 성공하면 201 + 생성/갱신된 target_id 반환
    """
    data = request.get_json(silent=True) or {}
    line_id = data.get('line_id')
    period_type = data.get('period_type')
    period_start = data.get('period_start')
    target_count = data.get('target_count')

    if line_id is None or not period_type or not period_start or target_count is None:
        return jsonify({
            "message": "line_id, period_type, period_start, target_count은 필수입니다."
        }), 400

    if period_type not in ('DAILY', 'WEEKLY', 'MONTHLY'):
        return jsonify({"message": "period_type은 DAILY/WEEKLY/MONTHLY 중 하나여야 합니다."}), 400

    target_id = production_target_service.create_target(
        line_id, period_type, period_start, target_count
    )

    if target_id is None:
        return jsonify({"message": f"line_id={line_id}에 해당하는 라인이 없습니다."}), 404

    return jsonify({
        "target_id": target_id,
        "line_id": line_id,
        "period_type": period_type,
        "period_start": period_start,
        "target_count": target_count,
    }), 201


# -----------------------------------------------------------------------------
# GET /production-targets/line/<line_id>
# 특정 라인의 목표 등록 이력 조회
# -----------------------------------------------------------------------------
@production_target_bp.route('/production-targets/line/<int:line_id>')
def get_targets_by_line(line_id):
    """특정 라인(line_id)에 등록된 목표 생산량 이력을 조회한다. (최신순)"""
    targets = production_target_service.get_targets_by_line(line_id)
    return jsonify(targets)


# -----------------------------------------------------------------------------
# GET /production-targets/achievement?line_id=&period_type=&period_start=
# 목표 생산량 대비 실제 달성률 조회
# -----------------------------------------------------------------------------
@production_target_bp.route('/production-targets/achievement')
def get_achievement_rate():
    """
    특정 라인/기간의 목표 생산량 대비 실제 달성률을 조회한다.
    - 예: /api/production-targets/achievement?line_id=1&period_type=MONTHLY&period_start=2026-08-01
    - 응답: {"line_id": 1, "period_type": "MONTHLY", "period_start": "2026-08-01",
             "period_end": "2026-08-31", "target_count": 8000,
             "actual_count": 7624, "achievement_rate": 95.3}
    - 목표가 등록돼 있지 않으면 404
    """
    line_id = request.args.get('line_id', type=int)
    period_type = request.args.get('period_type')
    period_start = request.args.get('period_start')

    if line_id is None or not period_type or not period_start:
        return jsonify({"message": "line_id, period_type, period_start는 필수입니다."}), 400

    result = production_target_service.get_achievement_rate(line_id, period_type, period_start)

    if result is None:
        return jsonify({"message": "해당 라인/기간에 등록된 목표가 없습니다."}), 404

    return jsonify(result)
