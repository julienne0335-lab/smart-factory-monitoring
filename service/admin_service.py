# =============================================================================
# admin_service.py — 10단계(로그인/권한) 신규
# 역할: 로그인 비즈니스 로직 처리
# - DAO에서 관리자 정보를 받아와서 비밀번호를 검증
# - 세션에 저장할 "안전한" 형태(dict)로 가공해서 반환
#   (password 해시값은 여기서 걸러내고 절대 세션까지 넘기지 않음)
# =============================================================================

from werkzeug.security import check_password_hash, generate_password_hash

from dao import admin_dao


def hash_password(plain_password):
    """
    평문 비밀번호를 해시로 변환한다. (계정 생성/시드 스크립트에서 사용)
    werkzeug 기본 알고리즘(pbkdf2:sha256) 사용 — 별도 패키지 설치 불필요
    (Flask를 설치하면 werkzeug가 같이 딸려옴).
    """
    return generate_password_hash(plain_password)


def login(login_id, password):
    """
    로그인 아이디 + 비밀번호를 검증하고, 성공하면 세션에 저장할 dict를 반환한다.

    [처리 순서]
      1. login_id로 Admin 조회 → 없으면 실패
      2. 입력한 평문 비밀번호를 DB의 해시값과 비교 → 다르면 실패
      3. 성공하면, password 해시값은 빼고 나머지 정보만 dict로 반환
         (이 dict가 그대로 routes/admin.py에서 session['admin']에 저장됨)

    [파라미터]
      login_id (str): 로그인 아이디
      password (str): 입력한 평문 비밀번호

    [반환값]
      dict: 로그인 성공 시 세션에 저장할 관리자 정보
            {admin_id, login_id, name, role, factory_id, line_id}
      None: 아이디가 없거나 비밀번호가 틀린 경우
            (일부러 "아이디가 없음" / "비밀번호가 틀림"을 구분하지 않음 —
             구분해서 알려주면 공격자가 "이 아이디는 존재한다"는 걸
             알아낼 수 있는 정보 노출(계정 열거 공격)로 이어지기 때문)
    """
    admin = admin_dao.get_admin_by_login_id(login_id)
    if admin is None:
        return None

    if not check_password_hash(admin['password'], password):
        return None

    return {
        "admin_id": admin['admin_id'],
        "login_id": admin['login_id'],
        "name": admin['name'],
        "role": admin['role'],
        "factory_id": admin['factory_id'],
        "line_id": admin['line_id'],
    }
