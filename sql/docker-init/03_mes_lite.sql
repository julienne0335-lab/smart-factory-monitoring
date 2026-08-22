-- 03_mes_lite.sql — docker-entrypoint-initdb.d 자동 실행용 MES-lite 확장
--
-- 원본은 sql/migrate_mes_lite.sql (로컬 개발 DB에 수동 적용하는 버전).
-- 02_triggers.sql 다음에 실행되도록 파일명을 03으로 시작함 (init 스크립트는
-- 알파벳 순 실행). 01(스키마+더미데이터)이 먼저 적재된 뒤라야 WorkLog/Line
-- 테이블이 존재하므로 이 순서가 중요함.
--
-- 트리거 로직처럼 여기도 원본과 내용을 맞춰서 함께 수정할 것.

SET NAMES utf8mb4;

ALTER TABLE WorkLog
    ADD COLUMN result ENUM('정상','불량') NOT NULL DEFAULT '정상' AFTER worker_type;

UPDATE WorkLog SET result = IF(RAND() < 0.03, '불량', '정상');

CREATE TABLE IF NOT EXISTS ProductionTarget (
    target_id     INT NOT NULL AUTO_INCREMENT,
    line_id       INT NOT NULL,
    period_type   ENUM('DAILY','WEEKLY','MONTHLY') NOT NULL,
    period_start  DATE NOT NULL,
    target_count  INT NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (target_id),
    UNIQUE KEY uq_target_line_period (line_id, period_type, period_start),
    KEY idx_target_line (line_id),
    CONSTRAINT fk_target_line FOREIGN KEY (line_id) REFERENCES Line (line_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
