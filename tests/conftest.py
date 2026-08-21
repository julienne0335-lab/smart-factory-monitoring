"""
conftest.py — pytest 공통 설정 파일
──────────────────────────────────────────────────────────────────────
[역할]
  pytest는 이 파일이 있는 걸 보고 "여기가 테스트 설정 루트구나"라고
  인식한다. 특별한 코드를 안 넣어도 pytest가 자동으로 읽어감.

[여기서 하는 일: sys.path에 프로젝트 루트 추가]
  이 tests/ 폴더는 프로젝트 루트(app.py, service/, dao/ 가 있는 곳)의
  하위 폴더다. 그런데 pytest를 실행하면 기본적으로 "tests 폴더 자체"만
  파이썬이 코드를 찾는 경로(sys.path)에 들어가고, 그 위에 있는
  프로젝트 루트는 안 들어간다.

  그래서 테스트 코드에서 `from service import error_service`처럼
  프로젝트 루트 기준으로 import하면 "ModuleNotFoundError: No module
  named 'service'" 에러가 난다.

  아래 두 줄이 이 문제를 해결한다:
    1. 이 파일(conftest.py)의 절대 경로를 구한다
    2. 그 경로에서 한 단계 위(tests/의 부모 = 프로젝트 루트)를
       sys.path 맨 앞에 끼워 넣는다

[전제 조건]
  이 tests/ 폴더는 반드시 app.py, service/, dao/ 와 같은 위치
  (프로젝트 루트) 바로 아래에 있어야 한다.
    smart_factory/          ← 프로젝트 루트
    ├── app.py
    ├── db.py
    ├── extensions.py
    ├── dao/
    ├── service/
    ├── routes/
    └── tests/               ← 이 폴더 (conftest.py가 여기 있음)
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
