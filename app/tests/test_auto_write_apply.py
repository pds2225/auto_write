"""test_auto_write_apply.py — image_apply / psst_fill / autopilot_pipeline 회귀 테스트.

새로 추가한 '실제 수정' 모듈들이:
  - 원본을 덮어쓰지 않고(out==in 가드)
  - 표 실측치가 있으면 차트를, 없으면 자리표시를 삽입하며
  - PSST 미흡/누락 영역에 작성 가이드를 추가하고
  - autopilot 이 전 단계를 무인 연속 실행하는지
를 검증한다. (숫자 날조가 없어야 함 — placeholder 폴백 동작 포함)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from auto_write.services.image_apply import apply_images, strip_notebooklm_blocks
from auto_write.services.psst_fill import apply_psst_scaffold
from auto_write.services.usage_acceptance import run_acceptance


def _make_doc(path: Path, *, with_table: bool = True) -> None:
    doc = Document()
    doc.add_heading("사업계획서", 0)
    doc.add_paragraph("가. 문제인식: 고객 시장 니즈와 기존 대안의 한계로 비용 손실.")
    doc.add_paragraph("나. 추진일정 로드맵 — 단계별 마일스톤.")          # gantt 트리거
    doc.add_paragraph("다. 목표 시장규모 TAM SAM SOM 성장률 전망.")       # 막대/도넛 트리거
    if with_table:
        t = doc.add_table(rows=2, cols=3)
        t.rows[0].cells[0].text = "2024년"
        t.rows[0].cells[1].text = "2025년"
        t.rows[0].cells[2].text = "2026년"
        t.rows[1].cells[0].text = "100"
        t.rows[1].cells[1].text = "200"
        t.rows[1].cells[2].text = "350"
    doc.save(str(path))


def test_apply_images_in_equals_out_blocked(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        apply_images(str(src), str(src))


def test_apply_images_inserts_notebooklm_prompt(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    report = apply_images(str(src), str(out))  # openai_service=None → 키워드 폴백
    assert out.exists()
    # 원본은 그대로(문단 수 변화 없음)
    assert len(Document(str(src)).paragraphs) < len(Document(str(out)).paragraphs)
    # 그림 위치마다 NotebookLM 슬라이드 프롬프트 블록이 삽입되어야 한다
    assert report.prompts_inserted >= 1
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "NotebookLM" in text


def test_apply_images_placeholder_only_still_inserts_prompt(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    # placeholder_only 는 하위호환용(동작에 영향 없음) — 항상 프롬프트 블록 삽입
    report = apply_images(str(src), str(out), placeholder_only=True)
    assert report.prompts_inserted >= 1


def test_apply_images_no_table_still_inserts_prompt(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=False)
    report = apply_images(str(src), str(out))
    # 표가 없어도 키워드 매칭 위치에 슬라이드 프롬프트가 들어간다 (숫자 날조 없음)
    assert report.prompts_inserted >= 1


def test_apply_images_table_anchor_inserts_after_table_not_end(tmp_path: Path) -> None:
    """버그① 회귀: 키워드가 '표 헤더'에만 있는(표 기반 양식) 경우에도
    NotebookLM 프롬프트가 문서 끝에 덤프되지 않고 해당 표 바로 뒤에 들어가야 한다."""
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    doc.add_paragraph("개요: 본 사업계획서 본문(키워드 없음).")
    table = doc.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "추진 일정"          # 로드맵/간트 트리거(표 헤더)
    table.rows[0].cells[1].text = "마일스톤"
    table.rows[0].cells[2].text = "담당"
    table.rows[1].cells[0].text = "1분기"
    doc.add_paragraph("맺음말: 마지막 본문 단락.")       # 표보다 뒤에 있는 본문
    doc.save(str(src))

    report = apply_images(str(src), str(out))            # openai_service=None → 키워드 폴백
    assert report.prompts_inserted >= 1
    assert report.anchors_missing == 0                   # 표 앵커를 찾았어야 함

    # 본문 순서상: 표(tbl) < NotebookLM 프롬프트 < 맺음말  (끝에 덤프 아님)
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph as _P
    out_doc = Document(str(out))
    seq = []
    for child in out_doc.element.body:
        if child.tag == qn("w:tbl"):
            seq.append(("tbl", ""))
        elif child.tag == qn("w:p"):
            seq.append(("p", _P(child, out_doc).text))
    idx_tbl = next(i for i, s in enumerate(seq) if s[0] == "tbl")
    idx_prompt = next(i for i, s in enumerate(seq) if "NotebookLM" in s[1])
    idx_end = next(i for i, s in enumerate(seq) if "맺음말" in s[1])
    assert idx_tbl < idx_prompt < idx_end


def test_submittable_filler_paragraph_fill_in_table_cell(tmp_path: Path) -> None:
    """버그①b 회귀: 채울 본문 앵커가 '표 셀 안'에 있어도 누락 없이 채워야 한다
    (이전엔 doc.paragraphs 만 봐서 표 셀 앵커를 '본문 앵커 미발견'으로 건너뜀)."""
    from auto_write.services.submittable_filler import SubmittableFiller

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    doc.add_paragraph("머리말")
    t = doc.add_table(rows=1, cols=1)
    t.rows[0].cells[0].text = "5. AI 인재활용 계획 세부내용 작성"   # 표 셀 안 앵커
    doc.save(str(src))

    plan = {"paragraph_fills": [
        {"anchor": "5. AI 인재활용 계획 세부내용 작성",
         "lines": ["실제 인재활용 계획 내용입니다.", "하위 항목 1"]}
    ]}
    report = SubmittableFiller(plan).finalize(src, out)
    assert report["paragraphs_filled"] == 1
    assert not any("앵커 미발견" in n for n in report["notes"])
    cell_text = "\n".join(
        c.text for tb in Document(str(out)).tables for r in tb.rows for c in r.cells
    )
    assert "실제 인재활용 계획 내용입니다." in cell_text


def test_psst_scaffold_adds_guidance(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src)  # team/scale 영역이 비어 미흡/누락
    report = apply_psst_scaffold(str(src), str(out))
    assert out.exists()
    assert report.areas_scaffolded >= 1
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "작성 보강 가이드" in text


def test_psst_scaffold_in_equals_out_blocked(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        apply_psst_scaffold(str(src), str(src))


def test_autopilot_end_to_end(tmp_path: Path) -> None:
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    report = run_autopilot(str(src), str(out), write_report=False)
    assert Path(report.output_docx).exists()
    assert report.backup_dir  # 원본 백업이 생성되어야 함
    assert report.score_total > 0
    # 그림 위치에 NotebookLM 프롬프트가 최소 1개, PSST 보강이 일어났을 것
    assert report.prompts_inserted >= 1
    assert report.psst_areas_scaffolded >= 1
    # R8 게이트: NotebookLM 작업용 블록이 삽입된 출력은 '제출본'이 아니다 —
    # 수용검사 fail → 파일명 _DRAFT 강제, 원래 이름으로는 내보내지 않는다.
    assert report.acceptance_submittable is False
    assert report.draft_marked is True
    assert report.output_docx.endswith("_DRAFT.docx")
    assert not out.exists()


def test_autopilot_acceptance_gate_passes_clean_doc(tmp_path: Path) -> None:
    """R8: 수용검사를 통과하는 출력은 지정한 이름 그대로 내보낸다."""
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "clean.docx"
    out = tmp_path / "clean_out.docx"
    doc = Document()
    doc.add_paragraph("개요: 본 문서는 게이트 검증용입니다.")  # 이미지/PSST 트리거 없음
    doc.save(str(src))
    report = run_autopilot(
        str(src), str(out), max_images=0, psst_scaffold=False, write_report=False
    )
    assert report.acceptance_submittable is True
    assert report.acceptance_verdict == "제출가능"
    assert report.draft_marked is False
    assert report.output_docx == str(out) and out.exists()


def test_autopilot_acceptance_gate_can_be_disabled(tmp_path: Path) -> None:
    """acceptance_gate=False 면 기존 동작 그대로(이름 유지, 판정 없음)."""
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    report = run_autopilot(str(src), str(out), acceptance_gate=False, write_report=False)
    assert report.acceptance_verdict == ""
    assert report.draft_marked is False
    assert report.output_docx == str(out) and out.exists()


def test_autopilot_gate_fail_closed_on_acceptance_error(tmp_path: Path, monkeypatch) -> None:
    """R9: 게이트 자신이 죽어도 통과로 취급하지 않는다(fail-closed) —
    예외가 전파되지 않고 acceptance_error 기록 + _DRAFT 강제 + 리포트 보존."""
    from auto_write.services import autopilot_pipeline

    def _boom(*_args, **_kwargs):  # 실제 시그니처(path, config) 변화에 둔감하게
        raise RuntimeError("acceptance crashed")

    monkeypatch.setattr(autopilot_pipeline, "run_acceptance", _boom)
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src)
    report = autopilot_pipeline.run_autopilot(
        str(src), str(out), max_images=0, psst_scaffold=False, write_report=False
    )
    assert "RuntimeError" in report.acceptance_error
    assert report.acceptance_verdict == ""          # 판정 자체는 없었음
    assert report.draft_marked is True              # 판정 불가 = 제출 금지
    assert report.output_docx.endswith("_DRAFT.docx")
    assert Path(report.output_docx).exists() and not out.exists()
    assert any("수용검사 실행 실패" in t for t in report.manual_todo)


def test_autopilot_draft_collision_uses_alternate_name(tmp_path: Path) -> None:
    """R9: 입력이 '<출력>_DRAFT.docx' 인 재실행 흐름에서도 침묵 스킵 없이
    _DRAFT2 대체 이름으로 마킹한다(원본 보존 + 제출본 이름 차단)."""
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "X_DRAFT.docx"
    out = tmp_path / "X.docx"
    _make_doc(src, with_table=True)  # NotebookLM 블록 삽입 → 수용검사 fail 유도
    report = run_autopilot(str(src), str(out), write_report=False)
    assert report.acceptance_submittable is False
    assert report.draft_marked is True
    assert report.output_docx.endswith("X_DRAFT2.docx")
    assert src.exists()                             # 입력 원본 보존
    assert Path(report.output_docx).exists() and not out.exists()


def test_autopilot_in_equals_out_blocked(tmp_path: Path) -> None:
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        run_autopilot(str(src), str(src))


# --- bizplan 생성·완성 오케스트레이터 (AI 비의존 결정론 경로) ---

def test_ai_writer_skips_without_key(tmp_path: Path) -> None:
    from auto_write.services.bizplan_ai_writer import ai_write_areas

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src)
    r = ai_write_areas(str(src), str(out), openai_service=None)
    assert r.skipped is True          # AI 키 없으면 본문 작성 생략(안전)
    assert out.exists()
    assert r.areas_written == 0


def test_bizplan_no_ai_completes(tmp_path: Path) -> None:
    from auto_write.services.bizplan_autopilot import run_bizplan_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    r = run_bizplan_autopilot(str(src), str(out), use_ai=False, write_report=False)
    assert Path(r.output_docx).exists()
    assert r.loops_run == 1           # 공고 없음 → 1회 완성
    assert r.ai_used is False
    assert r.backup_dir               # 원본 백업 생성
    # R8 전파: NotebookLM 블록이 든 중간본이 fail 이면 최종 복사본도 _DRAFT 를 유지해야
    # 한다 (이전 버그: shutil.copyfile 이 깨끗한 이름으로 복사해 DRAFT 마킹 소실).
    assert r.acceptance_submittable is False
    assert r.draft_marked is True
    assert r.output_docx.endswith("_DRAFT.docx")
    assert not out.exists()           # '제출' 이름으로는 내보내지 않는다
    assert any("제출 금지" in t for t in r.manual_todo)


def test_bizplan_in_equals_out_blocked(tmp_path: Path) -> None:
    from auto_write.services.bizplan_autopilot import run_bizplan_autopilot

    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        run_bizplan_autopilot(str(src), str(src), use_ai=False)


# --- NotebookLM 블록 제거 (R5 오답노트: 제출본에 작업용 블록 잔존 재발 방지) ---

def _check(path: Path, check_id: str):
    return next(r for r in run_acceptance(path).results if r.check_id == check_id)


def test_strip_notebooklm_in_equals_out_blocked(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        strip_notebooklm_blocks(str(src), str(src))


def test_strip_notebooklm_removes_all_blocks(tmp_path: Path) -> None:
    """apply_images 가 넣은 블록이 strip 후 0이어야 하고(검출=usage_acceptance),
    실본문은 한 글자도 사라지면 안 된다."""
    src = tmp_path / "in.docx"
    mid = tmp_path / "with_blocks.docx"
    out = tmp_path / "stripped.docx"
    _make_doc(src, with_table=True)

    report = apply_images(str(src), str(mid))            # openai_service=None → 키워드 폴백
    assert report.prompts_inserted >= 1
    assert _check(mid, "self_inserted_blocks").defects >= 1   # 삽입본은 FAIL 상태

    strip = strip_notebooklm_blocks(str(mid), str(out))
    assert strip.markers_removed >= 1
    assert strip.paragraphs_removed >= strip.markers_removed  # 구분선·프롬프트도 삭제
    assert _check(out, "self_inserted_blocks").defects == 0

    # 블록 5단락이 전부 제거되어 본문이 원본과 동일해야 함(오삭제·잔여물 모두 불가)
    src_texts = [p.text for p in Document(str(src)).paragraphs if p.text.strip()]
    out_texts = [p.text for p in Document(str(out)).paragraphs if p.text.strip()]
    assert out_texts == src_texts


def test_strip_notebooklm_partial_block_marker_only(tmp_path: Path) -> None:
    """실문서 재현: 사용자가 일부만 지워 헤더·안내만 남은 경우에도 마커는 제거하고
    인접 실본문은 건드리지 않는다(구조 미확인 시 보수적으로 마커만 삭제)."""
    src = tmp_path / "partial.docx"
    out = tmp_path / "stripped.docx"
    doc = Document()
    doc.add_paragraph("실제 본문 내용 A")
    doc.add_paragraph("📊 [NotebookLM 슬라이드 생성용 프롬프트] · 유형: pie")
    doc.add_paragraph("↓ 아래 문장을 NotebookLM 슬라이드 생성에 붙여넣으세요")
    doc.add_paragraph("실제 본문 내용 B")
    doc.save(str(src))

    strip = strip_notebooklm_blocks(str(src), str(out))
    assert strip.markers_removed == 2
    texts = [p.text for p in Document(str(out)).paragraphs if p.text.strip()]
    assert texts == ["실제 본문 내용 A", "실제 본문 내용 B"]
    assert _check(out, "self_inserted_blocks").defects == 0


def test_strip_notebooklm_no_blocks_noop_copy(tmp_path: Path) -> None:
    src = tmp_path / "clean.docx"
    out = tmp_path / "out.docx"
    _make_doc(src)
    strip = strip_notebooklm_blocks(str(src), str(out))
    assert strip.markers_removed == 0
    assert strip.paragraphs_removed == 0
    assert [p.text for p in Document(str(out)).paragraphs] == \
        [p.text for p in Document(str(src)).paragraphs]


# --- US-3c: 산출 형식 게이트(ACC-5) -------------------------------------------

def test_autopilot_required_format_gate(tmp_path: Path) -> None:
    """ACC-5: 요구 형식(hwp)과 산출(docx)이 다르면 제출명 차단 + 변환 안내."""
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=False)
    report = run_autopilot(
        str(src), str(out), max_images=0, psst_scaffold=False,
        required_format="hwp", write_report=False,
    )
    assert report.format_mismatch
    assert report.output_docx.endswith("_DRAFT.docx") or report.output_docx.endswith("_DRAFT2.docx")
    assert any("산출 형식 불일치" in t for t in report.manual_todo)


def test_autopilot_required_format_match_no_gate(tmp_path: Path) -> None:
    """요구 형식이 docx 로 일치하면 형식 게이트가 개입하지 않는다."""
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=False)
    report = run_autopilot(
        str(src), str(out), max_images=0, psst_scaffold=False,
        required_format="docx", write_report=False,
    )
    assert report.format_mismatch == ""


# --- US-4: 재실행 보호·--strict 종료코드·공고파일 경고(PIPE-2/3/7) --------------

def test_autopilot_rerun_preserves_previous_output(tmp_path: Path) -> None:
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    doc.add_paragraph("개요: 게이트 통과용 깨끗한 문서.")
    doc.save(str(src))
    r1 = run_autopilot(str(src), str(out), max_images=0, psst_scaffold=False, write_report=False)
    assert r1.overwrite_backup == "" and Path(r1.output_docx) == out
    r2 = run_autopilot(str(src), str(out), max_images=0, psst_scaffold=False, write_report=False)
    assert r2.overwrite_backup and Path(r2.overwrite_backup).exists()  # 1회차 산출물 보존


def test_cli_strict_exit_codes(tmp_path: Path, monkeypatch) -> None:
    """PIPE-3: --strict 시 0/2/3 계약, 미지정 시 기존 exit 0 호환."""
    import auto_write_autopilot as cli

    src = tmp_path / "bad.docx"
    doc = Document()
    doc.add_paragraph("사업비 [확인필요] 원")
    doc.save(str(src))
    common = ["--no-psst", "--max-images", "0", "--no-report"]
    assert cli.main([str(src), "-o", str(tmp_path / "o1.docx")] + common) == 0
    assert cli.main([str(src), "-o", str(tmp_path / "o2.docx"), "--strict"] + common) == 2

    from auto_write.services import autopilot_pipeline

    def _boom(*_a, **_k):
        raise RuntimeError("crash")

    monkeypatch.setattr(autopilot_pipeline, "run_acceptance", _boom)
    assert cli.main([str(src), "-o", str(tmp_path / "o3.docx"), "--strict"] + common) == 3


def test_submit_announcement_missing_warns(tmp_path: Path) -> None:
    """PIPE-7: 공고 파일 부재를 침묵하지 않는다."""
    from auto_write.submit import _read_announcement

    ann, warn = _read_announcement("", str(tmp_path / "없는공고.txt"), lambda p: "x")
    assert ann == "" and "찾을 수 없음" in warn
    ann2, warn2 = _read_announcement("직접 텍스트", "ignored.txt", lambda p: "x")
    assert ann2 == "직접 텍스트" and warn2 == ""


# --- US-6: extract+strip(--submit-clean) — PIPE-6/LEDG-4 -----------------------

def test_extract_matches_strip_identification(tmp_path: Path) -> None:
    """extract 와 strip 이 같은 식별을 공유 — 추출 후 strip 하면 블록 0, 본문서 프롬프트 소멸."""
    from auto_write.services.image_apply import extract_notebooklm_prompts

    src = tmp_path / "in.docx"
    mid = tmp_path / "mid.docx"
    out = tmp_path / "stripped.docx"
    _make_doc(src, with_table=True)
    apply_images(str(src), str(mid))
    prompts = extract_notebooklm_prompts(str(mid))
    assert prompts, "삽입된 프롬프트 본문이 추출돼야 한다"
    strip_notebooklm_blocks(str(mid), str(out))
    assert extract_notebooklm_prompts(str(out)) == []          # 동치: 지운 뒤 추출 0
    assert _check(out, "self_inserted_blocks").defects == 0    # 게이트 기준으로도 잔존 0
    text_after = "\n".join(p.text for p in Document(str(out)).paragraphs)
    for pr in prompts:
        assert pr[:20] not in text_after                       # 추출분이 문서에 안 남음


def test_autopilot_submit_clean_passes_gate(tmp_path: Path) -> None:
    """--submit-clean: 프롬프트 md 보존 + 블록 제거 후 게이트 통과 — '항상 _DRAFT' 해소."""
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    report = run_autopilot(
        str(src), str(out), psst_scaffold=False, submit_clean=True, write_report=False
    )
    assert report.prompts_inserted >= 1 and report.strip_removed >= 1
    assert report.prompt_md and Path(report.prompt_md).exists()
    assert len(Path(report.prompt_md).read_text(encoding="utf-8")) > 10  # 내용 보존
    assert report.acceptance_submittable is True
    assert report.output_docx == str(out) and out.exists()


def test_strip_cli_gates_final_name(tmp_path: Path) -> None:
    """strip CLI: fail 잔존 문서는 '_제출용' 명명 차단(_DRAFT), 깨끗하면 _제출용 (LEDG-4)."""
    import strip_notebooklm as cli
    from auto_write.services.image_apply import apply_images as _ai

    # (a) 블록 + 다른 fail(빈 명칭 칸) 잔존 → _DRAFT, '_제출용' 금지
    bad = tmp_path / "bad.docx"
    doc = Document()
    doc.add_paragraph("다. 목표 시장규모 TAM SAM SOM 성장률 전망.")
    t = doc.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "명 칭"
    t.cell(0, 1).text = ""
    doc.save(str(bad))
    mid = tmp_path / "bad_nlm.docx"
    _ai(str(bad), str(mid))
    rc = cli.main([str(mid)])
    assert rc == 2
    assert not list(tmp_path.glob("*_제출용.docx"))
    assert list(tmp_path.glob("*_정리본_DRAFT.docx"))

    # (b) 깨끗한 문서 + 블록 → strip 후 통과 → _제출용
    good = tmp_path / "good.docx"
    doc2 = Document()
    doc2.add_paragraph("다. 목표 시장규모 TAM SAM SOM 성장률 전망.")
    doc2.save(str(good))
    mid2 = tmp_path / "good_nlm.docx"
    _ai(str(good), str(mid2))
    rc2 = cli.main([str(mid2)])
    assert rc2 == 0
    assert list(tmp_path.glob("good_nlm_제출용.docx"))
    assert list(tmp_path.glob("good_nlm_슬라이드프롬프트.md"))
