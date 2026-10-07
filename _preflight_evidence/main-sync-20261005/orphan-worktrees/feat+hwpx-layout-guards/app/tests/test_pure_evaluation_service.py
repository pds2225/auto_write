"""test_pure_evaluation_service.py — 평가 루프 순수 집계/직렬화 함수 안전망.

EvaluationService 의 AI 무관 결정론 메서드를 직접 검증한다:
_parse_announcement_rule_based / build_eval_result / _match_sections_by_keywords /
build_refinement_context / to_report_dict.

이 메서드들은 self.openai_service 를 사용하지 않으므로 __new__ 로 인스턴스를 만들어
외부 의존을 피한다. log_line 은 print 뿐이라 부작용이 없다.
야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

import json

from auto_write.services.evaluation_service import (
    CriterionScore,
    EvalLoopReport,
    EvalResult,
    EvaluationService,
)


def _svc() -> EvaluationService:
    return EvaluationService.__new__(EvaluationService)


def _score(
    name, max_score, score, ratio, *,
    strengths="", weaknesses="", suggestion="", related_sections=None,
) -> CriterionScore:
    return CriterionScore(
        name=name, max_score=max_score, score=score, ratio=ratio,
        strengths=strengths, weaknesses=weaknesses, suggestion=suggestion,
        related_sections=list(related_sections or []),
    )


class TestParseAnnouncementRuleBased:
    def test_extracts_scored_item(self):
        out = _svc()._parse_announcement_rule_based("기술개발 역량 (30)")
        assert len(out) == 1
        assert out[0].max_score == 30
        assert "역량" in out[0].name

    def test_low_score_excluded(self):
        # 배점 < 5 → 제외 (name 은 3자 이상이므로 점수 필터만 검증)
        assert _svc()._parse_announcement_rule_based("성장성 (4)") == []

    def test_high_score_excluded(self):
        # 배점 > 100 → 제외
        assert _svc()._parse_announcement_rule_based("종합평가 (120)") == []

    def test_no_match_returns_empty(self):
        assert _svc()._parse_announcement_rule_based("배점 없는 순수 문장입니다") == []


class TestBuildEvalResult:
    def test_aggregates_totals_and_weak(self):
        scores = [
            _score("A", 20, 18, 0.9),
            _score("B", 20, 4, 0.2, related_sections=["sec_b"]),
        ]
        res = _svc().build_eval_result(1, scores, [])
        assert res.iteration == 1
        assert res.total_score == 22
        assert res.max_total == 40
        assert abs(res.pass_ratio - 0.55) < 1e-9
        assert res.weak_sections == ["sec_b"]
        assert "총점: 22/40" in res.summary

    def test_keyword_fallback_when_related_empty(self):
        scores = [_score("차별성", 20, 4, 0.2, related_sections=[])]
        pq = [{"question_id": "q1", "label": "차별성 및 경쟁력",
               "target": {"kind": "section"}}]
        res = _svc().build_eval_result(2, scores, pq)
        assert res.weak_sections == ["q1"]

    def test_no_weak_when_all_pass(self):
        scores = [_score("A", 20, 20, 1.0), _score("B", 10, 9, 0.9)]
        res = _svc().build_eval_result(1, scores, [])
        assert res.weak_sections == []

    def test_dedup_weak_sections_preserving_order(self):
        scores = [
            _score("A", 20, 4, 0.2, related_sections=["s1", "s1", "s2"]),
            _score("B", 20, 4, 0.2, related_sections=["s2"]),
        ]
        res = _svc().build_eval_result(1, scores, [])
        assert res.weak_sections == ["s1", "s2"]


class TestMatchSectionsByKeywords:
    def test_matches_by_name_word(self):
        score = _score("시장 규모", 20, 5, 0.25)
        pq = [
            {"question_id": "q1", "label": "목표 시장 분석", "target": {"kind": "section"}},
            {"question_id": "q2", "label": "규모 산정", "target": {"kind": "section"}},
            {"question_id": "q3", "label": "기타", "target": {"kind": "field"}},
        ]
        assert _svc()._match_sections_by_keywords(score, pq) == ["q1", "q2"]

    def test_skips_non_section_and_empty_qid(self):
        score = _score("시장", 20, 5, 0.25)
        pq = [
            {"question_id": "", "label": "시장 규모", "target": {"kind": "section"}},
            {"question_id": "q2", "label": "시장 분석", "target": {"kind": "field"}},
        ]
        assert _svc()._match_sections_by_keywords(score, pq) == []

    def test_limit_three(self):
        score = _score("시장", 20, 5, 0.25)
        pq = [{"question_id": f"q{i}", "label": "시장", "target": {"kind": "section"}}
              for i in range(5)]
        assert _svc()._match_sections_by_keywords(score, pq) == ["q0", "q1", "q2"]


class TestBuildRefinementContext:
    def test_includes_context_and_weak_items(self):
        scores = [_score("A", 20, 5, 0.25, weaknesses="근거 부족",
                         suggestion="원문 수치 재배치", related_sections=["sec1"])]
        pq = [{"question_id": "sec1", "label": "문제인식"}]
        out = _svc().build_refinement_context(["sec1"], scores, pq, "  원본초안  ")
        assert "원본초안" in out
        assert "=== 평가 결과 기반 보완 지시 ===" in out
        assert "[보완필요] 항목: 문제인식" in out
        assert "5/20" in out
        assert "근거 부족" in out
        assert "원문 수치 재배치" in out
        assert "수치·고유명사 변형 금지" in out

    def test_unknown_section_falls_back_to_id(self):
        out = _svc().build_refinement_context(["missing"], [], [], "ctx")
        assert "[보완필요] 항목: missing" in out


class TestToReportDict:
    def test_serializes_with_rounding(self):
        scores = [_score("A", 20, 15, 0.75, strengths="s", weaknesses="w",
                         suggestion="g", related_sections=["sec1"])]
        it = EvalResult(iteration=1, total_score=15, max_total=20,
                        pass_ratio=0.759999, criteria_scores=scores,
                        weak_sections=["sec1"], summary="요약")
        report = EvalLoopReport(
            project_id="p1", iterations=[it], final_score=15, final_max=20,
            final_pass_ratio=0.87654321, converged=True,
            announcement_criteria=[{"name": "A", "max_score": 20}],
            needs_input=["항목 확인"],
        )
        d = _svc().to_report_dict(report)
        assert d["project_id"] == "p1"
        assert d["final_score"] == 15
        assert d["final_pass_ratio"] == 0.8765     # round(0.87654321, 4)
        assert d["converged"] is True
        assert d["needs_input"] == ["항목 확인"]
        assert d["announcement_criteria"] == [{"name": "A", "max_score": 20}]
        it0 = d["iterations"][0]
        assert it0["iteration"] == 1
        assert it0["pass_ratio"] == 0.76            # round(0.759999, 4)
        assert it0["weak_sections"] == ["sec1"]
        cs0 = it0["criteria_scores"][0]
        assert cs0["name"] == "A"
        assert cs0["ratio"] == 0.75
        assert cs0["score"] == 15

    def test_json_serializable_with_empty_iterations(self):
        report = EvalLoopReport(
            project_id="p", iterations=[], final_score=0, final_max=0,
            final_pass_ratio=0.0, converged=False, announcement_criteria=[],
        )
        d = _svc().to_report_dict(report)
        json.dumps(d, ensure_ascii=False)  # 예외 없이 직렬화 = 순수 dict
        assert d["iterations"] == []
        assert d["needs_input"] == []
