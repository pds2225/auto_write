"""P5 GENERATE_MISSING provider: gpt-image-1 only, Gemini=0."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent
import sys

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.config import Settings
from auto_write.image_automation.generate_missing import (
    GPT_IMAGE_MODEL,
    generate_missing_assets,
)
from auto_write.image_automation.models import (
    AnchorCandidate,
    MatchAction,
    MatchDecision,
    PsstClass,
)
from auto_write.services import image_providers
from auto_write.services.openai_client import OpenAIService


def _settings(tmp: Path, *, openai_key: str = "sk-test") -> Settings:
    return Settings(
        app_root=tmp,
        workspace_root=tmp,
        template_root=tmp,
        project_root=tmp,
        results_root=tmp,
        static_root=tmp,
        template_view_root=tmp,
        host="127.0.0.1",
        port=8765,
        openai_api_key=openai_key,
        openai_model="gpt-4.1-mini",
        openai_search_model="gpt-4.1-mini",
        openai_image_model=GPT_IMAGE_MODEL,
        anthropic_api_key="",
        anthropic_model="m",
        anthropic_search_model="m",
        gemini_api_key="gemini-key-present",
    )


def _anchor() -> AnchorCandidate:
    return AnchorCandidate(
        anchor_id="a1",
        psst=PsstClass.PROBLEM.value,
        needed_visual_type="막대/도넛 차트",
        keywords=["시장규모"],
        text_preview="시장규모 앵커",
    )


class GenerateMissingGptProviderTest(unittest.TestCase):
    def test_generate_missing_gpt_image_never_calls_gemini(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = _settings(tmp_path)
            oa = OpenAIService(settings)
            out = tmp_path / "out.png"
            with patch.object(image_providers, "_gemini_generate") as gemini_mock:
                with patch.object(oa, "generate_image_file", return_value=True) as openai_mock:
                    ok = image_providers.generate_missing_gpt_image(
                        settings, oa, "테스트 프롬프트", out
                    )
            self.assertTrue(ok)
            gemini_mock.assert_not_called()
            openai_mock.assert_called_once()

    def test_generate_missing_gpt_image_rejects_non_gpt_model_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = _settings(tmp_path)
            settings = Settings(
                **{
                    **base.__dict__,
                    "openai_image_model": "dall-e-3",
                }
            )
            oa = OpenAIService(settings)
            out = tmp_path / "out.png"
            with patch.object(oa, "generate_image_file", return_value=True) as openai_mock:
                ok = image_providers.generate_missing_gpt_image(
                    settings, oa, "테스트", out
                )
            self.assertFalse(ok)
            openai_mock.assert_not_called()

    def test_generate_missing_assets_real_path_gemini_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = _settings(tmp_path)
            oa = OpenAIService(settings)
            anchors = [_anchor()]
            decisions = [MatchDecision(anchor_id="a1", action=MatchAction.SKIP)]

            def _fake_generate(_self, prompt, output_path):
                output_path.write_bytes(b"\x89PNG\r\n")
                return True

            with patch.object(image_providers, "_gemini_generate") as gemini_mock:
                with patch.object(OpenAIService, "generate_image_file", _fake_generate):
                    result = generate_missing_assets(
                        anchors,
                        decisions,
                        out_dir=tmp_path / "gen",
                        enabled=True,
                        missing_only=True,
                        max_paid_calls=1,
                        use_mock=False,
                        settings=settings,
                        openai_service=oa,
                    )
            self.assertEqual(result.gemini_calls, 0)
            self.assertEqual(result.openai_calls, 1)
            self.assertEqual(result.extras.get("openai_calls_real"), 1)
            self.assertEqual(result.extras.get("mock_calls"), 0)
            self.assertEqual(len(result.generated), 1)
            gemini_mock.assert_not_called()
            self.assertTrue(result.call_log[0].model == GPT_IMAGE_MODEL)

    def test_no_openai_key_falls_back_to_no_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = _settings(tmp_path, openai_key="")
            oa = OpenAIService(settings)
            anchors = [_anchor()]
            decisions = [MatchDecision(anchor_id="a1", action=MatchAction.SKIP)]
            result = generate_missing_assets(
                anchors,
                decisions,
                out_dir=tmp_path,
                enabled=True,
                missing_only=True,
                max_paid_calls=1,
                use_mock=False,
                settings=settings,
                openai_service=oa,
            )
            self.assertEqual(result.extras.get("reason"), "no_writer")
            self.assertEqual(result.openai_calls, 0)


if __name__ == "__main__":
    unittest.main()
