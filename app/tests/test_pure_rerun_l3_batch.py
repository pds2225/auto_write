# -*- coding: utf-8 -*-
"""rerun_l3_batch 순수 헬퍼 테스트 (가짜 데이터, 한글·실파일 불필요)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

_SPEC = importlib.util.spec_from_file_location(
    "rerun_l3_batch", Path(__file__).resolve().parents[1] / "tools" / "rerun_l3_batch.py")
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _f(label, state="EMPTY", ftype="T02", decision="REVIEW_REQUIRED", row=0, col=1, table=0, kinds=()):
    return NS(field_label=label, content_state=state, field_type=ftype, decision=decision,
              structure_types=kinds, section_index=0, table_index=table, row=row, col=col,
              paragraph_index=None)


def _row(name, papp, pfill, gate=True, crash="", kind="양식", napp=0, nfill=0):
    r = mod._blank_row(Path(name))
    r.update(kind=kind, profile_app=papp, profile_fill=pfill, narrative_app=napp, narrative_fill=nfill,
             profile_rate=round(pfill / papp, 3) if papp else "", engine_ok=True, gate_pass=gate,
             crash=crash, passed=pfill if gate else 0)
    return r


def test_excluded_reason_name_rules():
    assert mod.excluded_reason("(작성) 참가신청서.hwpx") == "작성"
    assert mod.excluded_reason("_step_identity.hwpx") == "_step_"
    assert mod.excluded_reason("02_filled.hwpx") == "filled"
    assert mod.excluded_reason("12_signed.hwpx") == "signed"
    assert mod.excluded_reason("13_fixed.hwpx") == "fixed"
    assert mod.excluded_reason("out_result.hwpx") == "result"
    assert mod.excluded_reason("demo_sample.hwpx") == "sample"
    assert mod.excluded_reason("신청서_v2.1.hwpx") == "버전 사본(vN)"
    assert mod.excluded_reason("20_v1.hwpx") == "버전 사본(vN)"
    assert mod.excluded_reason("신청서_가상회사.hwpx", ["가상회사"]) == "가상회사"
    assert mod.excluded_reason("(양식) 참가신청서.hwpx") == ""
    assert mod.excluded_reason("서비스_소개서.hwpx") == ""


def test_list_targets_keeps_blank_hwpx_only(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "(양식) 신청서.hwpx").write_bytes(b"x")
    (tmp_path / "sub" / "신청서_최종.hwpx").write_bytes(b"x")
    (tmp_path / "공고.hwp").write_bytes(b"x")
    keep, skipped = mod.list_targets([tmp_path, tmp_path])
    assert [p.name for p in keep] == ["(양식) 신청서.hwpx"]
    assert sorted((p.name, why) for p, why in skipped) == [
        ("공고.hwp", "hwp 생략(HWPX만 측정)"), ("신청서_최종.hwpx", "최종")]


def test_classify_profile_narrative_other():
    assert mod.classify(_f("대표자 성명")) == "profile"
    assert mod.classify(_f("E-mail")) == "profile"
    assert mod.classify(_f("", kinds=("CHECKBOX",))) == "profile"
    assert mod.classify(_f("아이디어 제안배경", ftype="T15")) == "narrative"
    assert mod.classify(_f("신청자역량")) == "narrative"  # 서술 문구가 프로필 키워드보다 우선
    assert mod.classify(_f("", ftype="T07")) == "narrative"
    assert mod.classify(_f("", ftype="T16")) == "other"


def test_slots_of_dedups_and_prefers_profile():
    fields = [_f("성명", row=1), _f("세부 내용", row=1), _f("시장 현황", row=2),
              _f("기업명", state="EXISTING", row=3), _f("주소", decision="NO_TARGET", row=4)]
    slots = mod.slots_of(fields)
    assert slots == {(0, 0, 1, 1, None): "profile", (0, 0, 2, 1, None): "narrative"}


def test_is_filled_copy_by_content():
    filled = [_f(l, state="EXISTING", row=i) for i, l in enumerate(["성명", "주소", "연락처", "이메일"])]
    blank = [_f(l, row=i) for i, l in enumerate(["성명", "주소", "연락처", "이메일"])]
    assert mod.is_filled_copy(filled) == (True, 1.0)
    assert mod.is_filled_copy(blank) == (False, 0.0)
    assert mod.is_filled_copy(filled[:3])[0] is False  # 값 칸 4개 미만이면 판단 안 함
    # 채움 가능 슬롯 타입 전체(T02/T07/T15/T16)에서 값을 본다
    mixed = [_f("", state="EXISTING", row=i, ftype="T15") for i in range(4)]
    assert mod.is_filled_copy(mixed) == (True, 1.0)


def test_summary_and_outputs(tmp_path):
    rows = [_row("a.hwpx", 10, 9, napp=5, nfill=1), _row("b.hwpx", 4, 0, gate=False),
            _row("c.hwpx", 0, 0, crash="ValueError: x"), _row("공고.hwpx", 0, 0, kind="공고문"),
            _row("사본.hwpx", 0, 0, kind="채운사본")]
    s = mod.write_outputs(tmp_path, rows, [(Path("x_최종.hwpx"), "최종")], {"commit": "test"})
    assert (s["forms"], s["announcements"], s["filled_copies"], s["crashes"]) == (3, 1, 1, 1)
    assert (s["profile_applicable"], s["profile_filled"], s["profile_passed"]) == (14, 9, 9)
    assert s["profile_fill_rate"] == round(9 / 14, 3)
    assert (s["narrative_applicable"], s["narrative_filled"]) == (5, 1)
    assert [r["name"] for r in mod.worst(rows, 2)] == ["c.hwpx", "b.hwpx"]
    md = (tmp_path / "rerun130_l3.md").read_text(encoding="utf-8")
    assert "x_최종.hwpx (최종)" in md and "사본.hwpx" in md
    assert (tmp_path / "rerun130_l3.csv").read_text(encoding="utf-8-sig").startswith("name,kind,profile_app")
