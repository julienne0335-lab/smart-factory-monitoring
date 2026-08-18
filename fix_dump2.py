"""
fix_dump2.py — 트리거 없이 새로 뜬 덤프를 정리 (v2 대상: smart_factory_dump_notrig.sql)
동작은 fix_dump.py랑 완전히 동일, 입력 파일 이름만 다름.
"""

INPUT_FILE = "smart_factory_dump_notrig.sql"
OUTPUT_FILE = "smart_factory_dump_notrig_final.sql"

print(f"{INPUT_FILE} 읽는 중...")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("DEFINER=`root`@`localhost`", "")
content = content.replace("utf8mb4_uca1400_ai_ci", "utf8mb4_general_ci")
content = content.replace("NO_AUTO_CREATE_USER,", "")
content = content.replace(",NO_AUTO_CREATE_USER", "")
content = content.replace("NO_AUTO_CREATE_USER", "")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("완료!")
if "서울" in content:
    print("✅ 한글 정상")
if "NO_AUTO_CREATE_USER" not in content:
    print("✅ sql_mode 정리됨")
if "uca1400" not in content:
    print("✅ 콜레이션 정리됨")
