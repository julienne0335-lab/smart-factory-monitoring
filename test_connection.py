"""
test_connection.py — Aiven MySQL 접속 테스트

[사용법]
  1. 이 파일, db.py, .env, ca.pem을 같은 폴더에 둔다
  2. pip install pymysql python-dotenv --break-system-packages (또는 그냥 pip install)
  3. python test_connection.py 실행

[기대 결과]
  ✅ 접속 성공, MySQL 버전, 현재 DB 이름 출력
  ✅ 예제 테이블 생성 → 삽입 → 조회 → 삭제까지 성공하면 SSL 접속 완전 정상
"""

from db import get_connection


def main():
    print("Aiven MySQL 접속 시도 중...")
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT VERSION() AS version, DATABASE() AS db_name")
        info = cursor.fetchone()
        print(f"✅ 접속 성공!")
        print(f"   MySQL 버전: {info['version']}")
        print(f"   현재 DB: {info['db_name']}")

        # 간단한 쓰기/읽기 테스트 (트리거·인덱스 없이도 기본 SSL 연결 자체를 검증)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connection_test (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message VARCHAR(100)
            )
        """)
        cursor.execute(
            "INSERT INTO connection_test (message) VALUES (%s)",
            ("hello from local db.py",)
        )
        conn.commit()

        cursor.execute("SELECT * FROM connection_test ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        print(f"✅ 쓰기/읽기 테스트 성공: {row}")

        cursor.execute("DROP TABLE connection_test")
        conn.commit()
        print("✅ 테스트 테이블 정리 완료")

    except Exception as e:
        conn.rollback()
        print(f"❌ 실패: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()