"""announcement_analyzer.py — 정부지원사업 '공고문'을 분석한다.

기존 ``evaluation_service.parse_announcement`` 는 평가기준·배점만 뽑는다(자격·서류 등은 제외).
본 모듈은 공고문 파일(DOCX/PDF/HWP/TXT)을 읽어 **종합 분석**한다.

  - 평가기준·배점        : ``EvaluationService.parse_announcement`` 재사용
  - 핵심 정보(종합)      : 지원대상·자격·지원금액·신청마감·제출서류·지원내용·가점·유의사항
                          (AI 키 있으면 구조화 추출, 없으면 정규식 휴리스틱)

목적: 사업계획서를 쓰기 전에 "무엇을 평가하고, 무엇을 제출해야 하며, 언제까지인지" 를
한눈에 정리하고, 평가기준을 ``bizplan_autopilot`` 채점에 그대로 넘긴다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .doc_text_extract import extract_text

# 휴리스틱 패턴(AI 미연결 시)
_DEADLINE_RE = re.compile(r"(접수|신청|모집|제출).{0,6}(기간|마감|기한|일정)|~?\s*\d{4}[.\-/]\s?\d{1,2}[.\-/]\s?\d{1,2}")
_AMOUNT_RE = re.compile(r"\d[\d,]*\s*(억원|억|백만원|천만원|만원|원)\b")
_DOC_HINT_RE = re.compile(r"(제출\s*서류|구비\s*서류|필수\s*서류|첨부\s*서류)")
_ELIG_RE = re.compile(r"(지원\s*대상|지원\s*자격|신청\s*자격|지원자격|모집\s*대상)")


@dataclass
class AnnouncementReport:
    source: str = ""
    ai_used: bool = False
    text_chars: int = 0
    criteria: list[dict[str, Any]] = field(default_factory=list)
    total_max_score: int = 0
    key_info: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "ai_used": self.ai_used,
            "text_chars": self.text_chars,
            "criteria": self.criteria,
            "total_max_score": self.total_max_score,
            "key_info": self.key_info,
            "notes": self.notes,
        }


_AI_SYSTEM = (
    "당신은 한국 정부지원사업 공고문을 분석하는 전문가입니다. 아래 공고 텍스트에서 "
    "다음 항목을 JSON object 로 추출하세요. **공고에 실제로 적힌 내용만** 쓰고, 없으면 "
    "빈 문자열/빈 배열로 두세요(추측 금지).\n\n"
    "{\n"
    '  "evaluation_criteria": [{"name": "평가항목명", "max_score": 30}],\n'
    '  "support_target": "지원대상(요약)",\n'
    '  "eligibility": "지원자격/신청요건(요약)",\n'
    '  "funding_amount": "지원금액·규모(예: 최대 1억원)",\n'
    '  "deadline": "신청 마감/접수 기간",\n'
    '  "required_documents": ["제출서류1", "제출서류2"],\n'
    '  "support_content": "지원내용(요약)",\n'
    '  "bonus_points": "가점/우대사항",\n'
    '  "notes": "유의사항(요약)"\n'
    "}\n\n"
    "evaluation_criteria 는 배점이 명시된 평가항목만 넣고, 배점이 없으면 빈 배열로 두세요."
)


def _ai_key_info(openai_service: Any, text: str) -> dict[str, Any]:
    result = openai_service.complete_json(_AI_SYSTEM, f"공고 텍스트:\n{text[:8000]}", max_tokens=1500)
    return result if isinstance(result, dict) else {}


def _collect_lines(text: str, pattern: re.Pattern, *, limit: int = 5) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s and pattern.search(s):
            out.append(s[:120])
            if len(out) >= limit:
                break
    return out


def _heuristic_key_info(text: str) -> dict[str, Any]:
    amounts = _AMOUNT_RE.findall(text)
    return {
        "support_target": " / ".join(_collect_lines(text, _ELIG_RE, limit=3)),
        "eligibility": " / ".join(_collect_lines(text, _ELIG_RE, limit=3)),
        "funding_amount": ", ".join(sorted({m if isinstance(m, str) else "".join(m) for m in
                                            _AMOUNT_RE.findall(text)})[:5]) if amounts else "",
        "deadline": " / ".join(_collect_lines(text, _DEADLINE_RE, limit=3)),
        "required_documents": _collect_lines(text, _DOC_HINT_RE, limit=5),
        "support_content": "",
        "bonus_points": "",
        "notes": "(AI 미연결 — 휴리스틱 추출. 정확한 분석은 API 키 설정 후 재실행 권장)",
    }


def _make_openai() -> Optional[Any]:
    try:
        from .openai_client import OpenAIService
        from ..config import get_settings

        return OpenAIService(get_settings())
    except Exception:
        return None


def analyze_announcement(
    source: str | Path,
    *,
    is_text: bool = False,
    openai_service: Optional[Any] = None,
) -> AnnouncementReport:
    """공고문(파일 경로 또는 텍스트)을 종합 분석한다.

    Args:
        source: 공고 파일 경로(DOCX/PDF/HWP/TXT) 또는 공고 텍스트(``is_text=True``).
        is_text: True 면 source 를 텍스트로 직접 사용.
        openai_service: OpenAIService. None 이면 내부 생성(키 없으면 휴리스틱).

    Returns:
        AnnouncementReport.
    """
    report = AnnouncementReport()
    if is_text:
        text = str(source)
        report.source = "(직접 입력 텍스트)"
    else:
        text, notes = extract_text(source)
        report.source = str(source)
        report.notes.extend(notes)
    report.text_chars = len(text)
    if not text.strip():
        report.notes.append("공고 텍스트가 비어 있습니다 — 형식을 확인하세요.")
        return report

    if openai_service is None:
        openai_service = _make_openai()
    available = bool(openai_service is not None and getattr(openai_service, "available", False))
    report.ai_used = available

    # 평가기준·배점 (EvaluationService 재사용)
    try:
        from .evaluation_service import EvaluationService

        eval_svc = EvaluationService(openai_service) if openai_service is not None else None
        if eval_svc is not None:
            criteria = eval_svc.parse_announcement(text)
        else:
            criteria = []
    except Exception as exc:
        criteria = []
        report.notes.append(f"평가기준 파싱 실패: {exc}")
    report.criteria = [
        {"name": c.name, "max_score": c.max_score, "description": getattr(c, "description", "")}
        for c in criteria
    ]
    report.total_max_score = sum(c.max_score for c in criteria)

    # 핵심 정보(종합)
    if available:
        try:
            report.key_info = _ai_key_info(openai_service, text)
        except Exception as exc:
            report.notes.append(f"AI 핵심정보 추출 실패 → 휴리스틱 사용: {exc}")
            report.key_info = _heuristic_key_info(text)
    else:
        report.key_info = _heuristic_key_info(text)

    # 평가기준이 비었고 AI 가 evaluation_criteria 를 줬으면 그것으로 채운다(중복 방지로 key_info 에서 제거).
    ec = report.key_info.pop("evaluation_criteria", None) if isinstance(report.key_info, dict) else None
    if not report.criteria and isinstance(ec, list):
        parsed = [
            {"name": str(x.get("name", "")).strip(),
             "max_score": int(x.get("max_score", 0) or 0),
             "description": ""}
            for x in ec
            if isinstance(x, dict) and str(x.get("name", "")).strip()
        ]
        report.criteria = parsed
        report.total_max_score = sum(c["max_score"] for c in parsed)

    return report
