"""
claude_service.py — Claude API를 활용한 에러 로그 분석 서비스
──────────────────────────────────────────────────────────────────────
[역할]
  RobotError 데이터를 Claude API에 보내서 원인 분석 / 심각도 / 권장 조치를
  받아오고, 결과를 ErrorAnalysis 테이블에 저장한다.

[기존 Service 계층과의 차이]
  robot_service, worklog_service, error_service는 "DB 데이터를 가공"하는
  역할이었다면, claude_service는 "외부 AI API를 호출"하는 역할을 추가로 가짐.
  그래도 원칙은 같음: DB 연결은 DAO(error_dao)가 담당, 이 파일은 비즈니스 로직만.

[두 가지 분석 모드]
  1. analyze_robot(robot_id)  → 로봇 1대의 에러 이력을 분석 (individual)
  2. analyze_unresolved_batch() → 미해결 에러 전체(최근 N건)를 한번에 분석 (batch)

[환경변수]
  .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 값이 있어야 함
  (python-dotenv가 자동으로 .env를 읽어서 os.environ에 넣어줌)
"""

import os
import json
from dotenv import load_dotenv
import anthropic

from dao import error_dao

# ── 환경변수 로드 + Claude 클라이언트 생성 ────────────────────────────
load_dotenv()  # .env 파일 읽어서 os.environ에 반영

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

MODEL_NAME = "claude-sonnet-5"


# ── 내부 헬퍼: 프롬프트 생성 ──────────────────────────────────────────

def _build_individual_prompt(robot_id, errors):
    """
    특정 로봇 1대의 에러 이력을 분석 요청하는 프롬프트를 만든다.

    [파라미터]
      robot_id (int): 분석 대상 로봇 ID
      errors (list of dict): error_dao.get_errors_by_robot()의 결과

    [반환값]
      str: Claude에게 보낼 프롬프트 텍스트
    """
    error_lines = []
    for e in errors:
        error_lines.append(
            f"- [{e['occurred_at']}] {e['error_type']} "
            f"(상태: {e['status']}) - {e['detail'] or '상세 없음'}"
        )
    error_text = "\n".join(error_lines)

    return f"""너는 스마트팩토리 휴머노이드 로봇 모니터링 시스템의 에러 분석 담당 AI야.
아래는 robot_id={robot_id} 로봇에서 발생한 에러 이력이야.

{error_text}

이 데이터를 바탕으로 다음 항목을 분석해서 반드시 JSON 형식으로만 답해줘.
설명, 마크다운 코드블록(```json 같은 것) 없이 순수 JSON 객체 하나만 출력해.

{{
  "summary": "전체 상황을 2~3문장으로 요약",
  "root_cause": "가장 유력한 원인 추정 (1~2문장)",
  "severity": "낮음 | 보통 | 높음 | 긴급 중 하나",
  "recommendation": "구체적인 권장 조치 (1~2문장)"
}}"""


def _build_batch_prompt(errors):
    """
    미해결 에러 전체(여러 로봇)를 한번에 분석 요청하는 프롬프트를 만든다.

    [파라미터]
      errors (list of dict): error_dao.get_unresolved_errors()의 결과

    [반환값]
      str: Claude에게 보낼 프롬프트 텍스트
    """
    error_lines = []
    for e in errors:
        error_lines.append(
            f"- robot_id={e['robot_id']} | [{e['occurred_at']}] {e['error_type']} "
            f"- {e['detail'] or '상세 없음'}"
        )
    error_text = "\n".join(error_lines)

    return f"""너는 스마트팩토리 휴머노이드 로봇 모니터링 시스템의 에러 분석 담당 AI야.
아래는 현재 미해결(status='미처리') 상태인 에러 목록이야. (여러 로봇에 걸쳐 있음)

{error_text}

이 데이터를 바탕으로 전체적인 경향을 분석해서 반드시 JSON 형식으로만 답해줘.
설명, 마크다운 코드블록 없이 순수 JSON 객체 하나만 출력해.

{{
  "summary": "전체 미해결 에러 현황을 3~4문장으로 요약 (특정 로봇/에러타입에 쏠림이 있는지 포함)",
  "root_cause": "공통적으로 보이는 원인 패턴 추정",
  "severity": "낮음 | 보통 | 높음 | 긴급 중 하나 (전체 상황 기준)",
  "recommendation": "우선적으로 조치해야 할 것 (구체적으로)"
}}"""


# ── 내부 헬퍼: API 호출 + 응답 파싱 ───────────────────────────────────

def _call_claude(prompt):
    """
    Claude API를 호출하고 응답 텍스트를 반환한다.

    [파라미터]
      prompt (str): 사용자 메시지로 보낼 프롬프트

    [반환값]
      str: Claude가 생성한 응답 텍스트 (원본, 파싱 전)
    """
    message = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    # content는 블록 리스트임. 텍스트 블록만 모아서 합침.
    return "".join(
        block.text for block in message.content if block.type == "text"
    )


def _parse_response(raw_text):
    """
    Claude 응답(JSON 문자열)을 dict로 파싱한다.
    혹시 모를 코드블록(```json ... ```)이 섞여 있으면 제거하고 시도한다.

    [파라미터]
      raw_text (str): Claude 원본 응답 텍스트

    [반환값]
      dict: {"summary", "root_cause", "severity", "recommendation"}
            파싱 실패 시 summary에 원본을 넣고 나머지는 기본값으로 채워서 반환
            (분석 자체가 실패해도 서버가 죽지 않도록 방어)
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        # ```json ... ``` 형태로 왔을 경우 앞뒤 코드블록 표시 제거
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    try:
        data = json.loads(cleaned)
        return {
            "summary": data.get("summary", ""),
            "root_cause": data.get("root_cause", ""),
            "severity": data.get("severity", "보통"),
            "recommendation": data.get("recommendation", ""),
        }
    except json.JSONDecodeError:
        # JSON 파싱 실패 시 방어 처리 — 원본 텍스트를 summary로 보존
        return {
            "summary": raw_text,
            "root_cause": "",
            "severity": "보통",
            "recommendation": "분석 응답 파싱에 실패했습니다. raw_response를 확인하세요.",
        }


# ── 외부 공개 함수: 개별 로봇 분석 ────────────────────────────────────

def analyze_robot(robot_id):
    """
    특정 로봇 1대의 에러 이력을 Claude API로 분석하고 결과를 저장한다.

    [파라미터]
      robot_id (int): 분석할 로봇 ID

    [반환값]
      dict: 저장된 분석 결과 (analysis_id 포함)
            에러 이력이 하나도 없으면 None 반환
    """
    errors = error_dao.get_errors_by_robot(robot_id)

    if not errors:
        return None

    prompt = _build_individual_prompt(robot_id, errors)
    raw_response = _call_claude(prompt)
    parsed = _parse_response(raw_response)

    analysis_id = error_dao.create_error_analysis(
        analysis_type="individual",
        robot_id=robot_id,
        target_count=len(errors),
        summary=parsed["summary"],
        root_cause=parsed["root_cause"],
        severity=parsed["severity"],
        recommendation=parsed["recommendation"],
        raw_response=raw_response,
    )

    return {
        "analysis_id": analysis_id,
        "analysis_type": "individual",
        "robot_id": robot_id,
        "target_count": len(errors),
        **parsed,
    }


# ── 외부 공개 함수: 미해결 에러 배치 분석 ─────────────────────────────

def analyze_unresolved_batch(limit=30):
    """
    미해결(status='미처리') 에러 최근 N건을 한번에 분석하고 결과를 저장한다.

    [파라미터]
      limit (int): 분석에 포함할 최대 에러 건수 (기본 30)

    [반환값]
      dict: 저장된 분석 결과 (analysis_id 포함)
            미해결 에러가 하나도 없으면 None 반환
    """
    errors = error_dao.get_unresolved_errors(limit=limit)

    if not errors:
        return None

    prompt = _build_batch_prompt(errors)
    raw_response = _call_claude(prompt)
    parsed = _parse_response(raw_response)

    analysis_id = error_dao.create_error_analysis(
        analysis_type="batch",
        robot_id=None,
        target_count=len(errors),
        summary=parsed["summary"],
        root_cause=parsed["root_cause"],
        severity=parsed["severity"],
        recommendation=parsed["recommendation"],
        raw_response=raw_response,
    )

    return {
        "analysis_id": analysis_id,
        "analysis_type": "batch",
        "robot_id": None,
        "target_count": len(errors),
        **parsed,
    }


# ── 외부 공개 함수: 분석 이력 조회 ────────────────────────────────────

def get_analysis_history(n=10):
    """
    최근 분석 이력(individual + batch)을 조회한다.
    - DB 조회만 하는 단순 위임이지만, 라우트가 "service만 호출한다"는
      아키텍처 원칙을 지키기 위해 이 함수를 통해 dao를 감쌈.

    [파라미터]
      n (int): 가져올 건수 (기본 10)

    [반환값]
      list of dict: 최근 분석 이력
    """
    return error_dao.get_recent_analyses(n)