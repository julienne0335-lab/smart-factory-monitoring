-- ErrorAnalysis 테이블
-- Claude API로 분석한 결과(개별 로봇 분석 / 미해결 에러 배치 분석)를 저장한다.
--
-- analysis_type = 'individual' → robot_id 채워짐 (특정 로봇 1대 분석)
-- analysis_type = 'batch'      → robot_id는 NULL (미해결 에러 전체 분석)

CREATE TABLE ErrorAnalysis (
    analysis_id     INT AUTO_INCREMENT PRIMARY KEY,
    analysis_type   ENUM('individual', 'batch') NOT NULL,
    robot_id        INT NULL,                       -- individual일 때만 값 존재
    target_count    INT NOT NULL,                    -- 분석에 사용된 에러 건수
    summary         TEXT NOT NULL,                   -- 전체 요약
    root_cause      TEXT,                             -- 추정 원인
    severity        ENUM('낮음', '보통', '높음', '긴급') NOT NULL,
    recommendation  TEXT,                             -- 권장 조치
    raw_response    TEXT,                             -- Claude 원본 응답 (디버깅/참고용)
    created_at      DATETIME DEFAULT NOW(),

    FOREIGN KEY (robot_id) REFERENCES Robot(robot_id)
);