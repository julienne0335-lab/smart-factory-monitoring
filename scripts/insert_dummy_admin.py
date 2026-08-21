"""
insert_dummy_admin.py — Admin(로그인 계정) 테스트 데이터 생성 — 10단계(로그인/권한) 신규
──────────────────────────────────────────────────────────────────────────────
[역할]
  로그인 기능을 테스트해볼 수 있도록 Admin 테이블에 계정을 채워 넣는다.

[생성하는 계정]
  - 공장 반장(슈퍼) 3명 — 공장(factory_id 1~3)마다 1명, line_id는 NULL
  - 라인 반장(일반) 15명 — 라인(line_id 1~15)마다 1명, factory_id는 NULL

[어느 DB에 들어가나 — 매번 .env를 고쳤다 지웠다 안 해도 됨]
  처음엔 ".env에 Aiven 값을 잠깐 넣었다가 끝나면 지우는" 방식으로 안내했는데,
  매번 편집/삭제를 반복하는 게 번거롭고 "지우는 걸 깜빡하면" 그 뒤로 로컬
  개발 내내 실수로 Aiven에 붙는 위험도 있었음. 그래서 --aiven 옵션으로 바꿈:

    python insert_dummy_admin.py           → 기본 .env 사용 (로컬 MariaDB)
    python insert_dummy_admin.py --aiven   → .env.aiven 사용 (Aiven MySQL)

  .env.aiven은 Aiven 접속정보만 따로 담아두는 별도 파일 (.gitignore에 이미
  등록되어 있어서 git에 올라가지 않음). 기존 .env는 이 스크립트를 어떤
  옵션으로 실행하든 전혀 건드리지 않으므로, 평소 로컬 개발 흐름과 완전히
  분리되어 안전함. .env.aiven이 아직 없다면 .env.aiven.example을 복사해서
  ".env.aiven"으로 저장하고 실제 Aiven 값을 채워넣으면 됨.

[비밀번호]
  전부 테스트용 비밀번호 "test1234!" 로 통일 (실제 서비스라면 각자 다르게,
  그리고 이런 스크립트로 평문을 다루지도 않았을 것). 저장 직전에
  werkzeug의 generate_password_hash()로 해싱해서 DB에는 해시값만 들어간다.

[주의]
  login_id는 UNIQUE 제약이 걸려 있어서, 같은 DB에 두 번 실행하면
  IntegrityError(중복 키 에러)가 난다. DB 하나당 딱 한 번만 실행하면 됨.
"""

import sys

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# ─────────────────────────────────────────
# 1. 대상 DB 결정: --aiven 옵션 여부로 어느 .env 파일을 읽을지 정한다.
#    - db.py도 내부적으로 load_dotenv()를 호출하지만, python-dotenv는
#      "이미 os.environ에 값이 있으면 덮어쓰지 않는" 게 기본 동작이라,
#      db.py를 import하기 "전에" 여기서 먼저 .env.aiven을 읽어두면
#      그 값이 그대로 우선권을 가진다 (db.py의 load_dotenv()는 무효화됨).
# ─────────────────────────────────────────
if '--aiven' in sys.argv:
    load_dotenv('.env.aiven')
    print("[Aiven 모드] .env.aiven 값으로 접속합니다.")
else:
    print("[로컬 모드] 기본 .env(또는 db.py 기본값)로 접속합니다. "
          "Aiven에 넣으려면 --aiven 옵션을 붙여서 다시 실행하세요.")

from db import get_connection   # noqa: E402  (위 load_dotenv() 이후에 import해야 함)

conn = get_connection()
cursor = conn.cursor()
print("DB 연결 성공!")

TEST_PASSWORD_HASH = generate_password_hash("test1234!")

# ─────────────────────────────────────────
# 2. 공장 반장(슈퍼) 3명 — factory_id 1~3, line_id는 NULL
#    (Factory 이름과 순서를 맞추려면 실제 Factory 테이블 순서를 확인해서
#     이름만 바꿔도 됨 — 여기서는 insert_dummy.py 기준 1=서울/2=부산/3=인천으로 가정)
#
#    [주의] login_id는 "서울".lower() 처럼 한글에 .lower()를 써도 그대로
#    "서울"만 나옴 (한글엔 대소문자 개념이 없어서 아무 효과가 없음).
#    그래서 로그인 아이디용 로마자 표기를 별도로 명시함.
# ─────────────────────────────────────────
factories = [
    (1, "서울", "seoul"),
    (2, "부산", "busan"),
    (3, "인천", "incheon"),
]

factory_admins = []
for factory_id, display_name, romanized in factories:
    factory_admins.append((
        factory_id,                    # factory_id
        None,                          # line_id
        f"{display_name}공장 반장",       # name
        f"{romanized}_super",          # login_id (예: seoul_super)
        TEST_PASSWORD_HASH,            # password (해시)
        "슈퍼",                         # role
    ))

cursor.executemany(
    """INSERT INTO Admin (factory_id, line_id, name, login_id, password, role)
       VALUES (%s, %s, %s, %s, %s, %s)""",
    factory_admins
)
conn.commit()
print(f"공장 반장(슈퍼) {len(factory_admins)}명 삽입 완료!")
for _, _, _, login_id, _, _ in factory_admins:
    print(f"  - {login_id} / test1234!")


# ─────────────────────────────────────────
# 3. 라인 반장(일반) 15명 — line_id 1~15, factory_id는 NULL
# ─────────────────────────────────────────
line_admins = []
for line_id in range(1, 16):
    line_admins.append((
        None,                          # factory_id
        line_id,                       # line_id
        f"{line_id}라인 반장",           # name
        f"line{line_id}",              # login_id (예: line1)
        TEST_PASSWORD_HASH,            # password (해시)
        "일반",                         # role
    ))

cursor.executemany(
    """INSERT INTO Admin (factory_id, line_id, name, login_id, password, role)
       VALUES (%s, %s, %s, %s, %s, %s)""",
    line_admins
)
conn.commit()
print(f"라인 반장(일반) {len(line_admins)}명 삽입 완료!")
for _, _, _, login_id, _, _ in line_admins:
    print(f"  - {login_id} / test1234!")

cursor.close()
conn.close()
print("완료! 예) seoul_super / test1234! 또는 line1 / test1234! 로 로그인해보세요.")