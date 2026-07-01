"""수용검사 결함별 '다음 행동' 안내(acceptance_remediation) + self_diagnose 통합 검증.

기능: 진단이 결함 개수만 내던 것을, 결함마다 "자동 명령으로 해결 / 사람이 값 입력 /
한글에서 수동 수정" 중 무엇을 어떻게 해야 제출 가능한지 안내하도록 만든 것을 증명한다.
"""

from __future__ import annotations

from docx import Document

from auto_write.services import acceptance_remediation as rem
from auto_write.services import usage_acceptance as ua
from auto_write.services.usage_acceptance import CheckResult, SEV_FAIL, SEV_WARN


def _run_check_ids() -> set[str]:
    """실제 검사(_ALL_CHECKS)를 빈 문서에 돌려 나오는 check_id 전체(단일 출처)."""
    doc = Document()
    doc.add_paragraph("본문 한 줄")
    cfg = ua.AcceptanceConfig()
    return {check(doc, cfg).check_id for check in ua._ALL_CHECKS}


def test_every_check_id_has_specific_remedy() -> None:
    """실제 검사 전부에 전용 안내가 있어야 한다(새 검사 추가 시 여기서 강제 실패)."""
    ids = _run_check_ids()
    assert ids  # sanity: 검사가 하나라도 있어야
    for cid in ids:
        r = rem.remedy_for(cid)
        assert r is not rem._DEFAULT, f"{cid} 에 전용 안내가 없음 — _REMEDIES 에 추가 필요"
        assert r.kind in (rem.KIND_AUTO, rem.KIND_HUMAN, rem.KIND_MANUAL)
        assert r.action.strip()
        if r.kind == rem.KIND_AUTO:
            assert rem.DOC_TOKEN in r.command, f"{cid} 자동 안내에 실행 명령이 없음"
        else:
            assert r.command == "", f"{cid} 는 자동이 아닌데 명령이 붙어 있음"


def test_unknown_check_id_falls_back_to_default() -> None:
    r = rem.remedy_for("존재하지_않는_검사")
    assert r is rem._DEFAULT
    assert r.kind == rem.KIND_MANUAL


def test_build_excludes_passed_and_orders_fail_first() -> None:
    results = [
        CheckResult("font_size_spread", "글자크기 분산", SEV_WARN, 2),
        CheckResult("self_inserted_blocks", "자기삽입 블록", SEV_FAIL, 1),
        CheckResult("empty_table_rows", "빈 표 행", SEV_WARN, 0),   # passed → 제외
        CheckResult("unresolved_markers", "미해결 마커", SEV_FAIL, 3),
    ]
    items = rem.build_remediation(results, "제출본.docx")
    ids = [it["check_id"] for it in items]

    assert "empty_table_rows" not in ids           # 통과한 검사는 남은 일에서 빠진다
    assert ids[:2] == ["self_inserted_blocks", "unresolved_markers"]  # fail 먼저(원순서 유지)
    assert ids[2] == "font_size_spread"            # warn 은 뒤


def test_build_substitutes_doc_path_in_command() -> None:
    results = [CheckResult("self_inserted_blocks", "자기삽입 블록", SEV_FAIL, 1)]
    items = rem.build_remediation(results, "내 문서 v2.docx")
    cmd = items[0]["command"]
    assert "내 문서 v2.docx" in cmd
    assert rem.DOC_TOKEN not in cmd
    assert cmd.startswith("python strip_notebooklm.py")


def test_human_kind_items_have_no_command() -> None:
    results = [CheckResult("unresolved_markers", "미해결 마커", SEV_FAIL, 2)]
    items = rem.build_remediation(results, "x.docx")
    assert items[0]["kind"] == rem.KIND_HUMAN
    assert items[0]["command"] == ""


def test_unique_commands_dedups_in_first_seen_order() -> None:
    # residual_colored_runs 와 template_placeholders 는 같은 autopilot 명령을 공유
    results = [
        CheckResult("self_inserted_blocks", "블록", SEV_FAIL, 1),
        CheckResult("residual_colored_runs", "유색", SEV_FAIL, 1),
        CheckResult("template_placeholders", "자리표시", SEV_FAIL, 1),
    ]
    items = rem.build_remediation(results, "a.docx")
    cmds = rem.unique_commands(items)
    assert len(cmds) == 2                          # autopilot 명령은 한 번만
    assert cmds[0].startswith("python strip_notebooklm.py")
    assert any("auto_write_autopilot.py" in c for c in cmds)


def test_format_text_all_pass_returns_ready_line() -> None:
    lines = rem.format_remediation_text([])
    assert len(lines) == 1
    assert "바로 제출 가능" in lines[0]


def test_format_text_groups_by_kind_and_lists_commands() -> None:
    results = [
        CheckResult("self_inserted_blocks", "자기삽입 블록", SEV_FAIL, 2),
        CheckResult("unresolved_markers", "미해결 마커", SEV_FAIL, 5),
        CheckResult("font_size_spread", "글자크기 분산", SEV_WARN, 3),
    ]
    items = rem.build_remediation(results, "제출본.docx")
    text = "\n".join(rem.format_remediation_text(items))

    assert "제출까지 남은 일" in text
    assert "자동으로 해결" in text and "사람이 직접 입력" in text
    assert "자기삽입 블록(2)" in text
    assert "미해결 마커(5)" in text
    assert "글자크기 분산(3) (경고)" in text        # warn 은 (경고) 꼬리표
    assert 'python strip_notebooklm.py "제출본.docx"' in text  # 실행 명령 그대로 복붙 가능


# --- self_diagnose CLI 통합: 결함 있는 문서 진단 시 '다음 행동'이 출력·JSON 에 실린다 ---

def _defective_docx(path) -> None:
    doc = Document()
    doc.add_paragraph("[확인필요]")                       # unresolved_markers (사람 입력)
    doc.add_paragraph("이 블록은 삭제하세요")               # self_inserted_blocks (자동 제거)
    doc.save(str(path))


def test_self_diagnose_prints_and_saves_remediation(tmp_path, capsys) -> None:
    import self_diagnose as sd

    docx = tmp_path / "결함문서.docx"
    _defective_docx(docx)
    out_json = tmp_path / "결과.json"

    rc = sd.main([str(docx), "--json", str(out_json)])
    captured = capsys.readouterr().out

    assert rc == 2                                        # 제출불가(fail 존재)
    assert "제출까지 남은 일" in captured
    # 자동 해결 명령이 실제 문서 경로로 안내된다
    assert "strip_notebooklm.py" in captured
    # 사람이 입력해야 하는 항목도 구체 행동으로 안내된다
    assert "지어내면 안 됩니다" in captured

    import json
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert "remediation" in data
    kinds = {it["kind"] for it in data["remediation"]}
    assert rem.KIND_AUTO in kinds and rem.KIND_HUMAN in kinds
    # 각 항목이 check_id·action 을 기계가 읽을 수 있게 담는다
    assert all(it["check_id"] and it["action"] for it in data["remediation"])


def test_self_diagnose_clean_doc_reports_no_remaining_work(tmp_path, capsys) -> None:
    import self_diagnose as sd

    docx = tmp_path / "깨끗한문서.docx"
    doc = Document()
    doc.add_paragraph("정상 본문입니다. 결함이 없습니다.")
    doc.save(str(docx))

    rc = sd.main([str(docx)])
    captured = capsys.readouterr().out

    assert rc == 0
    assert "바로 제출 가능" in captured
