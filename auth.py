# =============================================================================
# auth.py
# 역할: 로그인/권한 관련 공통 유틸 (10단계 신규)
# - dao/service/routes 어디에도 속하지 않는 "가로로 걸치는" 공통 기능이라
#   extensions.py(socketio)처럼 프로젝트 루트에 독립 파일로 둠
# - 세션(Flask session) 기반 로그인 상태 확인 + 역할별 데이터 스코프 강제
# =============================================================================
#
# [세션에 저장하는 값]
#   로그인 성공 시 session['admin']에 아래 dict를 통째로 저장한다.
#     {
#       "admin_id":   int,
#       "login_id":   str,
#       "name":       str,            # 표시용 이름 (예: "김철수")
#       "role":       "슈퍼" | "일반",  # 슈퍼=공장 반장, 일반=라인 반장
#       "factory_id": int | None,     # 슈퍼(공장 반장)일 때만 값 있음
#       "line_id":    int | None,     # 일반(라인 반장)일 때만 값 있음
#     }
#   (DB의 password 해시값은 세션에 절대 넣지 않음 — 담을 이유도 없고,
#    세션 쿠키는 브라우저에 저장되므로 민감정보를 최소한으로 유지해야 함)

from functools import wraps

from flask import session, redirect, url_for, jsonify, request


def get_current_admin():
    """
    현재 로그인한 관리자 정보를 반환한다.

    [반환값]
      dict: 로그인 중이면 session['admin']
      None: 로그인 안 했으면
    """
    return session.get('admin')


def login_required(view_func):
    """
    로그인하지 않은 상태로 이 데코레이터가 붙은 라우트에 접근하면 막는다.

    [분기 이유]
      이 프로젝트는 페이지 라우트(HTML 반환, 예: '/')와 API 라우트
      (JSON 반환, 예: '/api/robots')가 섞여 있다. 페이지는 사람이 브라우저로
      직접 열어보는 것이므로 로그인 페이지로 "리다이렉트"하는 게 자연스럽고,
      API는 프론트 JS의 fetch()가 호출하는 것이므로 리다이렉트해봤자
      JS가 처리 못 하니 401 JSON을 그대로 반환하는 게 맞다.
      → 요청 경로가 '/api'로 시작하는지로 두 경우를 구분한다.
        (Blueprint 3개 모두 url_prefix='/api'로 등록되어 있어서
         이 기준이 정확히 들어맞음)

    [사용 예시]
      @app.route('/')
      @login_required
      def index():
          ...
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if get_current_admin() is None:
            if request.path.startswith('/api'):
                return jsonify({"message": "로그인이 필요합니다."}), 401
            return redirect(url_for('admin.login_page'))
        return view_func(*args, **kwargs)
    return wrapper


def apply_scope(admin, filters):
    """
    로그인한 관리자의 역할(role)에 따라 검색 필터에 스코프를 강제로 덮어씌운다.

    [왜 필요한가]
      클라이언트(브라우저)가 보낸 line_id/factory_id 쿼리 파라미터를
      그대로 믿으면 안 된다 — 예를 들어 라인 반장이 개발자도구로
      line_id를 다른 값으로 바꿔서 요청하면, 원래는 못 보던 다른 라인
      데이터까지 조회될 수 있다. 그래서 클라이언트가 뭘 보냈든 서버가
      "이 사람은 이 스코프만 볼 수 있다"를 매번 강제로 덮어쓴다.

    [동작]
      - role == '일반' (라인 반장): filters['line_id']를 본인 line_id로 강제
      - role == '슈퍼'  (공장 반장): filters['factory_id']를 본인 factory_id로 강제
      - robot_id / error_type / 날짜 범위 등 나머지 조건은 그대로 둔다.
        전부 AND로 합쳐지는 조건이라, 스코프 밖의 robot_id 등을 같이 넣어도
        결과가 0건이 될 뿐 — 다른 공장/라인 데이터가 새어나가는 경우는 없다.

    [파라미터]
      admin   (dict) : get_current_admin()의 반환값 (None이면 호출하면 안 됨 —
                        login_required가 먼저 걸려 있어야 함)
      filters (dict) : 라우트에서 만든 필터 딕셔너리. 이 함수 안에서 직접 수정함.

    [반환값]
      dict: 스코프가 적용된 filters (전달받은 딕셔너리를 그대로 수정해서 반환)
    """
    if admin['role'] == '일반':
        filters['line_id'] = admin['line_id']
    elif admin['role'] == '슈퍼':
        filters['factory_id'] = admin['factory_id']
    return filters
