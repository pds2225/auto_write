import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.services.evaluation_service import CriterionScore, EvalCriterion, EvaluationService
from auto_write.services.eval_loop_runner import EvalLoopRunner


class _Q:
    def __init__(self, qid, label):
        self._d = {
            "question_id": qid,
            "label": label,
            "target": {"kind": "section", "field_id": qid},
            "required": True,
        }
        self.question_id = qid

    def model_dump(self):
        return dict(self._d)


class _Profile:
    def __init__(self):
        self.questions = [_Q("qa", "항목A"), _Q("qb", "항목B")]


class _FakeProjectService:
    def __init__(self, profile):
        self._profile = profile
        self.regenerate_calls = []

    def load_profile_for_project(self, pid):
        return self._profile

    def regenerate_sections(self, pid, qids, refinement_context=""):
        self.regenerate_calls.append(list(qids))
        return None


class _FakeStorage:
    def __init__(self, base):
        self._base = Path(base)

    def project_dir(self, pid):
        return self._base / pid


class _FakeOA:
    available = False


def _make_docx(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_paragraph("사업계획서 본문")
    doc.save(str(path))


def _cs(name, score, mx, qid):
    return CriterionScore(
        name=name, max_score=mx, score=score, ratio=score / mx,
        strengths="", weaknesses="", suggestion="", related_sections=[qid],
    )


class EvalLoopRunnerTest(unittest.TestCase):
    def _runner(self, score_rounds):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        _make_docx(base / "p1" / "output" / "output.docx")
        eval_service = EvaluationService(_FakeOA())
        rounds = [list(r) for r in score_rounds]

        def fake_score(doc_text, criteria, pq):
            return rounds.pop(0)

        eval_service.score_document = fake_score
        ps = _FakeProjectService(_Profile())
        storage = _FakeStorage(base)
        return EvalLoopRunner(eval_service, ps, storage), ps

    def test_reaches_target_after_regeneration(self):
        criteria = [EvalCriterion("항목A", 60, "", []), EvalCriterion("항목B", 40, "", [])]
        rounds = [
            [_cs("항목A", 20, 60, "qa"), _cs("항목B", 10, 40, "qb")],
            [_cs("항목A", 58, 60, "qa"), _cs("항목B", 38, 40, "qb")],
        ]
        runner, ps = self._runner(rounds)
        report = runner.run("p1", criteria=criteria, target_score=92, max_iterations=3, scoring_passes=1)
        self.assertEqual(len(ps.regenerate_calls), 1)
        self.assertEqual(ps.regenerate_calls[0], ["qa", "qb"])
        self.assertTrue(report.converged)
        self.assertGreaterEqual(report.final_pass_ratio, 0.92)
        self.assertEqual(report.needs_input, [])

    def test_plateau_reports_needs_input(self):
        criteria = [EvalCriterion("항목A", 60, "", []), EvalCriterion("항목B", 40, "", [])]
        low = [_cs("항목A", 20, 60, "qa"), _cs("항목B", 10, 40, "qb")]
        rounds = [list(low), list(low), list(low)]
        runner, ps = self._runner(rounds)
        report = runner.run("p1", criteria=criteria, target_score=92, max_iterations=3, scoring_passes=1)
        self.assertLess(report.final_pass_ratio, 0.92)
        self.assertIn("항목A", report.needs_input)
        self.assertIn("항목B", report.needs_input)

    def test_unmappable_weak_breaks_without_regeneration(self):
        criteria = [EvalCriterion("항목A", 60, "", [])]
        bad = [CriterionScore(
            name="항목A", max_score=60, score=10, ratio=10 / 60,
            strengths="", weaknesses="", suggestion="", related_sections=["zzz"],
        )]
        runner, ps = self._runner([list(bad), list(bad)])
        report = runner.run("p1", criteria=criteria, target_score=92, max_iterations=3, scoring_passes=1)
        self.assertEqual(ps.regenerate_calls, [])
        self.assertIn("항목A", report.needs_input)

    def tearDown(self):
        if hasattr(self, "tmp"):
            self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
