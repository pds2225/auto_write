"""CLI wiring for M4 generate_missing (mock-only, hybrid path, budget_zero)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from auto_write.image_automation.models import (
    AnchorCandidate,
    MatchAction,
    MatchDecision,
    PsstClass,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_business_plan_images.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("run_business_plan_images", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _m2_stub(tmp_path: Path) -> SimpleNamespace:
    anchors = [
        AnchorCandidate(
            anchor_id="a1",
            psst=PsstClass.PROBLEM.value,
            needed_visual_type="막대/도넛 차트",
            keywords=["시장규모"],
            text_preview="시장",
        )
    ]
    matches = [MatchDecision(anchor_id="a1", action=MatchAction.SKIP)]
    return SimpleNamespace(
        run_dir=tmp_path,
        manifest=SimpleNamespace(anchors=anchors, matches=matches),
    )


@pytest.fixture(scope="module")
def cli():
    return _load_cli()


def test_enable_generate_missing_help_says_mock(cli):
    help_text = cli.build_parser().format_help()
    assert "mock" in help_text.lower()
    assert "실 OpenAI" in help_text or "OpenAI 호출 없음" in help_text


def test_run_m4_budget_zero_warns_and_receipt(cli, tmp_path: Path, capsys):
    rc = cli._run_m4_generate_missing(_m2_stub(tmp_path), max_paid_calls=0)
    assert rc == 0
    err = capsys.readouterr().err
    assert "budget_zero" in err or "max-paid-calls" in err
    receipt = json.loads(
        (tmp_path / "generate_missing" / "generate_missing_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["reason"] == "budget_zero"
    assert receipt["use_mock"] is True
    assert receipt["openai_calls_real"] == 0


def test_run_m4_prints_use_mock_true(cli, tmp_path: Path, capsys):
    cli._run_m4_generate_missing(_m2_stub(tmp_path), max_paid_calls=1)
    out = capsys.readouterr().out
    assert "use_mock" in out
    assert "no real OpenAI" in out or "mock stub" in out
    payload = json.loads(out.split("--- M4", 1)[1].split("\n", 1)[1])
    assert payload["use_mock"] is True
    assert payload["openai_calls_real"] == 0
    assert payload["mock_calls"] == 1
