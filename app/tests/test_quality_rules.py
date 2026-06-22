"""사업계획서 작성 규칙 1단계(저위험) 테스트.

Phase 1: 신규 규칙은 모두 옵트인이며, 켜지 않으면 현행 동작과 동등하다.
- quality_rules 프리셋 플래그 / resolve_ruleset 매핑·override·검증
- run_all(rules=None) 및 run_all(rules=프리셋) == 레거시(서식 count 동일, Phase 1 no-op)
- ⑦ check_unverified_claims: 기본 off, 활성 시 '확정 단정'만 warn, 게이트(submittable) 불변

Phase 2(②③⑤ 배선)에서 run_all 의 rules 동등성 단언은 의도적으로 갱신될 예정이다.
"""

from __future__ import annotations

import pytest
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from auto_write.services.quality_rules import (
    BizplanRulesConfig, PRESETS, resolve_ruleset,
)
from auto_write.services.doc_quality_ops import run_all, normalize_colored_text_to_black
from auto_write.services.usage_acceptance import (
    AcceptanceConfig, SEV_WARN, run_acceptance, check_unverified_claims,
)


# --- 프리셋 / resolve_ruleset ----------------------------------------------

def test_presets_score_empty_required_only_bizplan():
    # ⑤ 채점 연동(가중치 0→비0, '동작 변경')은 bizplan 프리셋만 켠다.
    enabled = [n for n in PRESETS if PRESETS[n].score_empty_required]
    assert enabled == ["bizplan"]


def test_presets_flag_values():
    biz = PRESETS["bizplan"]
    assert biz.color_to_black is True
    assert biz.body_font_pt == 10.0            # ③ 본문 10pt
    assert biz.score_empty_required is True

    rep = PRESETS["report"]
    assert rep.body_font_pt is None
    assert rep.score_empty_required is False

    mini = PRESETS["minimal"]
    assert mini.color_to_black is False
    assert mini.blank_undecided is False

    off = PRESETS["off"]                        # 전부 off — 레거시와 논리 동등
    assert off.color_to_black is False
    assert off.body_font_pt is None
    assert off.suggest_notebooklm is False
    assert off.blank_undecided is False
    assert off.flag_unverified_claims is False
    assert off.score_empty_required is False


def test_default_config_is_conservative():
    # 명시 지정 없이 만든 기본 설정은 보수적(고위험·동작변경 규칙 off).
    d = BizplanRulesConfig()
    assert d.score_empty_required is False
    assert d.enforce_confirm_marker is False
    assert d.flag_unverified_claims is False
    assert d.body_font_pt == 10.0


def test_resolve_ruleset_mapping_and_override():
    assert resolve_ruleset("business_plan") is PRESETS["bizplan"]
    assert resolve_ruleset("pitch_deck") is PRESETS["bizplan"]
    assert resolve_ruleset("rnd_plan") is PRESETS["report"]    # 기타/미상 → report
    assert resolve_ruleset(None) is PRESETS["report"]
    # override(CLI --ruleset)가 doc_type 보다 우선
    assert resolve_ruleset("business_plan", override="minimal") is PRESETS["minimal"]
    assert resolve_ruleset(override="off") is PRESETS["off"]


def test_resolve_ruleset_unknown_override_raises():
    with pytest.raises(ValueError):
        resolve_ruleset(override="does-not-exist")


# --- 하위호환: run_all(rules=...) == 레거시 (Phase 1 no-op) -----------------

def _build_doc() -> Document:
    """후처리가 실제로 일을 하도록 빈 단락 + 파란 런을 포함한 문서."""
    doc = Document()
    doc.add_paragraph("정상 본문 문장입니다.")
    doc.add_paragraph("")  # 빈 단락 → empty_paragraphs_removed 유발
    p = doc.add_paragraph("실적 ")
    run = p.add_run("핵심 성과 수치")  # 안내문구 패턴 비매칭(삭제 안 됨)
    run.font.color.rgb = RGBColor(0x00, 0x00, 0xFF)  # 유색 → colored_runs_normalized
    return doc


def test_run_all_rules_none_equals_legacy():
    legacy = run_all(_build_doc())
    rules_none = run_all(_build_doc(), rules=None)
    assert legacy.as_dict() == rules_none.as_dict()


def test_run_all_rules_preset_is_phase1_noop():
    """Phase 1 에서 rules 는 받기만 하고 동작을 바꾸지 않는다(레거시 동등).

    Phase 2 에서 ②③⑤ 가 배선되면 이 단언은 의도적으로 갱신될 예정이다.
    """
    legacy = run_all(_build_doc())
    with_biz = run_all(_build_doc(), rules=PRESETS["bizplan"])
    with_off = run_all(_build_doc(), rules=PRESETS["off"])
    assert legacy.as_dict() == with_biz.as_dict() == with_off.as_dict()


def test_run_all_actually_does_work():
    """위 동등성이 '0==0' 공허가 아님을 보증 — 파란 런이 실제로 검정화된다."""
    rep = run_all(_build_doc())
    assert rep.colored_runs_normalized >= 1


def test_run_all_legacy_args_unaffected_by_rules_none():
    """오케스트레이터가 쓰는 인자 조합에서도 rules=None 이 결과를 바꾸지 않음."""
    kw = dict(remove_guides=True, emphasize=True, underline=False, normalize_fonts=False)
    legacy = run_all(_build_doc(), **kw)
    rules_none = run_all(_build_doc(), rules=None, **kw)
    assert legacy.as_dict() == rules_none.as_dict()


# --- ⑦ check_unverified_claims: warn·기본 off·게이트 불변 -------------------

def _doc_with(*texts: str) -> Document:
    doc = Document()
    for t in texts:
        doc.add_paragraph(t)
    return doc


def test_unverified_claims_off_by_default():
    doc = _doc_with("삼성전자와 협업(확정)")
    r_none = check_unverified_claims(doc, None)              # config 미지정 → 비활성
    assert r_none.severity == SEV_WARN and r_none.defects == 0
    r_default = check_unverified_claims(doc, AcceptanceConfig())  # 기본 flag off → 비활성
    assert r_default.defects == 0


def test_unverified_claims_active_flags_confirmed_only():
    cfg = AcceptanceConfig(flag_unverified_claims=True)
    doc = _doc_with("삼성전자와 협업(확정)", "B사와 협력 검토 중")
    r = check_unverified_claims(doc, cfg)
    assert r.severity == SEV_WARN
    assert r.defects == 1   # '협업(확정)'만 — '검토 중'은 헷지 표현으로 제외


def test_unverified_claims_excludes_evidence_marked():
    cfg = AcceptanceConfig(flag_unverified_claims=True)
    doc = _doc_with("삼성전자와 협업(확정) [산출근거: 계약서 2026.01]")
    assert check_unverified_claims(doc, cfg).defects == 0   # 근거 표기 → 제외


def test_unverified_claims_warn_does_not_change_gate(tmp_path):
    """warn 추가는 AcceptanceReport.submittable 에 영향 없음(SEV_FAIL 만 평가)."""
    doc = _doc_with("삼성전자와 협업(확정)")
    p = tmp_path / "claim.docx"
    doc.save(str(p))
    rep_off = run_acceptance(p, AcceptanceConfig(flag_unverified_claims=False))
    rep_on = run_acceptance(p, AcceptanceConfig(flag_unverified_claims=True))
    assert rep_off.submittable == rep_on.submittable   # 게이트(submittable) 불변
    assert rep_on.warn_defects >= 1                     # 경고는 잡힌다
    assert "unverified_claims" in {r.check_id for r in rep_on.results}  # 검사 등록 확인


# --- ② 색→검정 정규화는 형광펜·음영(highlight/shd)을 보존해야 함 (강조 증발 방지) ----

def _doc_with_colored_highlighted_run():
    doc = Document()
    p = doc.add_paragraph("핵심 ")
    run = p.add_run("성과 강조 문장")
    run.font.color.rgb = RGBColor(0x00, 0x00, 0xFF)     # 파란 글자색
    run.font.highlight_color = WD_COLOR_INDEX.YELLOW    # 노란 형광펜(w:highlight)
    rpr = run._element.get_or_add_rPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "FFFF00")
    rpr.append(shd)                                     # 음영(w:shd)
    return doc, run


def test_color_normalize_preserves_highlight_and_shd():
    """색 정규화는 글자색만 검정화하고 형광펜·음영은 보존해야 한다.

    검출기 check_residual_colored_runs 는 색만 보고 highlight 는 안 보므로, 색변환이
    highlight/shd 까지 지우면 게이트가 못 잡는 '강조 증발' 회귀가 된다(계획 §2-D-②).
    """
    doc, run = _doc_with_colored_highlighted_run()
    n = normalize_colored_text_to_black(doc)
    assert n >= 1                                       # 파란 글자색 → 검정
    rpr = run._element.find(qn("w:rPr"))
    color = rpr.find(qn("w:color"))
    assert color is not None and color.get(qn("w:val")) == "000000"
    assert rpr.find(qn("w:highlight")) is not None, "형광펜(highlight)이 보존돼야 함"
    assert rpr.find(qn("w:shd")) is not None, "음영(shd)이 보존돼야 함"
    assert normalize_colored_text_to_black(doc) == 0    # 멱등 — 2회차 0건
