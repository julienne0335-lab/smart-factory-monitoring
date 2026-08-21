-- trigger_setup.sql — 트리거 4개 (기존 2개 + 신규 2개)
--
-- ⚠️ HeidiSQL 사용 안내 (중요)
-- HeidiSQL은 이 파일을 통째로 "실행"(F9, 전체 실행)하면 DELIMITER 처리를
-- 못 알아듣고 트리거 본문 안의 세미콜론(;)에서 문장을 잘라버려서 에러가
-- 납니다. 그래서 이 파일에는 DELIMITER를 아예 쓰지 않았습니다.
--
-- 대신 아래를 "각 STEP 블록을 마우스로 통째로 드래그해서 선택 → F9"로
-- 하나씩 실행해주세요. (전체 파일을 한 번에 실행하지 말고, STEP 단위로
-- 나눠서 실행하는 것이 핵심입니다 — 한 STEP = CREATE TRIGGER ... END; 까지
-- 전부 선택한 뒤 실행)
--
-- STEP 0은 여러 줄이지만 전부 한 줄짜리 독립 문장이라 통째로 선택해서
-- 한 번에 실행해도 안전합니다.

SET NAMES utf8mb4;

-- ═══════════════════════════════════════════════════════════════════════
-- STEP 0 — 기존 트리거 삭제 (재실행 안전하게, 4줄 전부 선택 후 F9)
-- ═══════════════════════════════════════════════════════════════════════
DROP TRIGGER IF EXISTS battery_status_update;
DROP TRIGGER IF EXISTS robot_error_status;
DROP TRIGGER IF EXISTS line_error_cascade;
DROP TRIGGER IF EXISTS line_error_resolve;


-- ═══════════════════════════════════════════════════════════════════════
-- STEP 1 — battery_status_update (기존 트리거 — 버그 수정)
--
--    [발견한 문제]
--    기존 버전은 Robot 테이블에 어떤 UPDATE가 오든(배터리가 실제로
--    바뀌지 않았어도) 무조건 battery_level 기준으로 NEW.status를
--    재계산해서 덮어썼음. 그 결과 robot_error_status 트리거가
--    "UPDATE Robot SET status='오류정지'"를 실행해도, 이 BEFORE UPDATE
--    트리거가 곧바로 재실행되면서 배터리가 충분한 로봇은 status가 다시
--    '가동중'으로 되돌아가버림 — RobotError를 등록해도 배터리가 넉넉하면
--    실제로는 오류정지로 안 바뀌는 silent failure가 있었음.
--    (STEP 3의 line_error_cascade도 로봇 status를 직접 UPDATE하므로
--     고치지 않으면 똑같이 무력화됨)
--
--    [수정]
--    "배터리 값 자체가 이번 UPDATE로 실제 바뀔 때만" 배터리 기준 로직을
--    적용하도록 조건을 추가함. 배터리와 무관한 이유로 status만 바꾸는
--    UPDATE(로봇 오류 등록, 라인장애 연쇄 등)는 이제 이 트리거에게
--    간섭받지 않고 의도한 값 그대로 저장됨.
--
--    ↓↓↓ 여기서부터 맨 아래 세미콜론(;)까지 통째로 선택해서 F9 ↓↓↓
-- ═══════════════════════════════════════════════════════════════════════
CREATE TRIGGER battery_status_update
BEFORE UPDATE ON Robot
FOR EACH ROW
BEGIN
    IF NEW.battery_level <> OLD.battery_level THEN
        IF NEW.battery_level <= NEW.warning_threshold THEN
            SET NEW.status = '충전중';
        ELSE
            SET NEW.status = '가동중';
        END IF;
    END IF;
END;


-- ═══════════════════════════════════════════════════════════════════════
-- STEP 2 — robot_error_status (기존 트리거 — 내용 변경 없음)
--    STEP 1 수정 덕분에 이제 배터리 상태와 무관하게 항상 실제로 동작함.
--
--    ↓↓↓ 여기서부터 맨 아래 세미콜론(;)까지 통째로 선택해서 F9 ↓↓↓
-- ═══════════════════════════════════════════════════════════════════════
CREATE TRIGGER robot_error_status
AFTER INSERT ON RobotError
FOR EACH ROW
BEGIN
    UPDATE Robot
    SET status = '오류정지'
    WHERE robot_id = NEW.robot_id;
END;


-- ═══════════════════════════════════════════════════════════════════════
-- STEP 3 — line_error_cascade (신규) — "지점장애 → 라인 전체 가동 중단" 대응
--
--    구조_.pdf 8절에서 설계한 트랜잭션 원자성 패턴 구현:
--      "라인장애로그 INSERT + 소속 로봇 전체 상태 일괄 반영"
--      → AFTER INSERT 트리거이므로 원본 INSERT와 같은 트랜잭션에서
--        함께 성공/실패함 (트리거 내부에서 에러가 나면 LineError INSERT
--        자체도 롤백됨 — "하나라도 실패 시 전체 rollback" 요구 충족)
--
--    [로봇 개별 RobotError를 새로 만들지 않은 이유]
--    RobotError.error_type ENUM에는 '센서이상'/'충돌'/'낙상'/'과부하'/
--    '통신오류'만 있고 "상위 라인장애로 인한 연쇄 정지"에 해당하는 값이
--    없음. 로봇이 스스로 오류를 감지한 게 아니라 라인 전체가 내려가서
--    같이 멈춘 것이므로, 개별 오류 이력을 억지로 만드는 대신
--    Robot.status만 '오류정지'로 반영하는 쪽이 의미상 더 정확하다고 판단함.
--
--    ↓↓↓ 여기서부터 맨 아래 세미콜론(;)까지 통째로 선택해서 F9 ↓↓↓
-- ═══════════════════════════════════════════════════════════════════════
CREATE TRIGGER line_error_cascade
AFTER INSERT ON LineError
FOR EACH ROW
BEGIN
    UPDATE Line
    SET status = '정지'
    WHERE line_id = NEW.line_id;

    UPDATE Robot
    SET status = '오류정지'
    WHERE line_id = NEW.line_id;
END;


-- ═══════════════════════════════════════════════════════════════════════
-- STEP 4 — line_error_resolve (신규) — cascade의 반대 방향, 처리완료 시 복구
--
--    LineError.status가 '미처리' → '완료'로 바뀌는 순간에만 동작.
--      - Line.status를 '가동중'으로 되돌림
--      - 그 라인에서 현재 '오류정지'인 로봇을 배터리 기준으로 복구
--        (battery_level 자체는 안 건드리므로 battery_status_update가
--         또 끼어들어 값을 덮어쓰지 않음 — CASE로 직접 재계산해서 반영)
--
--    [알려진 한계 — 문서화해둠]
--    Robot 테이블에는 "왜 오류정지 상태가 됐는지"를 기록하는 컬럼이 없어서,
--    이 트리거는 그 라인의 로봇 중 현재 '오류정지'인 로봇을 전부 복구
--    대상으로 봄. 즉 같은 라인의 다른 로봇이 (라인장애와 무관하게) 개별
--    RobotError로 오류정지된 상태였다면, 그 로봇도 이 라인장애가
--    처리완료될 때 함께 복구되어버릴 수 있음. 더 정확히 하려면 Robot에
--    "정지 원인(robot_error / line_error)"을 남기는 컬럼을 추가해야 함
--    — 지금 스키마 범위 안에서는 이 정도가 현실적인 절충점으로 판단함.
--
--    ↓↓↓ 여기서부터 맨 아래 세미콜론(;)까지 통째로 선택해서 F9 ↓↓↓
-- ═══════════════════════════════════════════════════════════════════════
CREATE TRIGGER line_error_resolve
AFTER UPDATE ON LineError
FOR EACH ROW
BEGIN
    IF NEW.status = '완료' AND OLD.status <> '완료' THEN
        UPDATE Line
        SET status = '가동중'
        WHERE line_id = NEW.line_id;

        UPDATE Robot
        SET status = CASE
            WHEN battery_level <= warning_threshold THEN '충전중'
            ELSE '가동중'
        END
        WHERE line_id = NEW.line_id
          AND status = '오류정지';
    END IF;
END;


-- ═══════════════════════════════════════════════════════════════════════
-- STEP 5 — 확인
-- 왼쪽 트리에서 smart_factory → Triggers 펼쳐서 4개(battery_status_update,
-- robot_error_status, line_error_cascade, line_error_resolve) 다 보이면 완료.
-- ═══════════════════════════════════════════════════════════════════════
