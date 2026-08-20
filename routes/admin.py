# =============================================================================
# admin.py — 10단계(로그인/권한) 신규
# 역할: 로그인/로그아웃 관련 라우트
# - robot.py/worklog.py/error.py와 다르게 JSON이 아니라 HTML(로그인 폼)을
#   반환해야 해서, url_prefix='/api' 없이 앱 루트에 그대로 등록함
#   (app.py에서 register_blueprint(admin_bp) — prefix 인자 없음)
# =============================================================================

from flask import Blueprint, render_template, request, redirect, url_for, session

from service import admin_service

admin_bp = Blueprint('admin', __name__)


# -----------------------------------------------------------------------------
# GET  /login  → 로그인 폼 페이지 보여주기
# POST /login  → 로그인 아이디/비밀번호 검증 후 세션에 저장
# -----------------------------------------------------------------------------
@admin_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    """
    GET: 로그인 폼을 그냥 보여준다.
    POST: 폼에서 넘어온 login_id/password를 admin_service.login()으로 검증한다.
      - 성공: session['admin']에 저장하고 '/'(로봇 목록)로 리다이렉트
      - 실패: 에러 메시지와 함께 로그인 폼을 다시 보여준다
        (login.html의 {% if error %} 블록이 이 값을 사용함)
    """
    if request.method == 'GET':
        return render_template('login.html', error=None)

    login_id = request.form.get('login_id', '').strip()
    password = request.form.get('password', '')

    admin = admin_service.login(login_id, password)

    if admin is None:
        return render_template(
            'login.html',
            error='아이디 또는 비밀번호가 올바르지 않습니다.'
        )

    session['admin'] = admin
    return redirect(url_for('index'))


# -----------------------------------------------------------------------------
# POST /logout → 세션 비우고 로그인 페이지로
# -----------------------------------------------------------------------------
@admin_bp.route('/logout', methods=['POST'])
def logout():
    """
    세션에서 로그인 정보를 지운다.
    - GET이 아니라 POST인 이유: 로그아웃도 "서버 상태를 바꾸는 행동"이라
      링크(<a href>) 클릭 한 번으로 실행되면 안 되고, 폼 제출로만 실행되게 함
      (CSRF 방지 관례 — POST /errors/robot으로 새 에러 등록하는 것과 같은 원칙)
    """
    session.pop('admin', None)
    return redirect(url_for('admin.login_page'))
