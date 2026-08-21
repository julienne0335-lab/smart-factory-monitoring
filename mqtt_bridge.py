# =============================================================================
# mqtt_bridge.py
# 역할: MQTT 브로커(Mosquitto)를 구독(subscribe)해서, 센서 시뮬레이터
#       (scripts/mqtt_sensor_simulator.py)가 발행(publish)한 값을
#       기존 Flask 백엔드 파이프라인(DB 반영 → 실시간 알림)에 연결한다.
#
# [14.2절 설계와의 관계]
#   포트폴리오 14.2절은 "가상 센서 시뮬레이터"만 예시로 보여줬는데,
#   그건 발행자(publisher) 쪽 절반이다. 이 파일은 그 나머지 절반 —
#   "백엔드가 MQTT를 구독해서 실시간 반영한다"는 문장을 실제로 구현한 것.
#
# [extensions.py / socket_events.py와 같은 이유로 별도 파일로 분리함]
#   robot_service.apply_sensor_reading()을 가져다 써야 하는데, service
#   계층은 다시 extensions.socketio를 참조한다. app.py 최상단에서 이
#   파일을 import하면 5.2절에서 겪었던 순환 임포트와 같은 함정에 빠질
#   여지가 있으므로, app.py의 create_app() "실행 시점"에 import하도록
#   맞춘다(= socket_events.py와 동일한 규칙).
#
# [브로커가 없거나 늦게 뜨는 경우]
#   connect_async() + loop_start()를 쓰면 연결 시도를 백그라운드 스레드에
#   맡기고 즉시 반환한다. Mosquitto가 아직 안 떠 있어도 Flask 앱 자체는
#   정상적으로 뜨고, 브로커가 나중에 뜨면 paho가 알아서 재연결을 시도한다.
#   즉 "MQTT 파이프라인이 없어도 앱의 나머지 기능은 죽지 않는다"는 게
#   여기서 지키고 싶은 원칙이다 — claude_service(6단계)가 실패해도 로봇
#   조회 API는 멀쩡히 동작하는 것과 같은 결의 설계.
# =============================================================================

import json
import os
import sys

import paho.mqtt.client as mqtt

from service import robot_service

# MQTT 콜백은 백그라운드 네트워크 스레드에서 돈다. 이 스레드 안에서 print()가
# 던지는 예외(예: Windows 한글 콘솔의 cp949가 인코딩 못 하는 문자)는 아무도
# 잡아주지 않고 그대로 스레드를 죽여버려서, 그 뒤로 들어오는 모든 센서값이
# 조용히 유실된다 — 실제로 이 파이프라인을 테스트하다가 "—" 한 글자 때문에
# 겪은 버그다. sys.stdout.reconfigure()로 인코딩 문제를 애초에 예외로
# 만들지 않는다 (errors="replace" → 표현 못하는 문자는 깨져 보일지언정
# 프로세스/스레드를 죽이지는 않음).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MQTT_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_BROKER_PORT", 1883))
MQTT_TOPIC = "factory/robot/sensor"

_client = None  # start_mqtt_bridge()가 여러 번 불려도 재구독하지 않도록 가드


def _on_connect(client, userdata, flags, reason_code, properties=None):
    """
    브로커 연결(또는 재연결)에 성공했을 때 호출된다.
    구독을 connect 콜백 안에서 하는 이유: 재연결이 일어날 때마다
    구독도 자동으로 다시 걸리게 하기 위함 (paho 공식 권장 패턴).
    """
    print(f"[mqtt] 브로커 연결됨 ({MQTT_HOST}:{MQTT_PORT}) → '{MQTT_TOPIC}' 구독")
    client.subscribe(MQTT_TOPIC)


def _on_disconnect(client, userdata, flags, reason_code, properties=None):
    print("[mqtt] 브로커 연결 끊김 — paho가 자동 재연결을 시도합니다")


def _on_message(client, userdata, msg):
    """
    센서 페이로드 1건을 수신할 때마다 호출된다.

    [의도적으로 여기서 예외를 삼키는 이유]
    시뮬레이터가 보내는 값 하나가 깨져 있다고 MQTT 네트워크 루프 스레드
    전체가 죽으면(paho는 콜백에서 발생한 예외를 그대로 던지면 루프가
    멈춘다) 그 뒤로 들어오는 모든 정상 센서값까지 함께 유실된다.
    RobotError처럼 "명시적으로 등록하는" 이벤트가 아니라 "계속 흘러드는
    스트림"이라는 점에서, 한 건의 실패가 파이프라인 전체를 막아서는
    안 된다고 판단해 여기서 로그만 남기고 다음 메시지를 계속 받는다.
    """
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        robot_id = payload["robot_id"]
        battery_level = payload["battery_level"]
        joint_wear = payload["joint_wear"]
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
        print(f"[mqtt] 잘못된 페이로드 무시: {e} — raw={msg.payload!r}")
        return

    result = robot_service.apply_sensor_reading(robot_id, battery_level, joint_wear)
    if result is None:
        print(f"[mqtt] robot_id={robot_id} 존재하지 않음 — 무시")


def start_mqtt_bridge():
    """
    MQTT 구독을 시작한다. create_app() 안에서 한 번 호출된다.
    - loop_start(): 네트워크 송수신을 별도 백그라운드 스레드에서 돌림
      (Flask 요청 처리 스레드를 막지 않음 — extensions.py의
       socketio async_mode='threading'과 같은 결의 선택)
    """
    global _client
    if _client is not None:
        return  # 이미 시작됨 (reloader 등으로 두 번 호출되는 상황 방지)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    client.connect_async(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    _client = client
    return client
