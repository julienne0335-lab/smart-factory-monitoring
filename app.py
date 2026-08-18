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

from flask import Flask, render_template
from extensions import socketio   # ← 여기서 가져옴

from routes.robot import robot_bp
from routes.worklog import worklog_bp
from routes.error import error_bp


def create_app():
    app = Flask(__name__)
    socketio.init_app(app)

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

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/errors')
    def errors_page():
        return render_template('errors.html')

    @app.route('/worklogs')
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
    # debug=True : 코드 수정 시 서버 자동 재시작 + 에러 발생 시 상세 에러 페이지 표시
    #              (개발 중에만 사용, 배포 시에는 False로 바꾸거나 이 블록 자체를 안 씀)
    socketio.run(app, debug=True)