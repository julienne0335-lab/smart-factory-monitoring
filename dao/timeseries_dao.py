"""
timeseries_dao.py — InfluxDB(시계열 DB) 접근 계층
──────────────────────────────────────────────────────────────────────
[14.9절 4순위 확장] 로봇 센서(battery_level/joint_wear)의 시계열 이력을
저장·조회한다. Robot.battery_level/joint_wear(MariaDB)는 지금까지처럼
"현재값" 스냅샷 용도로 그대로 두고(battery_status_update 트리거가
여전히 이 컬럼을 기준으로 동작함), 여기서는 "언제 몇 %였는지"의 이력만
추가로 남긴다 — 기존 트리거·API·스키마는 전혀 건드리지 않는 순수 추가
(additive) 확장이다.

[연결 실패에 관대한 이유]
mqtt_bridge.py("MQTT 파이프라인이 없어도 앱의 나머지 기능은 죽지 않는다")와
같은 원칙: 시계열 이력 저장 하나가 실패한다고 센서 반영 파이프라인 전체
(DB 갱신 + socketio 실시간 알림)가 죽으면 안 된다. INFLUX_URL이 비어
있으면(로컬에 InfluxDB를 안 띄운 개발자) 클라이언트 자체를 만들지 않고
조용히 기록/조회를 건너뛴다.
"""

import os

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = os.environ.get("INFLUX_URL")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "smart_factory")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "sensor_readings")

MEASUREMENT = "robot_sensor"

_client = None  # get_connection()과 달리 클라이언트는 재사용한다 — pymysql
                 # 연결과 다르게 InfluxDBClient는 커넥션 풀을 자체적으로
                 # 관리하는 무거운 객체라 매 호출마다 새로 만들 이유가 없다.


def _get_client():
    """
    INFLUX_URL이 설정돼 있을 때만 클라이언트를 만든다.
    설정돼 있지 않으면 None을 반환해 호출부가 조용히 기록/조회를 건너뛰게 한다.
    """
    global _client
    if not INFLUX_URL:
        return None
    if _client is None:
        _client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    return _client


def write_sensor_reading(robot_id, line_id, factory_id, battery_level, joint_wear):
    """
    센서 값 한 건을 시계열로 기록한다.

    [태그 vs 필드]
      robot_id/line_id/factory_id는 태그(tag) — "어느 로봇/라인/공장인지"로
      필터링/그룹핑할 때 인덱싱되어 빠르다. battery_level/joint_wear는
      필드(field) — 값 자체이고 태그로 쓰기엔 카디널리티가 의미 없다.
    """
    client = _get_client()
    if client is None:
        return

    point = (
        Point(MEASUREMENT)
        .tag("robot_id", str(robot_id))
        .tag("line_id", str(line_id))
        .tag("factory_id", str(factory_id))
        .field("battery_level", float(battery_level))
        .field("joint_wear", float(joint_wear))
    )

    try:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=INFLUX_BUCKET, record=point)
    except Exception as e:
        # mqtt_bridge.py의 _on_message()와 같은 이유로 예외를 여기서 삼킨다:
        # 이력 저장 한 건의 실패가 센서 반영 파이프라인 전체를 막아서는 안 된다.
        print(f"[influx] 센서 이력 기록 실패(무시하고 계속): {e}")


def query_sensor_history(robot_id, range_start="-1h"):
    """
    로봇 1대의 센서 이력을 시간순으로 조회한다.

    [파라미터]
      robot_id     (int) : 조회할 로봇
      range_start  (str) : Flux range() 문법의 상대 시작 시점 (예: "-1h", "-30m", "-7d")
                            호출부(robot_service.get_sensor_history)가 화이트리스트
                            정규식으로 검증한 값만 넘겨야 한다 — 여기서는 그대로
                            Flux 쿼리 문자열에 꽂아 넣으므로 검증되지 않은 사용자
                            입력을 직접 넘기면 Flux 인젝션이 된다.

    [반환값]
      list of dict: [{"time": ISO8601 문자열, "battery_level": float, "joint_wear": float}, ...]
      InfluxDB가 설정돼 있지 않거나 조회에 실패하면 빈 리스트.
    """
    client = _get_client()
    if client is None:
        return []

    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {range_start})
      |> filter(fn: (r) => r._measurement == "{MEASUREMENT}" and r.robot_id == "{robot_id}")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"])
    '''

    try:
        query_api = client.query_api()
        tables = query_api.query(flux, org=INFLUX_ORG)
    except Exception as e:
        print(f"[influx] 센서 이력 조회 실패: {e}")
        return []

    history = []
    for table in tables:
        for record in table.records:
            history.append({
                "time": record.get_time().isoformat(),
                "battery_level": record.values.get("battery_level"),
                "joint_wear": record.values.get("joint_wear"),
            })
    return history
