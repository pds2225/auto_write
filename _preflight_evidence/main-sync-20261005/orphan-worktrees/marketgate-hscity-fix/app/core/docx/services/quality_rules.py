"""사업계획서 작성 규칙(①~⑧) 프리셋 설정 — 범용 엔진 제어 레이어.

auto_write 품질 하네스에 '사업계획서 작성 규칙'을 옵트인으로 켜고 끄기 위한
설정 모듈이다. 규칙의 '수정 로직'은 기존 doc_quality_ops / submittable_filler /
doc_quality_score 등에 있고, 이 모듈은 '어떤 규칙을 켤지'만 묶는다.

설계 원칙(계획 v4):
- 하위호환 옵트인: 아무 것도 켜지 않은 상태(=ruleset None 또는 "off" 프리셋)는
  현행 동작과 논리 동등해야 한다(서식 count·점수 불변).
- ⑤ 채점 연동(score_empty_required)은 '재사용'이 아니라 '동작 변경'이라 별도
  플래그로 게이팅한다. 보수적으로 어떤 프리셋도 기본 on 하지 않는다(추후 옵트인).
- ⑧ 역할경계는 코드 구조로 강제하므로 런타임 플래그가 아니다.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["BizplanRulesConfig", "PRESETS", "resolve_ruleset"]


@dataclass(frozen=True)
class BizplanRulesConfig:
    """사업계획서 작성 규칙 on/off 묶음 (frozen — 프리셋은 불변)."""

    preserve_original_format: bool = True   # ① 원본 서식 보존(항상 권장 True)
    color_to_black: bool = True             # ② 파란/유색 글씨 → 검정
    body_font_pt: float | None = 10.0       # ③ 본문 통일 pt. None 이면 target_pt 모드 끔
    suggest_notebooklm: bool = True         # ④ NotebookLM 그림 프롬프트 제안
    enforce_confirm_marker: bool = False    # ⑤ 빈 필수칸에 [확인필요] 주입(옵트인, 기본 off)
    score_empty_required: bool = False      # ⑤ 채점 연동(가중치 0→비0). 동작 변경 — 기본 off
    blank_undecided: bool = True            # ⑥ 미확정 항목 공란 처리
    flag_unverified_claims: bool = False    # ⑦ 근거 없는 협업·실적 단정 경고(warn, 기본 off)
    # ⑧ 에이전트 역할경계는 코드 구조로 강제 — 런타임 플래그 없음


# 프리셋: 문서 유형/용도별 기본 규칙 묶음.
#   "off" 는 모든 규칙을 끈 상태로, ruleset=None(레거시)과 논리 동등하다.
PRESETS: dict[str, BizplanRulesConfig] = {
    # 사업계획서 풀세트: ③ 본문 10pt. ⑤ 채점 연동은 보수적으로 off(사용자 결정 2026-06-22)
    # — 어떤 프리셋도 score_empty_required 를 기본 on 하지 않는다(추후 옵트인).
    "bizplan": BizplanRulesConfig(),
    # 일반 보고서: 색검정·공란·프롬프트는 유지, 본문 pt 고정·채점연동은 off.
    "report": BizplanRulesConfig(
        body_font_pt=None,
        enforce_confirm_marker=False,
        score_empty_required=False,
    ),
    # 최소 개입: 색검정·pt고정·공란처리·채점연동 모두 off(서식 절대보존형 양식용).
    "minimal": BizplanRulesConfig(
        color_to_black=False,
        body_font_pt=None,
        enforce_confirm_marker=False,
        blank_undecided=False,
        score_empty_required=False,
    ),
    # 전부 off — 현행 동작 보존(ruleset=None 과 논리 동등, 점수 불변).
    "off": BizplanRulesConfig(
        preserve_original_format=False,
        color_to_black=False,
        body_font_pt=None,
        suggest_notebooklm=False,
        enforce_confirm_marker=False,
        score_empty_required=False,
        blank_undecided=False,
        flag_unverified_claims=False,
    ),
}

# 문서 유형(document_type_classifier.type_code) → 프리셋 이름 매핑.
_DOC_TYPE_PRESET = {
    "business_plan": "bizplan",
    "pitch_deck": "bizplan",
}


def resolve_ruleset(
    doc_type: str | None = None,
    override: str | None = None,
) -> BizplanRulesConfig:
    """문서 유형/사용자 지정으로 적용할 규칙 프리셋을 고른다.

    - override(예: CLI --ruleset)가 주어지면 그 프리셋을 강제한다.
      알 수 없는 이름이면 ValueError(잘못된 입력 즉시 실패).
    - override 가 없으면 doc_type(type_code)으로 매핑한다. 사업계획서/발표자료는
      "bizplan", 그 외/미상은 "report" 로 보수적으로 매핑한다.

    항상 BizplanRulesConfig 를 반환한다. 레거시(규칙 미적용)는 "off" 프리셋
    (ruleset=None 과 논리 동등)으로 표현한다.
    """
    if override is not None:
        if override not in PRESETS:
            raise ValueError(
                f"알 수 없는 ruleset: {override!r} (사용 가능: {sorted(PRESETS)})"
            )
        return PRESETS[override]
    preset_name = _DOC_TYPE_PRESET.get(doc_type or "", "report")
    return PRESETS[preset_name]
