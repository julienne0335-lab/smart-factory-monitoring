-- 02_triggers.sql — docker-entrypoint-initdb.d 자동 실행용 트리거 정의
--
-- 원본은 sql/trigger_setup.sql (HeidiSQL에서 STEP 단위로 수동 실행하도록
-- DELIMITER 없이 작성됨 — HeidiSQL이 DELIMITER를 못 알아듣기 때문).
-- 여기서는 실제 mysql 클라이언트(컨테이너 초기화 스크립트가 사용)가
-- DELIMITER를 정상 지원하므로, 같은 트리거 4개를 자동 실행 가능한 형태로
-- 옮겨 적었다. 트리거 로직을 바꿀 때는 두 파일을 함께 수정할 것.
--
-- 01_schema.sql(= sql/smart_factory_dump_notrig_final.sql을 그대로 마운트)
-- 다음에 실행되도록 파일명을 02로 시작함 (init 스크립트는 알파벳 순 실행).

SET NAMES utf8mb4;

DROP TRIGGER IF EXISTS battery_status_update;
DROP TRIGGER IF EXISTS robot_error_status;
DROP TRIGGER IF EXISTS line_error_cascade;
DROP TRIGGER IF EXISTS line_error_resolve;

DELIMITER $$

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
END$$

CREATE TRIGGER robot_error_status
AFTER INSERT ON RobotError
FOR EACH ROW
BEGIN
    UPDATE Robot
    SET status = '오류정지'
    WHERE robot_id = NEW.robot_id;
END$$

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
END$$

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
END$$

DELIMITER ;
