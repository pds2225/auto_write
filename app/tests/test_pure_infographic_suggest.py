"""test_pure_infographic_suggest.py — 인포그래픽 슬라이드 프롬프트 순수 헬퍼 안전망.

_append_design_guide / _keyword_slide_prompt / _match_anchor 를 외부 의존
(python-docx·AI) 없이 직접 검증한다. 디자인 규칙 중복 방지·날조 금지 문구·앵커 보정
동작을 고정한다. 야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

from auto_write.services.infographic_suggest import (
    _SLIDE_DESIGN_GUIDE,
    _append_design_guide,
    _keyword_slide_prompt,
    _match_anchor,
)


class TestAppendDesignGuide:
    def test_empty_returns_guide(self):
        assert _append_design_guide("") == _SLIDE_DESIGN_GUIDE

    def test_already_has_guide_unchanged(self):
        txt = "내용 [디자인] 이미 있음"
        assert _append_design_guide(txt) == txt

    def test_appends_with_space_when_no_terminal_punct(self):
        assert _append_design_guide("내용") == "내용 " + _SLIDE_DESIGN_GUIDE

    def test_no_extra_space_after_period(self):
        assert _append_design_guide("내용.") == "내용." + _SLIDE_DESIGN_GUIDE

    def test_no_extra_space_after_trailing_space(self):
        assert _append_design_guide("내용 ") == "내용 " + _SLIDE_DESIGN_GUIDE

    def test_idempotent(self):
        # 한 번 붙이면 [디자인] 이 포함되므로 두 번째 호출은 그대로 반환.
        once = _append_design_guide("내용")
        assert _append_design_guide(once) == once


class TestKeywordSlidePrompt:
    def test_strips_figure_prefix_for_topic(self):
        out = _keyword_slide_prompt("막대 차트", "[그림] 시장규모")
        assert "'시장규모'" in out
        assert "'막대 차트'" in out

    def test_falls_back_to_visual_type_when_caption_empty(self):
        out = _keyword_slide_prompt("도넛 차트", "")
        assert "'도넛 차트'" in out

    def test_contains_no_fabrication_rule(self):
        # 문서에 없는 데이터는 만들지 말라는 날조 금지 지침이 반드시 포함.
        out = _keyword_slide_prompt("타임라인", "[그림] 추진 일정")
        assert "만들어 넣지 마" in out

    def test_ends_with_design_guide(self):
        out = _keyword_slide_prompt("조직도", "[그림] 팀 구성")
        assert "[디자인]" in out
        assert out.endswith(_SLIDE_DESIGN_GUIDE)


class TestMatchAnchor:
    def test_empty_anchor_returns_empty(self):
        assert _match_anchor("", ["가", "나"]) == ""

    def test_anchor_is_substring_of_paragraph(self):
        paras = ["목표 시장규모 분석", "팀 구성"]
        assert _match_anchor("시장규모", paras) == "목표 시장규모 분석"

    def test_paragraph_is_substring_of_anchor(self):
        paras = ["긴 앵커"]
        assert _match_anchor("아주 긴 앵커 텍스트입니다", paras) == "긴 앵커"

    def test_no_match_returns_empty(self):
        assert _match_anchor("전혀없는내용ABC", ["다른것", "또다른것"]) == ""

    def test_prefix_key_fallback(self):
        # 전체 문자열은 어느 단락의 부분문자열도 아니지만, 앞 12자가 포함되면 보정.
        anchor = "성장전략 요약 그리고 딴판인결말"
        paras = ["앞부분 성장전략 요약 그리고 딴판아닌결말"]
        assert _match_anchor(anchor, paras) == paras[0]

    def test_first_match_wins(self):
        paras = ["시장 이야기", "또 시장 이야기"]
        assert _match_anchor("시장", paras) == "시장 이야기"
