-- trigger_setup.sql — 트리거 2개를 데이터 로드가 끝난 뒤 별도로 생성
SET NAMES utf8mb4;

DELIMITER $$

CREATE TRIGGER battery_status_update
BEFORE UPDATE ON Robot
FOR EACH ROW
BEGIN
    IF NEW.battery_level <= NEW.warning_threshold THEN
        SET NEW.status = '충전중';
    ELSE
        SET NEW.status = '가동중';
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

DELIMITER ;
