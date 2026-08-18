"""
db.py — DB 연결 설정
──────────────────────────────────────────────────────────────────────
[역할]
  Flask 백엔드에서 MySQL/MariaDB에 접속할 때 사용하는 연결 설정 파일.
  get_connection()을 호출하면 매번 새로운 연결을 반환함.

[왜 환경변수 기반으로 바꿨나]
  로컬 개발(MariaDB, SSL 불필요)과 배포 환경(Aiven MySQL, SSL 필수)이
  접속 정보가 완전히 다름. 코드를 두 벌로 관리하지 않고, .env 파일 /
  배포 플랫폼(Render)의 환경변수만 바꿔서 양쪽 다 대응하도록 구성함.

[.env 파일 사용법 — 로컬 개발용]
  1. pip install python-dotenv
  2. 프로젝트 루트에 .env 파일 생성
  3. .env는 절대 git에 커밋하지 말 것! .gitignore에 반드시 추가
     (팀 프로젝트에서 하드코딩된 비밀번호를 커밋했다가 노출되는 사고가
      흔한데, 그걸 근본적으로 막는 방법이 바로 이 env 분리임)

[로컬 개발 시 동작]
  .env 파일이 없거나 DB_* 값이 비어 있으면, 아래 기본값(localhost용
  MariaDB 설정)으로 자동 대체됨. 즉 예전처럼 별도 설정 없이도
  로컬 MariaDB 그대로 동작함 — 로컬 개발 흐름은 안 건드림.

[배포(Render) 시 동작]
  Render 대시보드의 Environment 탭에 DB_HOST, DB_PORT, DB_USER,
  DB_PASSWORD, DB_NAME, DB_SSL_CA를 등록해두면, 서버가 시작할 때
  자동으로 그 값들을 읽어서 Aiven MySQL에 SSL로 접속함.
"""

import os
import pymysql
from dotenv import load_dotenv

load_dotenv()  # .env 파일이 있으면 읽어서 os.environ에 반영 (없어도 에러 안 남)

# ── 접속 정보: 환경변수 우선, 없으면 로컬 기본값(MariaDB) 사용 ─────────
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "localhost"),
    "port":     int(os.environ.get("DB_PORT", 3306)),
    "user":     os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "030609"),
    "db":       os.environ.get("DB_NAME", "smart_factory"),
    "charset":  "utf8mb4",              # 한글 + 이모지 등 4바이트 문자 지원
    # DictCursor: SELECT 결과를 튜플 대신 딕셔너리로 반환
    # 예) row[0] 대신 row["robot_id"] 로 접근 가능
    "cursorclass": pymysql.cursors.DictCursor,
}

# Aiven처럼 SSL이 필요한 원격 DB에 접속할 때만 CA 인증서 경로를 지정.
# DB_SSL_CA 환경변수가 없으면(=로컬 MariaDB) SSL 옵션 자체를 안 붙임.
_ssl_ca_path = os.environ.get("DB_SSL_CA")
if _ssl_ca_path:
    DB_CONFIG["ssl"] = {"ca": _ssl_ca_path}
# ────────────────────────────────────────────────────────────────────


def get_connection():
    """
    DB 연결 객체(Connection)를 반환한다.

    [중요]
      이 함수를 호출하면 매번 새로운 연결을 열어서 반환함.
      사용 후 반드시 conn.close()로 닫아야 함.
      dao 계층에서는 항상 try/finally 블록으로 닫기를 보장함.

    [사용 예시]
      conn = get_connection()
      try:
          cursor = conn.cursor()
          cursor.execute("SELECT * FROM Robot")
          rows = cursor.fetchall()   # list of dict 반환 (DictCursor 덕분)
          conn.commit()              # INSERT/UPDATE/DELETE 후 반드시 commit
      except Exception:
          conn.rollback()            # 오류 시 롤백
          raise
      finally:
          conn.close()               # 연결 반드시 종료

    [반환값]
      pymysql.connections.Connection 객체
    """
    return pymysql.connect(**DB_CONFIG)