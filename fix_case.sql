-- fix_case.sql
-- Windows MariaDB(대소문자 구분 안 함) → Aiven MySQL(대소문자 구분함) 이전 과정에서
-- 테이블명이 전부 소문자로 저장된 걸 원래 설계(DDL 문서) 그대로 맞추는 스크립트.

SET NAMES utf8mb4;

-- 1. 기존 뷰 삭제 (지금 소문자 테이블을 참조하고 있어서, 테이블명 바꾸기 전에 먼저 지워야 함)
DROP VIEW IF EXISTS robot_view;
DROP VIEW IF EXISTS safetyevent_view;

-- 2. 테이블명을 원래 설계 그대로 대소문자 교정
RENAME TABLE
  `admin`         TO `Admin`,
  `factory`       TO `Factory`,
  `line`          TO `Line`,
  `lineerror`     TO `LineError`,
  `maintenance`   TO `Maintenance`,
  `robot`         TO `Robot`,
  `roboterror`    TO `RobotError`,
  `safetyevent`   TO `SafetyEvent`,
  `worklog`       TO `WorkLog`,
  `erroranalysis` TO `ErrorAnalysis`;

-- 3. 뷰 재생성 (VIEW 확정본 그대로)
CREATE VIEW Robot_View AS
SELECT r.*, l.name AS line_name, l.status AS line_status,
       f.name AS factory_name, f.location AS factory_location
FROM Robot r
JOIN Line l ON r.line_id = l.line_id
JOIN Factory f ON l.factory_id = f.factory_id;

CREATE VIEW SafetyEvent_View AS
SELECT s.*, r.model_name, l.name AS line_name, f.name AS factory_name
FROM SafetyEvent s
JOIN Robot r ON s.robot_id = r.robot_id
JOIN Line l ON r.line_id = l.line_id
JOIN Factory f ON l.factory_id = f.factory_id;
