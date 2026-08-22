# =============================================================================
# app.py
# 역할: Flask 애플리케이션의 진입점(entry point)
# - Flask 앱 객체를 생성
# - routes 계층에서 만든 Blueprint들을 등록 (register_blueprint)
# - 앱을 실행 (app.run)
#
# [흐름 요약]
#   요청 → app.py가 URL을 보고 어떤 Blueprint(robot/worklog/error)로
#   보낼지 결정 → 해당 routes 함수 실행 → service 호출 → dao 호출 → DB
# =============================================================================

import os

from flask import Flask, render_template
from dotenv import load_dotenv

from extensions import socketio   # ← 여기서 가져옴
from auth import login_required   # 10단계: 로그인 확인 데코레이터

from routes.robot import robot_bp
from routes.worklog import worklog_bp
from routes.error import error_bp
from routes.admin import admin_bp   # 10단계: 로그인/로그아웃

load_dotenv()  # db.py에서도 호출하지만, SECRET_KEY는 여기서 바로 써야 해서 한 번 더 호출
# (load_dotenv()는 몇 번을 불러도 안전함 — .env 파일을 다시 읽어서 os.environ을
#  갱신할 뿐, 중복 호출 자체가 에러를 내거나 값을 꼬이게 하지 않음)


def create_app():
    app = Flask(__name__)
    socketio.init_app(app)

    # -------------------------------------------------------------------
    # SECRET_KEY (10단계 신규)
    # - Flask session은 "서명된 쿠키"라서, 이 키로 서명/검증한다.
    #   이 키를 모르면 클라이언트가 세션 쿠키 내용을 위조할 수 없음.
    # - .env(로컬) / Render 환경변수(배포)에 SECRET_KEY를 넣어두면 그 값을 씀.
    #   없으면 개발용 기본값으로 대체하되, 배포 환경에서는 반드시 별도로
    #   설정해야 함 (기본값은 GitHub에 공개되어 있어 배포용으로 쓰면 안 됨).
    # -------------------------------------------------------------------
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-this-secret-key')

    # -------------------------------------------------------------------
    # socket 이벤트 핸들러 등록
    # - 함수 안에서 import하는 이유: socket_events.py가 app.py의 socketio를
    #   가져다 쓰는데(순환 참조), 이걸 파일 최상단에서 import하면
    #   app.py가 아직 완성되지 않은 시점에 socket_events.py가 app.py를
    #   불러오려다 에러가 남. create_app() 함수 "실행 시점"에 import하면
    #   그때는 이미 socketio 객체가 만들어져 있으므로 문제없음.
    # - import만 해도 @socketio.on(...) 데코레이터가 실행되면서
    #   이벤트가 등록되므로, 반환값을 변수에 담을 필요는 없음
    # -------------------------------------------------------------------
    from routes import socket_events

    app.register_blueprint(robot_bp, url_prefix='/api')
    app.register_blueprint(worklog_bp, url_prefix='/api')
    app.register_blueprint(error_bp, url_prefix='/api')
    app.register_blueprint(admin_bp)   # /login, /logout — prefix 없이 루트에 등록

    @app.route('/')
    @login_required
    def index():
        return render_template('index.html')

    @app.route('/errors')
    @login_required
    def errors_page():
        return render_template('errors.html')

    @app.route('/worklogs')
    @login_required
    def worklogs_page():
        return render_template('worklogs.html')

    return app


# 앱 인스턴스 생성
# - Flask 개발 서버(app.run)나 배포 환경(PythonAnywhere의 WSGI)에서
#   모두 이 app 객체를 가져다 씀
app = create_app()


# -----------------------------------------------------------------------------
# 로컬 개발 서버 실행
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    DEBUG = True
    # debug=True : 코드 수정 시 서버 자동 재시작 + 에러 발생 시 상세 에러 페이지 표시
    #              (개발 중에만 사용, 배포 시에는 False로 바꾸거나 이 블록 자체를 안 씀)

    # -------------------------------------------------------------------
    # MQTT 센서 브리지 (14.2절 확장) — 이 __main__ 블록 안에서만 시작한다
    # - create_app()은 gunicorn(배포)에서도 "app.py를 모듈로 import"하는
    #   과정에서 항상 실행되지만, 그 안에서 MQTT 브리지를 시작해버리면
    #   로컬 Mosquitto가 없는 배포 환경(Render)에서도 매번 연결을 시도하게
    #   된다. 14장 전체가 "하드웨어/브로커 없이도 로컬에서 아키텍처를
    #   검증한다"는 틀이므로, 브리지는 `python app.py`로 로컬 실행할
    #   때만 붙도록 여기(=__main__ 블록)에 둔다.
    # - DEBUG=True면 socketio.run()이 Werkzeug reloader를 켜서 프로세스를
    #   부모/자식 두 번 실행한다. WERKZEUG_RUN_MAIN이 세팅된 쪽(자식,
    #   실제로 요청을 서빙하는 프로세스)에서만 시작해야 MQTT 구독이
    #   두 번 붙지 않는다 — 5.2절 순환 임포트만큼이나 "프로세스가 몇 번
    #   실행되는가"를 몰라서 겪기 쉬운 함정이라 이렇게 가드해둔다.
    # -------------------------------------------------------------------
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not DEBUG:
        from mqtt_bridge import start_mqtt_bridge
        start_mqtt_bridge()

    # FLASK_RUN_HOST: 기본값 127.0.0.1(로컬 전용, 기존 동작 그대로).
    # Docker 컨테이너 안에서는 0.0.0.0으로 열어야 호스트 포트 매핑이
    # 컨테이너까지 도달한다 (docker-compose.yml의 app 서비스에서 설정).
    HOST = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    socketio.run(app, host=HOST, debug=DEBUG)