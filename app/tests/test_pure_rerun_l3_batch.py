# -*- coding: utf-8 -*-
"""rerun_l3_batch 순수 헬퍼 테스트 (가짜 데이터, 한글·실파일 불필요)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "rerun_l3_batch", Path(__file__).resolve().parents[1] / "tools" / "rerun_l3_batch.py")
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _row(name, app, filled, passed, gate=True, crash="", kind="양식"):
    return {"name": name, "file": name, "kind": kind, "applicable": app, "auto_eligible": 0,
            "filled": filled, "passed": passed,
            "fill_rate": round(min(1.0, filled / app), 3) if app else "",
            "engine_ok": True, "gate_pass": gate, "form_intact": True, "lrule": "",
            "lrule_fail": "", "fail_reason": "", "crash": crash, "analysis_status": "COMPLETE",
            "seconds": 0.1}


def test_excluded_reason_tokens():
    assert mod.excluded_reason("(작성) 참가신청서_v1.hwpx") == "작성"
    assert mod.excluded_reason("양식_AutoWrite_x.hwpx") == "autowrite"
    assert mod.excluded_reason("참가신청서_제출본.hwpx") == "제출본"
    assert mod.excluded_reason("(양식) 참가신청서.hwpx") == ""
    assert mod.excluded_reason("신청서_홍길동.hwpx", ["홍길동"]) == "홍길동"


def test_list_targets_keeps_blank_hwpx_only(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "(양식) 신청서.hwpx").write_bytes(b"x")
    (tmp_path / "sub" / "신청서_최종.hwpx").write_bytes(b"x")
    (tmp_path / "공고.hwp").write_bytes(b"x")
    keep, skipped = mod.list_targets([tmp_path, tmp_path])
    assert [p.name for p in keep] == ["(양식) 신청서.hwpx"]
    assert [(p.name, why) for p, why in skipped] == [("신청서_최종.hwpx", "최종")]


def test_is_applicable_uses_state_and_decision():
    class F:
        def __init__(self, state, decision):
            self.content_state, self.decision, self.protected = state, decision, True
    assert mod.is_applicable(F("EMPTY", "REVIEW_REQUIRED"))
    assert mod.is_applicable(F("GUIDANCE", "AUTO"))
    assert not mod.is_applicable(F("EXISTING", "REVIEW_REQUIRED"))
    assert not mod.is_applicable(F("EMPTY", "NO_TARGET"))


def test_summary_and_outputs_exclude_announcements(tmp_path):
    rows = [_row("a.hwpx", 10, 5, 5), _row("b.hwpx", 4, 0, 0, gate=False),
            _row("c.hwpx", 0, 0, 0, crash="ValueError: x"), _row("공고.hwpx", 0, 0, 0, kind="공고문")]
    s = mod.write_outputs(tmp_path, rows, [(Path("x_최종.hwpx"), "최종")], {"commit": "test"})
    assert s["forms"] == 3 and s["announcements"] == 1 and s["crashes"] == 1
    assert s["applicable_total"] == 14 and s["filled_total_capped"] == 5
    assert s["pass_forms"] == 2
    assert [r["name"] for r in mod.worst(rows, 2)] == ["c.hwpx", "b.hwpx"]
    md = (tmp_path / "rerun130_l3.md").read_text(encoding="utf-8")
    assert "x_최종.hwpx (최종)" in md and "공고.hwpx" not in md.split("## 하위 15")[1].split("## 제외")[0]
    assert (tmp_path / "rerun130_l3.csv").read_text(encoding="utf-8-sig").startswith("name,kind,")
