# =============================================================================
# socket_events.py
# 역할: WebSocket(Socket.IO) 이벤트 핸들러 정의
# - HTTP Blueprint(robot.py, worklog.py, error.py)와는 다른 메커니즘
# - @socketio.on('이벤트명') 데코레이터로 이벤트를 등록함
# - 클라이언트가 연결/해제될 때, 또는 특정 이벤트를 보낼 때 실행됨
# =============================================================================

from flask import request
from flask_socketio import join_room, leave_room
from extensions import socketio   # 여기도 동일하게 교체


# -----------------------------------------------------------------------------
# connect 이벤트
# - 클라이언트가 socket.io로 연결을 시도할 때 자동 실행됨
# - 연결 시 factory_id를 쿼리 파라미터로 받아서, 해당 공장 room에 입장시킴
#   예) io({ query: { factory_id: 1 } }) → factory_1 room에 join
# -----------------------------------------------------------------------------
@socketio.on('connect')
def handle_connect():
    factory_id = request.args.get('factory_id')

    if factory_id is None:
        # factory_id 없이 연결하면 room에 안 넣고 로그만 남김
        # (추후 관리자 전체 알림 room을 따로 만들고 싶다면 여기서 처리 가능)
        print("클라이언트 연결됨 (factory_id 없음)")
        return

    room_name = f"factory_{factory_id}"
    join_room(room_name)
    print(f"클라이언트 연결됨 → {room_name} room 입장")


# -----------------------------------------------------------------------------
# disconnect 이벤트
# - 클라이언트 연결이 끊길 때(새로고침, 탭 닫기 등) 자동 실행됨
# - leave_room()을 따로 호출하지 않아도 Flask-SocketIO가
#   해당 세션을 모든 room에서 자동으로 제거해줌    
# -----------------------------------------------------------------------------
@socketio.on('disconnect')
def handle_disconnect():
    print("클라이언트 연결 종료")


# -----------------------------------------------------------------------------
# (참고) 알림을 실제로 보내는 함수는 여기 두지 않음
# - "누가 언제 연결했는지"를 다루는 이 파일과
#   "에러 발생 시 알림을 쏘는" 로직은 책임이 다르므로 분리 예정
# - emit 함수는 다음 단계에서 error_service.py 쪽에 추가할 예정
# =============================================================================