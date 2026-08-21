"""
fix_dump.py — mysqldump 결과물을 Aiven(MySQL) import용으로 정리 (v2)

[하는 일]
  1. DEFINER=`root`@`localhost` 구문 제거 (권한 에러 방지)
  2. MariaDB 전용 콜레이션(utf8mb4_uca1400_ai_ci)을 MySQL이 아는 걸로 치환
  3. MySQL 8에서 삭제된 sql_mode 값(NO_AUTO_CREATE_USER) 제거
     (트리거/뷰 정의부에 mysqldump가 자동으로 넣어주는 SET sql_mode 구문에 포함됨)
  전부 UTF-8로 명시적으로 읽고 써서 한글 깨질 여지 없음.

[사용법]
  원본 덤프(smart_factory_dump.sql)가 있는 폴더에서:
    python fix_dump.py
  → smart_factory_dump_final.sql 생성됨 (기존 파일 있으면 덮어씀)
"""

INPUT_FILE = "smart_factory_dump.sql"
OUTPUT_FILE = "smart_factory_dump_final.sql"

print(f"{INPUT_FILE} 읽는 중... (76MB라 몇 초 걸릴 수 있음)")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    content = f.read()

before_len = len(content)

# 1. DEFINER 제거
content = content.replace("DEFINER=`root`@`localhost`", "")

# 2. MariaDB 전용 콜레이션 → MySQL 호환 콜레이션으로 치환
content = content.replace("utf8mb4_uca1400_ai_ci", "utf8mb4_general_ci")

# 3. MySQL 8+에서 제거된 sql_mode 값 삭제 (콤마 위치 두 경우 다 처리)
content = content.replace("NO_AUTO_CREATE_USER,", "")
content = content.replace(",NO_AUTO_CREATE_USER", "")
content = content.replace("NO_AUTO_CREATE_USER", "")  # 혹시 단독으로 있는 경우 대비

print(f"{OUTPUT_FILE} 쓰는 중...")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("완료!")
print(f"원본 길이: {before_len:,}자 / 결과 길이: {len(content):,}자")

if "서울" in content:
    print("✅ 한글 정상 확인됨 ('서울' 문자열 발견)")
else:
    print("⚠️ '서울' 문자열을 못 찾음 — 원본 데이터 자체를 다시 확인해보세요")

if "NO_AUTO_CREATE_USER" not in content:
    print("✅ NO_AUTO_CREATE_USER 제거 확인됨")
if "uca1400" not in content:
    print("✅ MariaDB 전용 콜레이션 제거 확인됨")