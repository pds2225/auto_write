"""마포 실양식 E2E(가짜 데이터). AUTO_WRITE_MAPO_FORM 이 있을 때만 실행하며 원본은 읽기 전용이다.

1단계: 콘솔 경로로 본문·이미지 채움(COM 차단) → 채운 HWPX 를 AUTO_WRITE_E2E_OUT 에 저장.
이후 단계(F1/F2/F5/F6/F7)는 같은 폴더의 산출물을 이어서 쓴다.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from test_submit_finish_body_images import _bizplan, _console, _no_com, _section_json  # noqa: F401
from test_hwpx_web_e2e_gate import web, client, _route, _tail, _loc  # noqa: F401


def _out() -> Path:
    p = os.environ.get("AUTO_WRITE_E2E_OUT")
    if not p:
        pytest.skip("AUTO_WRITE_E2E_OUT 없음")
    d = Path(p)
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_stage1_fill(client, monkeypatch, tmp_path):
    source = Path(os.environ.get("AUTO_WRITE_MAPO_FORM", ""))
    if not source.is_file():
        pytest.skip("AUTO_WRITE_MAPO_FORM 없음")
    out_dir = _out()
    _no_com(monkeypatch)
    plan = _bizplan(tmp_path / "plan.docx", False)
    refs = [("plan.docx", plan.read_bytes())] + _section_json(tmp_path, ["3. 창업 아이디어", "기대효과"])
    route = _console(client, source.read_bytes(), refs)
    filled = Path(route["routing"]["final"])
    shutil.copy2(filled, out_dir / "stage1_filled.hwpx")
