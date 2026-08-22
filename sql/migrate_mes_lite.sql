-- migrate_mes_lite.sql — 3순위(통계·MES-lite) 확장 마이그레이션
-- ──────────────────────────────────────────────────────────────────────
-- 로컬 개발 DB에 한 번 수동 적용할 것:
--   mysql -u root -p smart_factory < sql/migrate_mes_lite.sql
-- (docker-compose 스택은 sql/docker-init/03_mes_lite.sql이 컨테이너
--  최초 기동 시 자동으로 동일한 내용을 적용하므로 이 파일을 따로 실행할
--  필요 없음 — 이미 데이터가 있는 볼륨이면 docker-init 스크립트 자체가
--  재실행되지 않기 때문에, docker 볼륨을 이미 만든 뒤라면 컨테이너 안에서
--  이 파일을 직접 mysql 클라이언트로 실행해야 함)

-- ── 1. WorkLog에 품질 결과(result) 컬럼 추가 ────────────────────────────
ALTER TABLE WorkLog
    ADD COLUMN result ENUM('정상','불량') NOT NULL DEFAULT '정상' AFTER worker_type;

-- 기존 행 backfill: 이 프로젝트에는 실제 품질검사 결과 데이터가 없다.
-- worklog_dao.py 상단 WORK_TYPE_POWER_KW 주석과 동일한 원칙으로, 일반적인
-- 산업용 조립라인 불량률(2~5%대)을 참고한 "추정치"로 임의 3%를 불량 처리한다.
-- 통계 목적의 근사치이며 실제 품질 검사 결과가 아님을 발표/문서에서 밝힐 것.
UPDATE WorkLog SET result = IF(RAND() < 0.03, '불량', '정상');

-- ── 2. ProductionTarget(목표 생산량) 테이블 신설 ────────────────────────
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
