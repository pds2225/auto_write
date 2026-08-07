"""test_pure_qa_render_helpers.py — QAService·RenderService 순수 헬퍼 안전망.

두 서비스는 build_report / render E2E 로만 간접 검증돼 왔고, 그 안의
문자열·정규식 헬퍼(외부 의존 없음)는 직접 단위 테스트가 없었다.
이 파일은 python-docx Document 없이 문자열 입력만으로 검증한다(결정론).

특히 QAService._normalize_match_text 의 '두 번 반복된 텍스트 절반 축약'
(DOCX 병합에서 앵커 제목이 이어붙어 두 번 나타나는 경우의 방어 로직)은
미묘해서 회귀로 고정할 가치가 크다.
"""

from __future__ import annotations

from types import SimpleNamespace

from auto_write.services.qa_service import QAService
from auto_write.services.render_service import RenderService


QA = QAService()


# ------------------------------------------------------------------ QAService
class TestMsg:
    def test_format(self):
        assert QAService._msg("품질", "안내문구 잔존") == "[품질] 안내문구 잔존"


class TestIsNonBusinessLabel:
    def test_admin_labels_are_non_business(self):
        assert QAService._is_non_business_label("담당자") is True
        assert QAService._is_non_business_label("담 당 자")  # 공백 끼어도 매칭
        assert QAService._is_non_business_label("별첨 서류 목록")

    def test_bullet_only_line_is_non_business(self):
        assert QAService._is_non_business_label("◦") is True
        assert QAService._is_non_business_label("■□●") is True

    def test_business_text_and_none(self):
        assert QAService._is_non_business_label("사업 개요") is False
        assert QAService._is_non_business_label(None) is False
        assert QAService._is_non_business_label("") is False


class TestNormalizeMatchText:
    def test_collapses_whitespace_and_strips(self):
        assert QA._normalize_match_text("  a \n\t b  c ") == "a b c"

    def test_unifies_dash_variants(self):
        # en dash(–)·em dash(—)·non-breaking hyphen(‑) → ASCII '-'
        assert QA._normalize_match_text("2024–2025—2026‑말") == "2024-2025-2026-말"

    def test_doubled_text_reduced_to_half(self):
        s = "창업 아이템의 개발 계획"          # 13자 — 2배 시 26자(짝수·16 이상)
        assert QA._normalize_match_text(s * 2) == s

    def test_quadrupled_text_reduced_twice(self):
        # 축약 루프는 최대 2회 — 4배 반복도 원문까지 줄어든다.
        s = "창업 아이템의 개발 계획"
        assert QA._normalize_match_text(s * 4) == s

    def test_non_duplicated_long_text_unchanged(self):
        s = "가나다라마바사아자차카타파하AB"    # 16자(짝수)지만 반반이 다름
        assert QA._normalize_match_text(s) == s

    def test_empty_and_none(self):
        assert QA._normalize_match_text("") == ""
        assert QA._normalize_match_text(None) == ""


class TestMatchAnchor:
    def test_substring_match(self):
        assert QA._match_anchor("1. 창업 아이템 개요", "창업 아이템") is True

    def test_space_insensitive_compact_match(self):
        # 앵커에 공백이 없고 본문에 공백이 있어도(또는 그 반대) 매칭돼야 한다.
        assert QA._match_anchor("창업 아이템 소개", "창업아이템") is True

    def test_doubled_candidate_still_matches(self):
        anchor = "창업 아이템의 개발 계획"
        assert QA._match_anchor(anchor * 2, anchor) is True

    def test_empty_inputs_do_not_match(self):
        assert QA._match_anchor("", "앵커") is False
        assert QA._match_anchor("본문", "") is False

    def test_unrelated_text_does_not_match(self):
        assert QA._match_anchor("전혀 다른 문장", "창업 아이템") is False


class TestIsMeaningfulText:
    def test_empty_or_blank_is_not_meaningful(self):
        assert QA._is_meaningful_text("") is False
        assert QA._is_meaningful_text("   ") is False

    def test_non_business_label_is_not_meaningful(self):
        assert QA._is_meaningful_text("담당자") is False

    def test_guide_markers_are_not_meaningful(self):
        assert QA._is_meaningful_text("※ 작성요령을 참고하세요") is False
        assert QA._is_meaningful_text("<제목 기재>") is False
        assert QA._is_meaningful_text("성명 ○○○") is False

    def test_anchor_echo_is_not_meaningful(self):
        # 앵커 제목이 그대로 반복된 줄은 '본문 내용'으로 치지 않는다.
        assert QA._is_meaningful_text("1. 사업 개요", anchor_text="사업 개요") is False

    def test_real_content_is_meaningful(self):
        assert QA._is_meaningful_text("2026년 매출 10억원 달성") is True


class TestMissingFieldMessage:
    def test_project_meta_message(self):
        q = SimpleNamespace(label="사업명", question_id="q1", target={"key": "project_title"})
        assert QAService._missing_field_message(q, "project_meta") == (
            "❌ '사업명' 항목이 비어있습니다. project_input.json의 meta.project_title를 채워주세요."
        )

    def test_organization_profile_defaults_key_to_name(self):
        q = SimpleNamespace(label="기업명", question_id="", target={})
        msg = QAService._missing_field_message(q, "organization_profile")
        assert "organization.name" in msg
        assert msg.startswith("❌ '기업명'")

    def test_section_points_to_answers_question_id(self):
        q = SimpleNamespace(label="개발 계획", question_id="q7", target={})
        msg = QAService._missing_field_message(q, "section")
        assert "answers.q7" in msg

    def test_unknown_kind_without_id_falls_back(self):
        q = SimpleNamespace(label="", question_id="", target={})
        msg = QAService._missing_field_message(q, "unknown")
        assert msg == "❌ '필수 입력' 항목이 비어있습니다. 입력값을 확인해주세요."


# --------------------------------------------------------------- RenderService
class TestParseAnchorIndex:
    def test_numeric_string_with_spaces(self):
        assert RenderService._parse_anchor_index(" 3 ") == 3

    def test_int_and_negative(self):
        assert RenderService._parse_anchor_index(7) == 7
        assert RenderService._parse_anchor_index("-2") == -2

    def test_invalid_returns_default(self):
        assert RenderService._parse_anchor_index("abc") == -1
        assert RenderService._parse_anchor_index(None) == -1
        assert RenderService._parse_anchor_index("3.5") == -1   # float 문자열도 불허

    def test_empty_returns_custom_default(self):
        assert RenderService._parse_anchor_index("", 5) == 5


class TestShouldSkip:
    def test_skip_admin_sections(self):
        assert RenderService._should_skip_section("담당자") is True
        assert RenderService._should_skip_section("붙임: 증빙서류") is True

    def test_keep_business_sections(self):
        assert RenderService._should_skip_section("사업 개요") is False
        assert RenderService._should_skip_section("") is False
        assert RenderService._should_skip_section(None) is False

    def test_skip_evidence_image_slots(self):
        assert RenderService._should_skip_image_slot("증빙서류 첨부") is True
        assert RenderService._should_skip_image_slot("개인정보 동의서") is True

    def test_keep_content_image_slots(self):
        assert RenderService._should_skip_image_slot("시장규모 도표") is False
