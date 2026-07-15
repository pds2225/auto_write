"""SFT 데이터 레이어 P2 테스트 — 변환기 + 생성 소비자.

- build_examples: 사람 승인본 우선, draft_rejected 제외, dedup, 마스킹.
- build_learned_snippets: section 한정·항상 마스킹.
- export_all counts.
- _suggest_learned_snippets(소비자): 파일 읽기·라벨 정확일치·section 한정·마스킹 예시 주입.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from auto_write.config import Settings, ensure_directories
from auto_write.services import generation_store, learning_store, sft_export
from auto_write.services.evidence_service import EvidenceService
from auto_write.services.image_service import ImageService
from auto_write.services.openai_client import OpenAIService
from auto_write.services.project_service import ProjectService
from auto_write.services.qa_service import QAService
from auto_write.services.render_service import RenderService
from auto_write.storage import Storage


def _seed_trace(root: Path, project_id: str, questions: list[dict], answers: dict) -> None:
    generation_store.record_ai_call(
        provider="anthropic", model="c",
        system_prompt="당신은 작성 전문가입니다.",
        user_prompt=json.dumps({"questions": questions, "context": "참고 컨텍스트 본문"}, ensure_ascii=False),
        raw_response=json.dumps(answers, ensure_ascii=False),
        purpose="draft_answers", project_id=project_id, attempt=1, root=root,
    )


# --- 변환기 ------------------------------------------------------------------

def test_build_examples_ai_pairs(tmp_path: Path) -> None:
    _seed_trace(
        tmp_path, "p1",
        [{"question_id": "q1", "label": "문제 인식", "target": {"kind": "section"}},
         {"question_id": "q2", "label": "기업명", "target": {"kind": "table_cell"}}],
        {"q1": "문제 서술입니다", "q2": "밸류업"},
    )
    ex = sft_export.build_examples(
        learning_store.load_generation_traces(root=tmp_path),
        learning_store.load_feedback(root=tmp_path), root=tmp_path,
    )
    by = {(e["project_id"], e["qid"]): e for e in ex}
    assert len(ex) == 2
    assert by[("p1", "q1")]["source"] == "ai"
    assert by[("p1", "q1")]["assistant"] == "문제 서술입니다"
    assert "문제 인식" in by[("p1", "q1")]["user"]


def test_human_approved_overrides_ai_and_rejected_excluded(tmp_path: Path) -> None:
    _seed_trace(
        tmp_path, "p1",
        [{"question_id": "q1", "label": "문제 인식", "target": {"kind": "section"}},
         {"question_id": "q2", "label": "해결 방안", "target": {"kind": "section"}}],
        {"q1": "AI 초안 q1", "q2": "AI 초안 q2"},
    )
    learning_store.append_feedback(
        {"project_id": "p1", "qid": "q1", "action_type": "edited",
         "feedback": {"before": "AI 초안 q1", "after": "사람이 승인한 문장"}}, root=tmp_path)
    learning_store.append_feedback(
        {"project_id": "p1", "qid": "q2", "action_type": "draft_rejected",
         "feedback": {"before": "AI 초안 q2", "after": ""}}, root=tmp_path)
    ex = sft_export.build_examples(
        learning_store.load_generation_traces(root=tmp_path),
        learning_store.load_feedback(root=tmp_path), root=tmp_path,
    )
    by = {(e["project_id"], e["qid"]): e for e in ex}
    assert set(by.keys()) == {("p1", "q1")}  # q2(rejected) 제외
    assert by[("p1", "q1")]["source"] == "human"
    assert by[("p1", "q1")]["assistant"] == "사람이 승인한 문장"


def test_dedup_same_key_across_traces(tmp_path: Path) -> None:
    q = [{"question_id": "q1", "label": "문제 인식", "target": {"kind": "section"}}]
    _seed_trace(tmp_path, "p1", q, {"q1": "첫 응답"})
    _seed_trace(tmp_path, "p1", q, {"q1": "둘째 응답"})
    ex = sft_export.build_examples(
        learning_store.load_generation_traces(root=tmp_path),
        learning_store.load_feedback(root=tmp_path), root=tmp_path,
    )
    assert len([e for e in ex if e["qid"] == "q1"]) == 1  # dedup


def test_mask_scrubs_digits_and_pii(tmp_path: Path) -> None:
    _seed_trace(
        tmp_path, "p1",
        [{"question_id": "q1", "label": "매출", "target": {"kind": "section"}}],
        {"q1": "2025년 매출 3억원, 문의 abc@x.com"},
    )
    ex = sft_export.build_examples(
        learning_store.load_generation_traces(root=tmp_path),
        learning_store.load_feedback(root=tmp_path), root=tmp_path, mask=True,
    )
    a = ex[0]["assistant"]
    assert "3억" not in a and "2025" not in a
    assert "abc@x.com" not in a


def test_build_learned_snippets_section_only_and_masked(tmp_path: Path) -> None:
    _seed_trace(
        tmp_path, "p1",
        [{"question_id": "q1", "label": "문제 인식", "target": {"kind": "section"}},
         {"question_id": "q2", "label": "매출액", "target": {"kind": "table_cell"}}],
        {"q1": "AI q1", "q2": "AI q2"},
    )
    learning_store.append_feedback(
        {"project_id": "p1", "qid": "q1", "action_type": "edited",
         "feedback": {"before": "AI q1", "after": "승인 문장 2025년 5억"}}, root=tmp_path)
    learning_store.append_feedback(
        {"project_id": "p1", "qid": "q2", "action_type": "edited",
         "feedback": {"before": "AI q2", "after": "5억원"}}, root=tmp_path)
    learned = sft_export.build_learned_snippets(
        learning_store.load_generation_traces(root=tmp_path),
        learning_store.load_feedback(root=tmp_path), root=tmp_path,
    )
    assert "문제인식" in learned          # section 은 포함
    assert "매출액" not in learned          # table_cell 은 제외(사실칸)
    assert "2025" not in learned["문제인식"][0] and "5억" not in learned["문제인식"][0]  # 마스킹


def test_export_all_counts(tmp_path: Path) -> None:
    _seed_trace(tmp_path, "p1",
                [{"question_id": "q1", "label": "문제 인식", "target": {"kind": "section"}}],
                {"q1": "AI"})
    learning_store.append_feedback(
        {"project_id": "p1", "qid": "q1", "action_type": "edited",
         "feedback": {"before": "AI", "after": "사람"}}, root=tmp_path)
    res = sft_export.export_all(root=tmp_path)
    assert res["counts"]["examples"] == 1
    assert res["counts"]["human_approved"] == 1
    assert res["jsonl"].strip()  # 비어있지 않은 JSONL


# --- 생성 소비자 -------------------------------------------------------------

class LearnedSnippetConsumerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        s = Settings(
            app_root=root / "app", workspace_root=root / "workspace",
            template_root=root / "workspace" / "templates",
            project_root=root / "workspace" / "projects", results_root=root / "results",
            static_root=root / "app" / "auto_write" / "static",
            template_view_root=root / "app" / "auto_write" / "templates",
            host="127.0.0.1", port=8765,
            openai_api_key="", openai_model="m", openai_search_model="m", openai_image_model="i",
            anthropic_api_key="", anthropic_model="c", anthropic_search_model="c",
        )
        ensure_directories(s)
        oa = OpenAIService(s)
        self.service = ProjectService(
            storage=Storage(s), openai_service=oa,
            evidence_service=EvidenceService(oa), image_service=ImageService(oa),
            render_service=RenderService(), qa_service=QAService(),
        )
        # learned_snippets 를 tmp 로 격리.
        self.learn_root = root / "learning"
        self.learn_root.mkdir(parents=True, exist_ok=True)
        self._orig_root = learning_store.LEARNING_ROOT
        learning_store.LEARNING_ROOT = self.learn_root
        (self.learn_root / "learned_snippets.json").write_text(
            json.dumps({"snippets": {"문제인식": ["과거 승인 예시 문장입니다"]}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        learning_store.LEARNING_ROOT = self._orig_root
        self.tmp.cleanup()

    def test_section_label_match_injects_masked_example(self) -> None:
        missing = [
            {"question_id": "q1", "label": "문제 인식", "target": {"kind": "section"}},
            {"question_id": "q2", "label": "기업명", "target": {"kind": "table_cell"}},  # 사실칸 제외
            {"question_id": "q3", "label": "성장 전략", "target": {"kind": "section"}},  # 미매칭
        ]
        out = self.service._suggest_learned_snippets(missing)
        self.assertIn("q1", out)
        self.assertIn("과거 승인 예시 문장입니다", out["q1"])
        self.assertNotIn("q2", out)  # table_cell
        self.assertNotIn("q3", out)  # 라벨 미매칭

    def test_no_learned_file_returns_empty(self) -> None:
        (self.learn_root / "learned_snippets.json").unlink()
        out = self.service._suggest_learned_snippets(
            [{"question_id": "q1", "label": "문제 인식", "target": {"kind": "section"}}]
        )
        self.assertEqual(out, {})


if __name__ == "__main__":
    unittest.main()
