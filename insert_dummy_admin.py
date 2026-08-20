"""
insert_dummy_admin.py — Admin(로그인 계정) 테스트 데이터 생성 — 10단계(로그인/권한) 신규
──────────────────────────────────────────────────────────────────────────────
[역할]
  로그인 기능을 테스트해볼 수 있도록 Admin 테이블에 계정을 채워 넣는다.

[생성하는 계정]
  - 공장 반장(슈퍼) 3명 — 공장(factory_id 1~3)마다 1명, line_id는 NULL
  - 라인 반장(일반) 15명 — 라인(line_id 1~15)마다 1명, factory_id는 NULL

[비밀번호]
  전부 테스트용 비밀번호 "test1234!" 로 통일 (실제 서비스라면 각자 다르게,
  그리고 이런 스크립트로 평문을 다루지도 않았을 것). 저장 직전에
  werkzeug의 generate_password_hash()로 해싱해서 DB에는 해시값만 들어간다.

[주의]
  login_id는 UNIQUE 제약이 걸려 있어서, 이미 실행한 적이 있다면
  두 번째 실행 시 IntegrityError(중복 키 에러)가 난다. 딱 한 번만 실행하면 됨.
"""

import pymysql
from werkzeug.security import generate_password_hash

# ─────────────────────────────────────────
# 1. DB 연결 (insert_dummy_error.py와 동일한 설정)
# ─────────────────────────────────────────
conn = pymysql.connect(
    host='127.0.0.1',
    user='root',
    password='030609',     # ← 본인 비밀번호로 변경
    database='smart_factory',
    charset='utf8mb4'
)
cursor = conn.cursor()
print("DB 연결 성공!")

TEST_PASSWORD_HASH = generate_password_hash("test1234!")

# ─────────────────────────────────────────
# 2. 공장 반장(슈퍼) 3명 — factory_id 1~3, line_id는 NULL
#    (Factory 이름과 순서를 맞추려면 실제 Factory 테이블 순서를 확인해서
#     이름만 바꿔도 됨 — 여기서는 insert_dummy.py 기준 1=서울/2=부산/3=인천으로 가정)
# ─────────────────────────────────────────
factory_names = {1: "서울", 2: "부산", 3: "인천"}

factory_admins = []
for factory_id, name in factory_names.items():
    factory_admins.append((
        factory_id,                    # factory_id
        None,                          # line_id
        f"{name}공장 반장",              # name
        f"{name.lower()}_super",       # login_id (예: seoul_super)
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
