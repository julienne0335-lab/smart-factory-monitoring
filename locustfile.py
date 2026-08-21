"""
locustfile.py — Locust 부하 테스트 시나리오
──────────────────────────────────────────────────────────────────────
[Locust가 하는 일]
  가상의 사용자 여러 명이 동시에 웹사이트를 쓰는 상황을 흉내내서,
  서버가 몇 명까지 버티는지 / 응답이 얼마나 느려지는지를 측정하는 도구.
  pytest(로직 검증), Thunder/REST Client(기능 검증)와 달리
  이건 "성능"과 "동시 접속 한계"를 보는 단계임.

[설치]
  pip install locust

[실행 방법]
  1. 터미널에서 프로젝트 아무 폴더에서나:
     locust -f locustfile.py --host=https://실제-render-주소.onrender.com
  2. 실행하면 "Starting web interface at http://localhost:8089" 라고 뜸
  3. 브라우저로 http://localhost:8089 접속
  4. Number of users(동시 사용자 수), Spawn rate(초당 몇 명씩 늘릴지) 입력
     → 처음엔 Users=5, Spawn rate=1 정도로 작게 시작 추천 (무료 티어라 과부하 주의)
  5. "Start swarming" 클릭 → 실시간으로 응답시간/실패율 그래프가 뜸
  6. 충분히 봤으면 "Stop" 누르면 종료됨

[시나리오 설계 — 왜 이렇게 짰는지]
  실제 대시보드를 보는 사람처럼 "로봇 목록 확인 → 로봇 상세 → 워크로그/에러 확인"
  순서로 GET(읽기) 요청 위주로 구성함.

  POST(에러 등록)는 일부러 뺐음 — 이유:
    1. 부하 테스트에서 반복 호출하면 실제 DB에 가짜 에러가 계속 쌓임
    2. 실시간 알림(socketio.emit)도 매번 발생해서 부하 테스트의 목적(순수 조회 성능)과 안 맞음
    3. 실제 운영에서도 "에러 등록"은 드물게 일어나는 이벤트지, 초당 수십 번 발생하는
       트래픽 패턴이 아님 (반면 "목록 조회"는 계속 반복되는 트래픽이 맞음)

  robot_id는 1~75 사이에서 무작위로 골라서 요청함 (실제 로봇 75대 범위와 동일).
  name= 파라미터를 꼭 붙인 이유: 안 붙이면 robot_id가 다른 요청(/api/robots/1,
  /api/robots/2, ...)이 Locust 결과표에서 전부 따로따로 집계돼서 표가 무의미하게
  길어짐. name=으로 "/api/robots/[id]"처럼 하나로 묶어야 통계가 의미 있어짐.
"""

import random

from locust import HttpUser, between, task


class DashboardUser(HttpUser):
    # 실제 사람이 클릭하는 속도를 흉내냄: 요청 사이 1~3초 대기
    # (대기시간 없이 쏘면 "봇 트래픽" 테스트가 되어버려서 실사용 패턴과 안 맞음)
    wait_time = between(1, 3)

    # ── 자주 발생하는 요청 (weight 높음) ─────────────────────────────

    @task(5)
    def view_robot_list(self):
        """대시보드 첫 화면 — 전체 로봇 목록 (제일 자주 호출됨)"""
        self.client.get("/api/robots", name="/api/robots")

    @task(3)
    def view_robot_detail(self):
        """로봇 하나 클릭해서 상세 보기"""
        robot_id = random.randint(1, 75)
        self.client.get(f"/api/robots/{robot_id}", name="/api/robots/[id]")

    @task(3)
    def view_unresolved_errors(self):
        """에러 현황 페이지 — 미해결 에러 목록"""
        self.client.get("/api/errors/unresolved", name="/api/errors/unresolved")

    # ── 중간 빈도 요청 ─────────────────────────────────────────────

    @task(2)
    def view_worklogs_by_robot(self):
        """특정 로봇의 작업 이력 확인"""
        robot_id = random.randint(1, 75)
        self.client.get(
            f"/api/worklogs/robot/{robot_id}", name="/api/worklogs/robot/[id]"
        )

    @task(2)
    def view_error_stats(self):
        """로봇별 에러 통계 (관리자가 주기적으로 확인)"""
        self.client.get("/api/errors/stats/robot", name="/api/errors/stats/robot")

    @task(1)
    def view_long_worklogs(self):
        """장시간 작업 경고 목록"""
        self.client.get("/api/worklogs/long", name="/api/worklogs/long")

    # ── 무거운 요청 (weight 낮게 — 100만 건 중 큰 범위 조회라 부하가 큼) ──

    @task(1)
    def view_worklogs_by_date_range(self):
        """
        날짜 범위 워크로그 조회 — 응답 크기가 수백 KB~십수 MB까지 나올 수 있는
        가장 무거운 요청. weight를 1로 낮게 잡아서 "가끔 누군가 리포트를 뽑는"
        빈도로 설정함. 사용자 수를 늘릴 때 이 요청이 병목이 되는지 지켜볼 것.
        """
        self.client.get(
            "/api/worklogs/date?start=2024-01-01&end=2024-01-07",
            name="/api/worklogs/date (1주일 범위)",
        )

    @task(1)
    def view_dashboard_page(self):
        """대시보드 HTML 페이지 자체 (정적 파일 + 서버 렌더링 부하 확인용)"""
        self.client.get("/", name="/ (대시보드 페이지)")
