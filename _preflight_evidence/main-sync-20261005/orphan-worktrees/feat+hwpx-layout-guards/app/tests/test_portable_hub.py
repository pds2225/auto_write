"""runtime_env · output_naming · hub 계약 테스트 (어디서든 동일 CLI)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from auto_write.services.output_naming import resolve_submit_path, sanitize_filename_part, submit_filename
from auto_write.services.runtime_env import assert_engine_allowed, detect_capabilities
from auto_write_hub import main as hub_main


def test_submit_filename_default():
    assert submit_filename(name="박다솜") == "전문상담위원_참여신청서_박다솜.hwpx"


def test_submit_filename_version_and_sanitize():
    assert submit_filename(name="박 다솜", version="v1") == "전문상담위원_참여신청서_박다솜_v1.hwpx"
    assert sanitize_filename_part('a/b:c*') == "abc"
    assert sanitize_filename_part("") == "미상"


def test_resolve_submit_path(tmp_path: Path):
    p = resolve_submit_path(tmp_path, name="박다솜")
    assert p == tmp_path / "전문상담위원_참여신청서_박다솜.hwpx"


def test_detect_capabilities_portable_core():
    caps = detect_capabilities()
    d = caps.as_dict()
    assert caps.portable_core is True
    assert d["capabilities"]["rhwp_fill"] is True
    assert d["recommended_engine"] == "rhwp-hwpx-fill"
    assert "same_cli" in d["contract"]
    assert "HWPX" in d["contract"]["everywhere"]
    assert "DOCX" in d["contract"]["not_allowed"]


def test_assert_engine_allowed_rhwp_ok():
    assert_engine_allowed("rhwp-hwpx-fill")  # no raise


def test_hub_env_exit_0():
    code = hub_main(["env"])
    assert code == 0


def test_hub_diagnose_missing_file():
    code = hub_main(["diagnose", str(APP / "no_such_file_xyz.hwpx")])
    assert code == 1


def test_hub_fill_requires_confirm(tmp_path: Path):
    code = hub_main(["fill", "--notice-folder", str(tmp_path)])
    assert code == 2


def test_hub_fill_rejects_docx_output(tmp_path: Path):
    code = hub_main(
        [
            "fill",
            "--notice-folder",
            str(tmp_path),
            "--confirm-output-plan",
            "--output",
            "docx",
        ]
    )
    assert code == 2
