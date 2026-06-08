import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.config import Settings
from auto_write.models import ImageSlotProfile
from auto_write.services.openai_client import OpenAIService
from auto_write.services.image_service import ImageService
from auto_write.services import image_providers


def _settings(tmp: Path) -> Settings:
    return Settings(
        app_root=tmp, workspace_root=tmp, template_root=tmp, project_root=tmp,
        results_root=tmp, static_root=tmp, template_view_root=tmp,
        host="127.0.0.1", port=8765,
        openai_api_key="", openai_model="gpt-4.1-mini", openai_search_model="gpt-4.1-mini",
        openai_image_model="gpt-image-1",
        anthropic_api_key="", anthropic_model="m", anthropic_search_model="m",
        gemini_api_key="",
    )


class ImagePipelineTest(unittest.TestCase):
    def test_no_keys_falls_back_to_local_image_no_external_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            oa = OpenAIService(_settings(tmp_path))
            svc = ImageService(oa)
            slot = ImageSlotProfile(
                slot_id="img1",
                label="사업 추진 체계 인포그래픽",
                required=True,
                anchor_type="after_paragraph",
                anchor_ref={"anchor_text": "추진 체계"},
                source="template",
            )
            images = svc.build_images([slot], answers={}, evidence=[], output_dir=tmp_path / "g")
            self.assertEqual(len(images), 1)
            self.assertTrue(Path(images[0].path).exists())
            self.assertEqual(images[0].source, "generated")

    def test_generate_infographic_returns_empty_without_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            oa = OpenAIService(_settings(tmp_path))
            out = tmp_path / "x.png"
            provider = image_providers.generate_infographic(oa.settings, oa, "테스트 인포그래픽", out)
            self.assertEqual(provider, "")
            self.assertFalse(out.exists())

    def test_extract_numbers_same_unit_and_empty(self):
        oa = OpenAIService(_settings(Path(tempfile.gettempdir())))
        svc = ImageService(oa)
        nums = svc._extract_numbers("1년차 120억, 2년차 240억, 3년차 360억 목표")
        self.assertGreaterEqual(len(nums), 2)
        self.assertEqual(nums[0][2], "억")
        self.assertEqual(svc._extract_numbers("특별한 수치 없음"), [])


if __name__ == "__main__":
    unittest.main()
