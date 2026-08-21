# =============================================================================
# mqtt_sensor_simulator.py
# 역할: 하드웨어(라즈베리파이/ESP32) 없이, 75대 로봇의 배터리·관절마모 센서값을
#       MQTT로 계속 발행(publish)하는 "가상 센서" — 14.2절 설계 예시의 실행판.
#
# [insert_dummy.py(2단계)와의 관계]
#   robot_id 1~75, battery_level/joint_wear의 값 범위는 2단계 더미데이터
#   생성 스크립트와 동일한 규칙을 따른다. 다른 점은 "DB에 한 번에 INSERT"
#   하는 대신 "1초마다 하나씩 MQTT로 발행"한다는 것 — 14.2절 콜아웃에서
#   말한 "기존 로직을 발행자로 개조"를 그대로 구현한 것.
#
# [단순 랜덤이 아니라 "점진적 방전 + 재충전" 패턴을 쓴 이유]
#   완전 랜덤(random.uniform(10,100))으로 매번 값을 던지면 배터리 값이
#   매 tick 요동쳐서, battery_status_update 트리거(1.4절, 15.2절에서 버그
#   수정)가 상태를 전환하는 걸 자연스럽게 관찰하기 어렵다. 로봇별로 배터리
#   상태를 들고 있다가 조금씩 깎고, warning_threshold 아래로 떨어지면 다시
#   완충되는 방식으로 시뮬레이션해야 "가동중 → 충전중 → 가동중"이 실제
#   현장처럼 자연스럽게 재현되고, 알림 파이프라인(robot_sensor_update)도
#   의미 있는 값 변화로 검증할 수 있다.
#
# [실행 방법]
#   1) Mosquitto 브로커를 먼저 띄워둔다:
#        "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto\mosquitto.conf -v
#   2) Flask 앱을 띄운다 (mqtt_bridge가 구독을 시작함): python app.py
#   3) 이 스크립트를 실행한다: python scripts\mqtt_sensor_simulator.py
# =============================================================================

import json
import random
import sys
import time

import paho.mqtt.client as mqtt

# mqtt_bridge.py와 동일한 이유 — Windows 콘솔 인코딩 때문에 print()가
# 예외를 던져 이 스크립트가 죽는 걸 방지한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "factory/robot/sensor"

ROBOT_COUNT = 75          # 0.2절 시스템 규모와 동일
TICK_SECONDS = 1          # 몇 초마다 로봇 하나씩 값을 발행할지
WARNING_THRESHOLD = 20    # Robot.warning_threshold 기본값(1.2절 DDL)과 동일

# robot_id → {"battery": float, "wear": float} — 프로세스가 떠 있는 동안
# 로봇별 상태를 기억해야 "점진적으로 깎이는" 흐름을 만들 수 있다.
_state = {
    robot_id: {
        "battery": random.uniform(50, 100),  # insert_dummy.py 신규 로봇 기준과 동일 범위
        "wear": random.uniform(0, 50),
    }
    for robot_id in range(1, ROBOT_COUNT + 1)
}


def _tick(robot_id):
    """
    로봇 1대의 센서값을 한 스텝 진행시킨다.
    - battery: 매 tick 1~4 감소. warning_threshold 이하로 떨어지면
      "충전 완료"를 흉내내어 80~100으로 점프시킨다.
    - wear(관절 마모도): 배터리와 달리 리셋되지 않고 계속 누적(최대 100).
      실제 부품처럼 "정비하기 전까지는 마모가 되돌아가지 않는다"는 걸
      표현하려는 의도 — Maintenance(정비 이력) 테이블과의 관계를 감안한
      설계이며, 실제 정비 반영까지는 이번 확장 범위 밖이다.
    """
    s = _state[robot_id]

    if s["battery"] <= WARNING_THRESHOLD:
        s["battery"] = round(random.uniform(80, 100), 1)
    else:
        s["battery"] = round(max(0.0, s["battery"] - random.uniform(1, 4)), 1)

    s["wear"] = round(min(100.0, s["wear"] + random.uniform(0, 0.3)), 1)

    return s["battery"], s["wear"]


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()

    print(f"[simulator] {MQTT_TOPIC} 발행 시작 (로봇 {ROBOT_COUNT}대, {TICK_SECONDS}초 간격)")
    try:
        robot_id = 1
        while True:
            battery, wear = _tick(robot_id)
            payload = {
                "robot_id": robot_id,
                "battery_level": battery,
                "joint_wear": wear,
                "timestamp": time.time(),
            }
            client.publish(MQTT_TOPIC, json.dumps(payload))
            print(f"[simulator] robot_id={robot_id:>2} battery={battery:>5.1f} wear={wear:>5.1f}")

            robot_id = robot_id % ROBOT_COUNT + 1  # 1..75를 순환
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        print("\n[simulator] 종료")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
