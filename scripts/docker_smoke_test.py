# =============================================================================
# docker_smoke_test.py
# 역할: docker-compose 스택(18장)이 실제로 정상 동작하는지 확인하는 가벼운
#       스모크 테스트.
#
# [pytest 단위 테스트와 다른 이유]
#   tests/ 밑의 테스트는 DB/소켓을 전부 Mock으로 바꿔치기해서 "서비스 계층
#   로직"만 검증한다(빠르고, 컨테이너 없이도 항상 돌아감). 이 스크립트는
#   반대로 진짜 컨테이너 3개가 실제로 붙어서 동작하는지 — DB 초기화가
#   끝났는지, 앱이 응답하는지, API 한 건이 실제로 DB까지 왕복하는지 —
#   확인하는 것이 목적이라 성격이 다르다. 그래서 pytest 스위트에 넣지
#   않고 별도 스크립트로 둔다(scripts/의 다른 것들처럼 필요할 때 수동 실행).
#
# [사용법]
#   docker compose up -d 로 스택을 띄운 뒤:
#     python scripts/docker_smoke_test.py
#
# [의존성]
#   표준 라이브러리만 사용한다(urllib, json, subprocess) — 이 스크립트를
#   돌리려고 별도 패키지를 설치할 필요가 없게 하기 위함.
# =============================================================================

import json
import subprocess
import sys
import urllib.error
import urllib.request

# Windows 콘솔의 기본 인코딩(cp949)은 이 스크립트가 출력하는 한글을 그대로
# 못 받는 경우가 있다(파이프로 리다이렉트될 때 특히) — mqtt_bridge.py에서
# 이미 겪은 것과 같은 문제라 여기서도 동일하게 방어한다(17장 버그3 참고).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:5000"
FAILURES = []


def check(desc, ok):
    print(f"[{'OK  ' if ok else 'FAIL'}] {desc}")
    if not ok:
        FAILURES.append(desc)
    return ok


def _parse_json_if_possible(raw):
    """
    body가 JSON일 수도(API), HTML일 수도(로그인 페이지 등) 있다.
    JSON이 아니면 파싱을 포기하고 None을 반환한다 — 호출부는 status
    코드만으로도 충분히 검증 가능한 경우에 이 함수를 쓴다.
    """
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def http_request(method, path, body=None):
    """urllib로 간단히 요청 1건을 보내고 (status_code, parsed_json_or_None) 튜플을 반환한다."""
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, _parse_json_if_possible(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, _parse_json_if_possible(e.read())


def check_containers():
    """docker compose ps로 3개 컨테이너가 전부 Running(+ db는 Healthy)인지 확인"""
    try:
        # encoding="utf-8"을 명시하지 않으면 Windows에서 text=True가 기본
        # 로케일(cp949)로 디코딩을 시도하다가, docker CLI 출력에 섞인 UTF-8
        # 멀티바이트 문자("…" 등)에서 그대로 죽는다 — 17장에서 겪은 것과
        # 같은 종류의 콘솔 인코딩 버그라 여기서도 처음부터 피해간다.
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        check("docker compose ps 실행 (Docker Desktop이 켜져 있는지 확인)", False)
        print(f"       ↳ {e}")
        return

    services = {}
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        row = json.loads(line)
        services[row["Service"]] = row

    for name in ("db", "mosquitto", "app"):
        row = services.get(name)
        check(f"{name} 컨테이너가 떠 있음 (docker compose up -d 실행했는지 확인)",
              row is not None and row.get("State") == "running")

    db = services.get("db")
    if db is not None:
        check("db 컨테이너 헬스체크 통과 (healthcheck.sh)", db.get("Health") == "healthy")


def check_app_responds():
    status, _ = http_request("GET", "/login")
    check("GET /login → 200 (Flask 앱이 응답함)", status == 200)


def check_robots_api():
    status, body = http_request("GET", "/api/robots")
    ok = status == 200 and isinstance(body, list) and len(body) > 0
    check(f"GET /api/robots → 200 + 로봇 목록 (DB 덤프가 로드됐는지 확인, 실제 {len(body) if isinstance(body, list) else '?'}대)", ok)


def check_maintenance_roundtrip():
    """
    POST /api/maintenance → GET /api/maintenance/robot/<id> 왕복으로
    "API가 실제 DB에 쓰고 읽는다"까지 한 번에 확인한다 (19장 확장).
    """
    status, body = http_request("POST", "/api/maintenance", {
        "robot_id": 1,
        "part_name": "스모크테스트",
        "maint_type": "정기점검",
    })
    if not check("POST /api/maintenance → 201", status == 201 and isinstance(body, dict)):
        return

    maint_id = body["maint_id"]
    status, records = http_request("GET", "/api/maintenance/robot/1")
    found = isinstance(records, list) and any(r["maint_id"] == maint_id for r in records)
    check(f"GET /api/maintenance/robot/1 → 방금 등록한 maint_id={maint_id} 포함", found)


def main():
    check_containers()
    check_app_responds()
    check_robots_api()
    check_maintenance_roundtrip()

    print()
    if FAILURES:
        print(f"{len(FAILURES)}건 실패:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("전부 통과.")


if __name__ == "__main__":
    main()
