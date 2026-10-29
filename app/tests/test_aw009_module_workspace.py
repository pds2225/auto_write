from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from docx import Document

from auto_write.services import module_workspace as aw


@pytest.fixture(autouse=True)
def isolated_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(aw, "ROOT", tmp_path / "workspaces")


def docx(*paragraphs: str) -> bytes:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def sample_hwpx() -> bytes:
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
    <hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
            xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
      <hp:p><hp:run><hp:t>1. 시장 경쟁</hp:t></hp:run></hp:p>
      <hp:p><hp:run><hp:t>경쟁사 비교표의 실제 내용</hp:t></hp:run></hp:p>
    </hs:sec>'''.encode("utf-8")
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("Contents/section0.xml", xml)
        z.writestr("Version.xml", "<version/>")
    return b.getvalue()


def sample_inputs():
    return ("공고.txt", b"2026 test announcement"), (
        "양식.docx", docx("1. 사업개요", "서술 입력", "2. 시장분석", "작성 공간")
    ), [("기존계획서.docx", docx("1. 경쟁 분석", "A사는 B를 해결한다.", "비교표 내용"))]


def test_roles_and_announcement_mandatory():
    announcement, template, references = sample_inputs()
    with pytest.raises(ValueError, match="필수"):
        aw.start(None, template, references, roles_confirmed=True)
    with pytest.raises(ValueError, match="역할"):
        aw.start(announcement, template, references, roles_confirmed=False)


def test_docx_toc_and_source_modules_have_real_locator_and_no_fake_page():
    announcement, template, references = sample_inputs()
    state = aw.start(announcement, template, references, roles_confirmed=True)
    assert [s["title"] for s in state["toc"]] == ["1. 사업개요", "2. 시장분석"]
    assert state["modules"]
    blocks = [b for m in state["modules"] for b in m["blocks"]]
    assert any(b["text"] == "A사는 B를 해결한다." for b in blocks)
    assert all(b["locator"]["format"] == "docx" for b in blocks)
    assert all(b["page"] is None for b in blocks)
    assert not state["approved"]
    assert state["status"] == "WAITING_PLAN"
    assert not (aw._base(state["id"]) / "plan.json").exists()


def test_composition_is_approval_gated_with_explicit_source_ids():
    announcement, template, references = sample_inputs()
    state = aw.start(announcement, template, references, roles_confirmed=True)
    wid = state["id"]
    block = state["modules"][0]["blocks"][1]["id"]
    with pytest.raises(ValueError, match="승인"):
        aw.record_execution(wid, "RUNNING")
    with pytest.raises(ValueError, match="없는 선택"):
        aw.plan(wid, "section-1", ["invented-id"], "그대로")
    plan = aw.plan(wid, "section-1", [block], "[1]은 그대로")
    assert plan["approved"] is False
    assert plan["selected_material_ids"] == [block]
    assert len(plan["source_locators"]) == 1
    assert plan["source_locators"][0]["page"] is None
    assert aw.get(wid)["status"] == "PLAN_READY"
    state = aw.approve(wid)
    assert state["approved"] is True
    assert state["plan"]["approved"] is True
    aw.record_execution(wid, "BLOCKED", reason="native test not run")
    assert aw.get(wid)["status"] == "BLOCKED"
    with pytest.raises(ValueError, match="이미 승인"):
        aw.plan(wid, "section-2", [block], "다시 작성")


def test_combined_file_role_requires_human_confirm():
    _, template, _ = sample_inputs()
    state = aw.start(None, template, [], combined=True, roles_confirmed=True)
    assert state["combined"] and state["roles_confirmed"]
    assert state["announcement_file"]["sha256"] == state["template_file"]["sha256"]
    plan = aw.plan(state["id"], state["toc"][0]["id"], [], "출처 없이 새 서술을 만들어줘")
    assert plan["generation_label_required"] is True


def test_hwpx_module_keeps_exact_original_bytes_and_structure_locator():
    announcement, template, _ = sample_inputs()
    original = sample_hwpx()
    state = aw.start(announcement, template, [("기존.hwpx", original)], roles_confirmed=True)
    folder = aw._base(state["id"])
    stored = next(row for row in state["inputs"] if row["filename"] == "기존.hwpx")
    assert (folder / stored["stored"]).read_bytes() == original
    blocks = [b for m in state["modules"] for b in m["blocks"]]
    assert any("경쟁사 비교표" in b["text"] for b in blocks)
    assert all(b["locator"]["format"] == "hwpx" for b in blocks)
    assert all("section" in b["locator"] and "paragraph" in b["locator"] for b in blocks)
    assert all(b["page"] is None for b in blocks)


def test_nested_form_heading_is_not_a_new_major_toc():
    announcement = ("공고.txt", b"announcement")
    template = ("양식.docx", docx("1. 사업개요", "1-1. 개요", "2. 시장분석"))
    state = aw.start(announcement, template, [], roles_confirmed=True)
    assert [row["title"] for row in state["toc"]] == ["1. 사업개요", "2. 시장분석"]


def test_number_instructions_only_interpreted_when_unambiguous():
    announcement, template, references = sample_inputs()
    state = aw.start(announcement, template, references, roles_confirmed=True)
    blocks = [b["id"] for m in state["modules"] for b in m["blocks"]][:2]
    result = aw.plan(state["id"], "section-1", blocks, "[1]은 그대로. [2]는 표에 추가.")
    assert result["ai_interpreted_actions"][0]["action"] == "원문 그대로"
    assert result["ai_interpreted_actions"][1]["action"] == "해당 파트에 추가"
    assert result["selected_material_ids"] == blocks


def test_ambiguous_numbered_plan_cannot_execute():
    ann, tmpl, refs = sample_inputs()
    state = aw.start(ann, tmpl, refs, roles_confirmed=True)
    block = state["modules"][0]["blocks"][0]["id"]
    aw.plan(state["id"], "section-1", [block], "좋은 문장을 써줘")
    with pytest.raises(ValueError, match="모호"):
        aw.approve(state["id"])
    assert not aw.get(state["id"])["approved"]


def test_invalid_announcement_file_type_refused():
    _, tmpl, refs = sample_inputs()
    with pytest.raises(ValueError, match="첨부파일"):
        aw.start(("bad.exe", b"executable"), tmpl, refs, roles_confirmed=True)
