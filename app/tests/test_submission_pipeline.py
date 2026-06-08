import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.config import Settings
from auto_write.models import GeneratedImage, ImageSlotProfile, ProjectInput, TemplateProfile
from auto_write.services.evaluation_service import EvaluationService
from auto_write.services.evidence_service import EvidenceService
from auto_write.services.image_service import ImageService
from auto_write.services.openai_client import OpenAIService
from auto_write.services.plan_builder import build_fill_plan
from auto_write.services.render_service import RenderService
from auto_write.services.submission_orchestrator import SubmissionPipeline


def _settings(tmp: Path) -> Settings:
    return Settings(
        app_root=tmp, workspace_root=tmp, template_root=tmp, project_root=tmp,
        results_root=tmp / "results", static_root=tmp, template_view_root=tmp,
        host="127.0.0.1", port=8765,
        openai_api_key="", openai_model="m", openai_search_model="m", openai_image_model="gpt-image-1",
        anthropic_api_key="", anthropic_model="m", anthropic_search_model="m",
        gemini_api_key="",
    )


def _profile(tmp: Path) -> TemplateProfile:
    slot = ImageSlotProfile(
        slot_id="img1", label="추진 체계 인포그래픽", required=True,
        anchor_type="table_cell",
        anchor_ref={"table_index": 0, "row": 0, "cell": 0},
        source="template",
    )
    return TemplateProfile(
        template_id="t1", template_name="s.docx",
        source_docx=str(tmp / "s.docx"), image_slots=[slot],
    )


class _FakeStorage:
    def __init__(self, base: Path):
        self._base = Path(base)
        self._inputs = {}

    def project_dir(self, pid):
        d = self._base / "projects" / pid
        d.mkdir(parents=True, exist_ok=True)
        return d

    def load_project_input(self, pid):
        return self._inputs[pid]

    def save_project_input(self, pid, pi):
        self._inputs[pid] = pi


class _FakeProjectService:
    def __init__(self, storage, profile, oa):
        self.storage = storage
        self._profile = profile
        self.openai_service = oa
        self.image_service = ImageService(oa)
        self.render_service = RenderService()
        self.evidence_service = EvidenceService(oa)

    def generate(self, pid):
        out = self.storage.project_dir(pid) / "output" / "output.docx"
        out.parent.mkdir(parents=True, exist_ok=True)
        doc = Document()
        doc.add_paragraph("1. 문제 인식")
        doc.add_paragraph("시장의 문제와 해결 방안을 서술한 본문 내용입니다.")
        t = doc.add_table(rows=1, cols=1)
        t.rows[0].cells[0].text = "< 사진(이미지) 또는 설계도 제목 >"
        doc.save(str(out))
        return None

    def load_profile_for_project(self, pid):
        return self._profile


class SubmissionPipelineTest(unittest.TestCase):
    def test_plan_builder_org_and_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pi = ProjectInput(
                template_id="t1",
                organization_profile={"기업명": "테스트(주)", "대표자": "홍길동", "빈값": ""},
                project_meta={"overview": {"명칭": "테스트 사업"}},
            )
            prof = _profile(tmp_path)
            ext_dir = tmp_path / "ext"
            ext_dir.mkdir()
            (ext_dir / "fill_plan.json").write_text(
                '{"row_rewrites":[{"table_index":0,"row":0,"cols":["A"]}]}', encoding="utf-8"
            )
            plan = build_fill_plan(prof, pi, external_plan_dir=ext_dir)
            self.assertEqual(plan["identity"]["기업명"], "테스트(주)")
            self.assertNotIn("빈값", plan["identity"])
            self.assertEqual(plan["overview"]["명칭"], "테스트 사업")
            self.assertEqual(len(plan["row_rewrites"]), 1)

    def test_insert_images_into_docx(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            docx_path = tmp_path / "d.docx"
            doc = Document()
            t = doc.add_table(rows=1, cols=1)
            t.rows[0].cells[0].text = "placeholder"
            doc.save(str(docx_path))
            from PIL import Image
            png = tmp_path / "i.png"
            Image.new("RGB", (200, 120), "#2563EB").save(str(png))
            slot = ImageSlotProfile(
                slot_id="img1", label="도식", required=True,
                anchor_type="table_cell",
                anchor_ref={"table_index": 0, "row": 0, "cell": 0},
                source="template",
            )
            prof = TemplateProfile(
                template_id="t1", template_name="s.docx",
                source_docx=str(docx_path), image_slots=[slot],
            )
            img = GeneratedImage(slot_id="img1", label="도식", path=str(png), source="generated")
            rep = RenderService().insert_images_into_docx(prof, [img], docx_path)
            self.assertEqual(rep["images_written"], 1)
            out = Document(str(docx_path))
            self.assertIn("w:drawing", out.tables[0].rows[0].cells[0]._tc.xml)

    def test_pipeline_end_to_end_no_ai(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = _settings(tmp_path)
            storage = _FakeStorage(tmp_path)
            oa = OpenAIService(settings)
            prof = _profile(tmp_path)
            ps = _FakeProjectService(storage, prof, oa)
            pi = ProjectInput(
                template_id="t1",
                organization_profile={"기업명": "테스트(주)"},
                project_meta={},
            )
            storage.save_project_input("p1", pi)
            pipeline = SubmissionPipeline(ps, EvaluationService(oa), storage, settings)
            report = pipeline.run("p1", announcement_text="", enable_images=True)
            self.assertIn("generate", report["steps"])
            self.assertIn("finalize", report["steps"])
            self.assertIn("images", report["steps"])
            self.assertTrue(Path(report["submit_docx"]).exists())
            self.assertTrue(Path(report["final_docx"]).exists())
            self.assertTrue((storage.project_dir("p1") / "output" / "output.docx").exists())
            self.assertGreaterEqual(report["images"]["inserted"], 1)


if __name__ == "__main__":
    unittest.main()
