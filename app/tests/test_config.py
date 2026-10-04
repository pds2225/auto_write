from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from auto_write.config import _resolve_results_root, _resolve_workspace_root, get_settings


class ConfigTests(unittest.TestCase):
    def test_resolve_workspace_root_keeps_writable_default(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            app_root = Path(tmp_dir) / "app"
            app_root.mkdir()

            workspace_root = _resolve_workspace_root(app_root)

            self.assertEqual(workspace_root, Path(tmp_dir) / "workspace")

    @patch("auto_write.config._can_write_to_dir", return_value=False)
    def test_resolve_workspace_root_falls_back_inside_app_when_default_is_not_writable(self, _mock_write):
        with tempfile.TemporaryDirectory() as tmp_dir:
            app_root = Path(tmp_dir) / "app"
            app_root.mkdir()

            workspace_root = _resolve_workspace_root(app_root)

            self.assertEqual(workspace_root, app_root / "workspace")

    def test_results_root_follows_env_and_defaults_beside_repo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            app_root = Path(tmp_dir) / "app"
            app_root.mkdir()
            with patch.dict(os.environ, {"AUTO_WRITE_RESULTS_ROOT": ""}, clear=False):
                self.assertEqual(_resolve_results_root(app_root), Path(tmp_dir) / "results")
            custom = Path(tmp_dir) / "disk" / "results"
            with patch.dict(os.environ, {"AUTO_WRITE_RESULTS_ROOT": str(custom)}, clear=False):
                settings = get_settings()
            self.assertEqual(settings.results_root, custom)

    @patch.dict(os.environ, {"AUTO_WRITE_TEMPLATE_AI_REFINE": ""}, clear=False)
    def test_template_ai_refine_is_disabled_by_default(self):
        settings = get_settings()

        self.assertFalse(settings.template_ai_refine_enabled)


if __name__ == "__main__":
    unittest.main()
