"""notice_pipeline.py — mail→auto_write A→B→C(+조건부 D) 통합 오케스트레이션.

사용자 UX: 명령 1회 → 한국어 요약 + filled/다음할일.txt + (선택) 팝업.
내부만: .analysis/run_manifest.json (사용자에게 읽으라고 하지 않음).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .cross_form_autofill import (
    BatchAutofillReport,
    batch_autofill_from_pool,
    format_batch_detail_korean,
    format_batch_summary_korean,
)
from .folder_analyzer import (
    FolderAnalysisReport,
    analyze_folder,
    format_folder_summary_korean,
)
from .pipeline_failure_ux import (
    check_deadline_warning,
    classify_download_failure,
    classify_login_wall,
    collect_all_failures,
    collect_input_failures,
    compute_pipeline_exit_code,
    pdf_only_pool_warning,
)
from .user_pipeline_config import load_config, resolve_mail_out_dir, resolve_source_pool

MAIL_ROOT = Path(r"D:\mail")
MAIL_FETCH_SCRIPT = MAIL_ROOT / "scripts" / "fetch_notice_attachments.py"


@dataclass
class PipelineResult:
    ok: bool = False
    notice_folder: str = ""
    source_pool: str = ""
    output_dir: str = ""
    analysis_summary: str = ""
    batch_summary: str = ""
    batch_detail: str = ""
    todo_text: str = ""
    deadline_warning: str = ""
    download_error: str = ""
    failure_lines: list[str] = field(default_factory=list)
    d_attempts: list[dict[str, Any]] = field(default_factory=list)
    confirm_files: list[str] = field(default_factory=list)
    exit_code: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _try_notify_popup(title_line: str) -> None:
    script = Path.home() / ".claude" / "scripts" / "notify_popup.ps1"
    if not script.is_file():
        return
    try:
        subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script), "-Kind", "pipeline",
            ],
            input=title_line,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _open_folder(path: Path) -> None:
    try:
        import os

        os.startfile(str(path))  # type: ignore[attr-defined]
    except OSError:
        pass


def resolve_notice_folder_from_log(out_dir: Path, url: str = "") -> Path | None:
    """_download_log.json 에서 최근 다운로드 공고 폴더를 찾는다."""
    manifest = out_dir / "_download_log.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    results = data.get("results") or []
    if url:
        for r in reversed(results):
            if r.get("detail_url") == url and r.get("status") == "DOWNLOADED":
                sp = r.get("save_path")
                if sp:
                    return Path(sp).parent
    for r in reversed(results):
        if r.get("status") == "DOWNLOADED" and r.get("save_path"):
            return Path(r["save_path"]).parent
    return None


def run_download(
    url: str,
    *,
    out_dir: Path | None = None,
    notify: bool = False,
    open_folder_flag: bool = False,
) -> tuple[Path | None, str]:
    """mail fetch 스크립트로 첨부를 받고 공고 폴더 경로를 반환한다."""
    if not MAIL_FETCH_SCRIPT.is_file():
        raise FileNotFoundError(f"다운로드 스크립트가 없습니다: {MAIL_FETCH_SCRIPT}")
    od = out_dir or resolve_mail_out_dir(None)
    cmd = [sys.executable, str(MAIL_FETCH_SCRIPT), url]
    if notify:
        cmd.append("--notify")
    if open_folder_flag:
        cmd.append("--open")
    cmd.extend(["--out-dir", str(od)])
    proc = subprocess.run(
        cmd,
        cwd=str(MAIL_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    log_results: list[dict[str, Any]] = []
    manifest = od / "_download_log.json"
    if manifest.is_file():
        try:
            log_results = json.loads(manifest.read_text(encoding="utf-8")).get("results") or []
        except (OSError, json.JSONDecodeError):
            pass

    folder = resolve_notice_folder_from_log(od, url)
    if not folder:
        for line in stdout.splitlines():
            if "저장 위치:" in line or "💾" in line:
                part = line.split(":", 1)[-1].strip()
                if part:
                    folder = Path(part)
                    break

    dl_fail = classify_download_failure(
        url,
        log_results,
        stderr=stderr,
        proc_rc=proc.returncode,
        folder_resolved=folder is not None,
    )
    if dl_fail.advices:
        raise RuntimeError(dl_fail.advices[0].message)

    if proc.returncode != 0 and "DOWNLOADED" not in stdout:
        err = (stderr or stdout).strip()
        raise RuntimeError(err or f"다운로드 실패(exit {proc.returncode})")

    if folder:
        return folder, stdout
    return None, stdout


def write_confirm_json_files(
    report: BatchAutofillReport,
    out_dir: Path,
) -> list[Path]:
    """needs_confirm 항목마다 confirm_<양식>.json 을 만든다."""
    written: list[Path] = []
    for item in report.items:
        if not item.ok or not item.needs_confirm:
            continue
        mapping: dict[str, str] = {}
        for entry in item.needs_confirm:
            tgt = entry.get("target_label") or entry.get("normalized") or ""
            cands = [c for c in (entry.get("candidates") or []) if c]
            if tgt and cands and '"' not in tgt and "=" not in tgt:
                mapping[str(tgt)] = str(cands[0])
        if not mapping:
            continue
        stem = Path(item.target).stem
        safe = re.sub(r'[<>:"/\\|?*]', "_", stem)[:80]
        path = out_dir / f"confirm_{safe}.json"
        path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written


def load_confirm_files(out_dir: Path) -> dict[str, str]:
    """filled/confirm_*.json 을 모두 읽어 합친다."""
    merged: dict[str, str] = {}
    for path in sorted(out_dir.glob("confirm_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            for k, v in data.items():
                merged[str(k)] = str(v)
    return merged


def build_todo_text(
    report: BatchAutofillReport,
    *,
    deadline_warning: str = "",
    confirm_files: list[Path] | None = None,
    d_attempts: list[dict[str, Any]] | None = None,
    download_error: str = "",
    failure_lines: list[str] | None = None,
) -> str:
    """비개발자용 다음할일.txt 본문."""
    lines: list[str] = []
    if deadline_warning:
        lines.append(deadline_warning)
    if download_error:
        lines.append(f"[실패] {download_error}")
    for fl in failure_lines or []:
        if fl not in lines:
            lines.append(fl)

    n_ok = report.ok_count
    n_hwp = report.hwp_count
    n_confirm = sum(i.needs_confirm_count for i in report.items)
    lines.append(f"[완료] 양식 {n_ok}개 · HWP {n_hwp}개 · 확인필요 {n_confirm}칸")
    if report.output_dir:
        lines.append(f"[열기] {report.output_dir}")

    cf = confirm_files or []
    for item in report.items:
        if not item.ok:
            continue
        name = Path(item.target).stem
        for nc in item.needs_confirm[:4]:
            tgt = nc.get("target_label") or nc.get("normalized") or ""
            cands = nc.get("candidates") or []
            cand = cands[0] if cands else ""
            cf_match = next((p for p in cf if name in p.stem), None)
            cf_hint = f" (명령 파일: {cf_match.name})" if cf_match else ""
            lines.append(f"[확인 필요] {name} — {tgt}{cf_hint}")
            if cand:
                lines.append(f"         후보: {cand}")
        for um in item.unmatched_targets[:4]:
            tgt = um.get("target_label") or um.get("normalized") or ""
            lines.append(f"[직접 입력] {name} — {tgt}")

    if d_attempts:
        for d in d_attempts:
            lines.append(
                f"[서술 작성] {d.get('form', '')} — "
                f"{'시도함' if d.get('ok') else '건너뜀'}: {d.get('note', '')}")

    if not lines:
        lines.append("[안내] 채울 양식이 없거나 작업이 완료되지 않았습니다.")
    return "\n".join(lines)


def write_run_manifest(
    notice_folder: Path,
    result: PipelineResult,
    analysis: FolderAnalysisReport | None,
    batch: BatchAutofillReport | None,
) -> Path:
    """기계용 run_manifest.json (내부)."""
    out_dir = notice_folder / ".analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "notice_folder": str(notice_folder),
        "source_pool": result.source_pool,
        "output_dir": result.output_dir,
        "deadline_warning": result.deadline_warning,
        "download_error": result.download_error,
        "failure_lines": result.failure_lines,
        "analysis": analysis.as_dict() if analysis else None,
        "batch": {
            "ok_count": batch.ok_count if batch else 0,
            "hwp_count": batch.hwp_count if batch else 0,
            "items": [
                {
                    "target": i.target,
                    "source": i.source,
                    "output": i.output,
                    "hwp_output": i.hwp_output,
                    "ok": i.ok,
                    "transcribed": i.transcribed,
                    "needs_confirm_count": i.needs_confirm_count,
                }
                for i in (batch.items if batch else [])
            ],
        },
        "d_attempts": result.d_attempts,
        "confirm_files": result.confirm_files,
        "exit_code": result.exit_code,
    }
    path = out_dir / "run_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_conditional_bizplan(
    batch: BatchAutofillReport,
    announcement_path: str,
    *,
    use_ai: bool = False,
) -> list[dict[str, Any]]:
    """서술형 미매칭이 있는 양식에만 bizplan 을 시도한다."""
    from .d_trigger import should_run_bizplan_for_target

    attempts: list[dict[str, Any]] = []
    ann_file = announcement_path if announcement_path and Path(announcement_path).exists() else None

    for item in batch.items:
        if not item.ok or not item.output:
            continue
        run, gaps, _fr = should_run_bizplan_for_target(item.target, item.unmatched_targets)
        note = f"서술 잔여 {len(gaps)}칸" if gaps else "서술 잔여 없음"
        entry: dict[str, Any] = {
            "form": Path(item.target).name,
            "ok": False,
            "note": note,
            "gaps": len(gaps),
        }
        if not run:
            attempts.append(entry)
            continue
        try:
            from .bizplan_autopilot import run_bizplan_autopilot
            from .doc_text_extract import extract_text

            out = Path(item.output)
            biz_out = out.with_name(out.stem + "_서술보강.docx")
            ann_text = None
            if ann_file:
                ann_text, _ = extract_text(ann_file)
            rep = run_bizplan_autopilot(
                str(out),
                output_docx=str(biz_out),
                announcement_text=ann_text or None,
                use_ai=use_ai,
                max_loops=1 if not use_ai else 2,
                write_report=False,
            )
            entry["ok"] = bool(rep.output_docx)
            entry["note"] = f"서술 보강 → {Path(rep.output_docx).name}"
        except Exception as exc:  # noqa: BLE001
            entry["note"] = f"서술 보강 실패: {exc}"
        attempts.append(entry)
    return attempts


def run_pipeline(
    *,
    url: str | None = None,
    notice_folder: str | Path | None = None,
    source_pool: str | None = None,
    skip_download: bool = False,
    output_subdir: str | None = None,
    retry_confirm: bool = False,
    run_bizplan: bool = True,
    use_ai_bizplan: bool = False,
    convert_hwp: bool = True,
    notify: bool = False,
    open_folder_flag: bool = False,
    save_defaults: bool = False,
) -> PipelineResult:
    """A→B→C(+D) 파이프라인 본체."""
    result = PipelineResult()
    cfg = load_config()
    out_sub = output_subdir or cfg.get("default_out_subdir") or "filled"

    try:
        pool = resolve_source_pool(source_pool)
    except ValueError as exc:
        inp = collect_input_failures(missing_source_pool=str(exc))
        result.failure_lines = inp.lines()
        result.notes.extend(result.failure_lines)
        result.exit_code = inp.exit_code
        return result
    result.source_pool = pool

    pdf_warn = pdf_only_pool_warning(Path(pool))
    if pdf_warn:
        result.notes.append(pdf_warn)

    if save_defaults and source_pool:
        from .user_pipeline_config import save_config

        save_config({"default_source_pool": str(source_pool).strip()})

    notice_path: Path | None = Path(notice_folder) if notice_folder else None

    if not skip_download and url:
        try:
            folder, _log = run_download(
                url, notify=notify, open_folder_flag=open_folder_flag)
            notice_path = folder
        except Exception as exc:  # noqa: BLE001
            result.download_error = str(exc)
            result.failure_lines = [f"[실패] {result.download_error}"]
            result.exit_code = 2
            result.todo_text = build_todo_text(
                BatchAutofillReport("", pool, ""),
                download_error=result.download_error,
                failure_lines=result.failure_lines,
            )
            return result
    elif not notice_path or not notice_path.is_dir():
        inp = collect_input_failures(
            missing_notice="--url 또는 --notice-folder 가 필요합니다.")
        result.failure_lines = inp.lines()
        result.notes.extend(result.failure_lines)
        result.exit_code = inp.exit_code
        return result

    result.notice_folder = str(notice_path)

    analysis = analyze_folder(notice_path, openai_service=None, save_json=True)
    result.analysis_summary = format_folder_summary_korean(analysis)
    result.deadline_warning = check_deadline_warning(analysis)

    confirmations = None
    out_dir = notice_path / out_sub
    if retry_confirm and out_dir.is_dir():
        confirmations = load_confirm_files(out_dir) or None

    batch = batch_autofill_from_pool(
        notice_path,
        pool,
        output_subdir=out_sub,
        confirmations=confirmations,
        convert_hwp=convert_hwp,
    )
    result.output_dir = batch.output_dir
    result.batch_summary = format_batch_summary_korean(batch)
    result.batch_detail = format_batch_detail_korean(batch)

    confirm_paths = write_confirm_json_files(batch, Path(batch.output_dir))
    result.confirm_files = [str(p) for p in confirm_paths]

    if run_bizplan and batch.items:
        ann_path = analysis.announcement_path or ""
        result.d_attempts = run_conditional_bizplan(
            batch, ann_path, use_ai=use_ai_bizplan)

    failure_report = collect_all_failures(
        analysis=analysis,
        batch=batch,
        pool=Path(pool),
        d_attempts=result.d_attempts,
        extra_notes=result.notes,
    )
    result.failure_lines = failure_report.lines()
    if result.download_error:
        result.failure_lines.insert(0, f"[실패] {result.download_error}")

    result.todo_text = build_todo_text(
        batch,
        deadline_warning=result.deadline_warning,
        confirm_files=confirm_paths,
        d_attempts=result.d_attempts,
        download_error=result.download_error,
        failure_lines=result.failure_lines,
    )

    todo_path = Path(batch.output_dir) / "다음할일.txt"
    todo_path.parent.mkdir(parents=True, exist_ok=True)
    todo_path.write_text(result.todo_text, encoding="utf-8")

    write_run_manifest(notice_path, result, analysis, batch)

    result.ok = batch.ok_count > 0 or bool(retry_confirm)
    result.exit_code = compute_pipeline_exit_code(
        failure_report,
        batch_ok_count=batch.ok_count,
        has_download_error=bool(result.download_error),
    )

    if notify:
        headline = result.batch_summary.split("\n")[0] if result.batch_summary else "파이프라인 완료"
        if result.deadline_warning:
            headline = result.deadline_warning + " " + headline
        _try_notify_popup(headline)

    if open_folder_flag and batch.output_dir:
        _open_folder(Path(batch.output_dir))

    return result


def format_pipeline_summary_korean(result: PipelineResult) -> str:
    """통합 한국어 요약(채팅용)."""
    parts: list[str] = []
    if result.deadline_warning:
        parts.append(result.deadline_warning)
    if result.download_error:
        parts.append(result.download_error)
    if result.failure_lines:
        parts.append("")
        parts.append("── 주의·실패 안내 ──")
        parts.extend(result.failure_lines)
    if result.notice_folder:
        parts.append(f"📁 {Path(result.notice_folder).name}")
    if result.analysis_summary:
        parts.append(result.analysis_summary)
    if result.batch_summary:
        parts.append("")
        parts.append("── 채움 결과 ──")
        parts.append(result.batch_summary)
    if result.batch_detail:
        parts.append("")
        parts.append(result.batch_detail)
    if result.d_attempts:
        n = sum(1 for d in result.d_attempts if d.get("ok"))
        parts.append(f"\n서술 보강: {n}/{len(result.d_attempts)}건 시도")
    if result.todo_text:
        parts.append("")
        parts.append(f"다음할일: {Path(result.output_dir) / '다음할일.txt'}")
    return "\n".join(parts).strip()
