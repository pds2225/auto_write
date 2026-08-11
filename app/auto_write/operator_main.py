from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from core.docx.services.cross_form_autofill import autofill_from_source
from core.docx.services.hwp_docx_convert import docx_to_hwp, hwp_to_docx

from .document_ingest import is_supported_template_file, template_upload_detail
from .domains.domain_router import DomainRouter
from .main import app, openai_service, project_service, settings, storage, templates
from .services.docx_edit_service import DocxEditService
from .services.git_sync_service import GitSyncError, GitSyncService
from .services.lrule_console_service import LRuleConsoleService
from .services.system_map_service import SystemMapService
from .services.workflow_monitor import WorkflowMonitor
from .utils import read_json, sanitize_user_filename


REPO_ROOT = Path(__file__).resolve().parents[2]
_CROSS_FORM_SOURCE_EXTS = {".docx", ".hwp", ".hwpx"}
git_sync = GitSyncService(REPO_ROOT)
lrule_console = LRuleConsoleService(REPO_ROOT)
system_map = SystemMapService(REPO_ROOT, lrule_console)
workflow_monitor = WorkflowMonitor()
docx_editor = DocxEditService()
domain_router = DomainRouter(settings)

# Replace only the legacy GET / page. Existing API/template/project routes remain available.
for _route in list(app.router.routes):
    if getattr(_route, "path", None) == "/" and "GET" in (getattr(_route, "methods", set()) or set()):
        app.router.routes.remove(_route)


def _ctx(request: Request, **extra) -> dict:
    git = git_sync.snapshot(fetch=False).as_dict()
    return {
        "request": request,
        "settings": settings,
        "ai_status_text": openai_service.status_text,
        "ai_provider": openai_service.provider,
        "git": git,
        **extra,
    }


def _project_output_dir(project_id: str) -> Path:
    return storage.project_dir(project_id) / "output"


def _result_docx(project_id: str) -> Path | None:
    output_dir = _project_output_dir(project_id)
    edited = sorted(
        output_dir.glob("output_user_edited*.docx"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    for path in edited:
        if path.is_file():
            return path
    preferred = [output_dir / "output.docx"]
    for path in preferred:
        if path.is_file():
            return path
    results_dir = storage.results_dir(project_id)
    if results_dir.exists():
        for path in sorted(results_dir.glob("*.docx")):
            if path.is_file():
                return path
    return None


def _source_override_path(project_id: str) -> Path:
    return _project_output_dir(project_id) / "source_overrides.json"


def _load_source_overrides(project_id: str) -> list[dict]:
    path = _source_override_path(project_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("sources", []) if isinstance(data, dict) else []
    except Exception:
        return []


def _reference_rows(project_id: str) -> list[dict]:
    rows: list[dict] = []
    input_path = storage.project_dir(project_id) / "project_input.json"
    if input_path.exists():
        try:
            data = read_json(input_path)
            for ref in data.get("references", []):
                name = str(ref.get("file_name", "")).strip()
                if name:
                    rows.append({"file": name, "page": "", "note": "페이지를 확인해 입력하세요."})
        except Exception:
            pass
    rows.extend(_load_source_overrides(project_id))
    seen = set()
    unique = []
    for row in rows:
        key = (str(row.get("file", "")), str(row.get("page", "")), str(row.get("note", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _applicable_rule_codes(domain_value: str) -> list[str]:
    try:
        lessons = lrule_console.load().get("lessons", [])
    except Exception:
        return []
    codes = []
    for rule in lessons:
        domain = str(rule.get("domain", "all"))
        if domain in {"all", domain_value}:
            codes.append(lrule_console.rule_code(rule))
    return codes


def _reference_priority(name: str) -> tuple[int, str]:
    """Prefer completed-plan-looking files before generic document references."""
    lowered = name.lower()
    score = 0
    for token in ("사업계획서", "계획서", "제출본", "완성", "기존", "previous", "plan"):
        if token in lowered:
            score += 3
    for token in ("공고", "양식", "서식", "신청서", "notice", "form"):
        if token in lowered:
            score -= 2
    return (-score, lowered)


def _prefill_template_from_references(
    template_name: str,
    template_bytes: bytes,
    refs: list[tuple[str, bytes]],
) -> tuple[str, bytes, dict]:
    """Use the deterministic cross-form engine before AI generation when safe.

    The target must currently be DOCX. Source references may be DOCX/HWP/HWPX;
    HWP-family source conversion is delegated to the existing cross-form engine.
    We try candidate source documents in a deterministic priority order and only
    promote a produced target when the engine reports real transcriptions.
    """
    stats = {
        "attempted": 0,
        "applied_sources": [],
        "transcribed": 0,
        "needs_confirm": 0,
        "errors": [],
        "mode": "bizplan",
        "reason": "",
    }
    if Path(template_name).suffix.lower() != ".docx":
        stats["reason"] = "cross-form 자동전사는 현재 DOCX 타깃에서만 선행 실행"
        return template_name, template_bytes, stats

    candidates = [
        (name, content)
        for name, content in refs
        if Path(name).suffix.lower() in _CROSS_FORM_SOURCE_EXTS and content
    ]
    if not candidates:
        stats["reason"] = "기존 문서형 참고자료 없음"
        return template_name, template_bytes, stats

    candidates.sort(key=lambda item: _reference_priority(item[0]))
    work_dir = Path(tempfile.mkdtemp(prefix="auto_write_cross_form_"))
    current_target = work_dir / "target_0.docx"
    current_target.write_bytes(template_bytes)

    for index, (source_name, source_bytes) in enumerate(candidates, start=1):
        source_suffix = Path(source_name).suffix.lower()
        source_path = work_dir / f"source_{index}{source_suffix}"
        source_path.write_bytes(source_bytes)
        output_path = work_dir / f"target_{index}.docx"
        stats["attempted"] += 1
        try:
            report = autofill_from_source(source_path, current_target, output_path, use_ai=False)
        except Exception as exc:
            stats["errors"].append(f"{source_name}: {type(exc).__name__}: {exc}"[:500])
            continue

        transcribed = int(getattr(report, "transcribed", 0) or 0)
        needs_confirm = len(getattr(report, "needs_confirm", []) or [])
        stats["needs_confirm"] += needs_confirm
        if bool(getattr(report, "ok", False)) and transcribed > 0 and output_path.is_file():
            current_target = output_path
            stats["transcribed"] += transcribed
            stats["applied_sources"].append(source_name)

    if stats["transcribed"] > 0:
        stats["mode"] = "cross_form_then_bizplan"
        stats["reason"] = "기존 자료의 확정 사실을 새 DOCX 양식에 먼저 전사한 뒤 나머지 작성 실행"
        return template_name, current_target.read_bytes(), stats

    stats["reason"] = "보수적 cross-form 매칭에서 자동전사 가능한 확정 항목 없음"
    return template_name, template_bytes, stats


async def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    name = sanitize_user_filename(upload.filename or "upload.bin")
    return name, await upload.read()


async def _run_document_generation(
    *,
    template_file: UploadFile,
    reference_files: list[UploadFile],
    project_title: str,
    organization_name: str,
    instruction: str,
    run_kind: str,
) -> tuple[str, str]:
    run_id = workflow_monitor.start_run(run_kind, "문서 작성" if run_kind == "write" else "문서 수정·보완")
    try:
        with workflow_monitor.step(run_id, "upload", "입력 파일 확인", "Web"):
            template_name, template_bytes = await _read_upload(template_file)
            if not is_supported_template_file(template_name):
                raise ValueError(template_upload_detail())
            refs: list[tuple[str, bytes]] = []
            for upload in reference_files:
                if upload and upload.filename:
                    ref_name, ref_bytes = await _read_upload(upload)
                    if ref_bytes:
                        refs.append((ref_name, ref_bytes))

        cross_form_stats = {
            "mode": "bizplan",
            "attempted": 0,
            "transcribed": 0,
            "applied_sources": [],
            "needs_confirm": 0,
            "errors": [],
            "reason": "수정·보완 경로는 기존 문서를 직접 재작성 입력으로 사용",
        }
        if run_kind == "write":
            workflow_monitor.start_step(
                run_id,
                "cross_form",
                "기존 자료 자동전사 검사",
                "core.docx cross_form_autofill",
            )
            try:
                template_name, template_bytes, cross_form_stats = _prefill_template_from_references(
                    template_name,
                    template_bytes,
                    refs,
                )
            except Exception as exc:
                workflow_monitor.fail_step(run_id, "cross_form", f"{type(exc).__name__}: {exc}")
                cross_form_stats["errors"] = [f"{type(exc).__name__}: {exc}"[:500]]
            else:
                workflow_monitor.finish_step(run_id, "cross_form", cross_form_stats)

        with workflow_monitor.step(run_id, "analyze", "양식 분석", "ProjectService"):
            profile = project_service.analyze_uploaded_template(template_name, template_bytes)

        with workflow_monitor.step(run_id, "route", "업무 분류", "DomainRouter"):
            route_text = " ".join([instruction, project_title, organization_name] + [name for name, _ in refs])
            domain_ctx = domain_router.resolve(
                text=route_text,
                filename=template_name,
                document_type="business_plan",
            )
            domain_value = domain_ctx.domain.value

        with workflow_monitor.step(
            run_id,
            "rules",
            "L 규칙 참조",
            "LRule Registry",
            {
                "domain": domain_value,
                "workflow_route": cross_form_stats.get("mode", "bizplan"),
                "rule_count": len(_applicable_rule_codes(domain_value)),
            },
        ):
            rule_codes = _applicable_rule_codes(domain_value)

        with workflow_monitor.step(run_id, "project", "작업공간 생성", "ProjectService"):
            project_id = project_service.create_project(profile.template_id, project_title or f"웹-{run_kind}")
            answers = {
                "user_brief": instruction,
                "user_notes": instruction,
            }
            project_service.save_project_form(
                project_id=project_id,
                answers=answers,
                project_title=project_title,
                organization_name=organization_name,
                evidence_topics="",
                reference_files=refs,
                improve_partial=True,
                psst_only=True,
                disable_images=True,
            )

        with workflow_monitor.step(
            run_id,
            "generate",
            "기존 엔진으로 문서 생성",
            "ProjectService.generate",
            {
                "workflow_route": cross_form_stats.get("mode", "bizplan"),
                "cross_form_transcribed": cross_form_stats.get("transcribed", 0),
                "rule_codes": rule_codes[:40],
                "rule_total": len(rule_codes),
            },
        ):
            project_service.generate(project_id)

        result = _result_docx(project_id)
        if not result or not result.is_file() or result.stat().st_size <= 0:
            raise RuntimeError("생성 엔진이 비어 있지 않은 DOCX 결과를 만들지 못했습니다.")

        workflow_monitor.finish_run(
            run_id,
            {
                "project_id": project_id,
                "result": str(result),
                "result_size": result.stat().st_size,
                "workflow_route": cross_form_stats.get("mode", "bizplan"),
                "cross_form": cross_form_stats,
            },
        )
        return project_id, run_id
    except Exception as exc:
        workflow_monitor.fail_run(run_id, f"{type(exc).__name__}: {exc}")
        raise


@app.get("/", response_class=HTMLResponse)
@app.get("/console", response_class=HTMLResponse)
async def operator_home(request: Request):
    architecture = system_map.overview()
    rule_summary = lrule_console.summary()
    runs = workflow_monitor.list_runs(8)
    return templates.TemplateResponse(
        request,
        "operator_home.html",
        _ctx(
            request,
            architecture=architecture,
            rule_summary=rule_summary,
            recent_runs=runs,
            error=request.query_params.get("error", ""),
        ),
    )


@app.post("/console/documents/write")
async def operator_write_document(
    template_file: UploadFile = File(...),
    reference_files: list[UploadFile] | None = File(default=None),
    project_title: str = Form(default=""),
    organization_name: str = Form(default=""),
    instruction: str = Form(default=""),
):
    try:
        project_id, run_id = await _run_document_generation(
            template_file=template_file,
            reference_files=reference_files or [],
            project_title=project_title,
            organization_name=organization_name,
            instruction=instruction,
            run_kind="write",
        )
    except Exception as exc:
        return RedirectResponse(url=f"/console?error={quote(str(exc)[:500], safe='')}", status_code=303)
    return RedirectResponse(url=f"/console/results/{project_id}?run_id={run_id}", status_code=303)


@app.post("/console/documents/revise")
async def operator_revise_document(
    document_file: UploadFile = File(...),
    instruction: str = Form(...),
    project_title: str = Form(default=""),
):
    name, content = await _read_upload(document_file)
    from starlette.datastructures import UploadFile as StarletteUploadFile
    import io

    template_upload = StarletteUploadFile(filename=name, file=io.BytesIO(content))
    reference_upload = StarletteUploadFile(filename=name, file=io.BytesIO(content))
    try:
        project_id, run_id = await _run_document_generation(
            template_file=template_upload,
            reference_files=[reference_upload],
            project_title=project_title or f"{Path(name).stem} 수정본",
            organization_name="",
            instruction=instruction,
            run_kind="revise",
        )
    except Exception as exc:
        return RedirectResponse(url=f"/console?error={quote(str(exc)[:500], safe='')}", status_code=303)
    return RedirectResponse(url=f"/console/results/{project_id}?run_id={run_id}", status_code=303)


@app.post("/console/documents/convert")
async def operator_convert_document(
    file: UploadFile = File(...),
    target: str = Form(...),
):
    run_id = workflow_monitor.start_run("convert", "문서 변환")
    try:
        with workflow_monitor.step(run_id, "upload", "변환 파일 확인", "Web"):
            name, content = await _read_upload(file)
            suffix = Path(name).suffix.lower()
            if suffix not in {".hwp", ".hwpx", ".docx"}:
                raise ValueError("HWP/HWPX/DOCX만 지원합니다.")
            if target not in {"docx", "hwp", "hwpx"}:
                raise ValueError("지원하지 않는 목표 형식입니다.")
            work_dir = Path(tempfile.mkdtemp(prefix="auto_write_convert_"))
            source = work_dir / name
            source.write_bytes(content)
            output = work_dir / f"{source.stem}.{target}"

        with workflow_monitor.step(run_id, "convert", "기존 변환 서비스 실행", "core.docx hwp_docx_convert"):
            if suffix in {".hwp", ".hwpx"} and target == "docx":
                report = hwp_to_docx(source, output)
            elif suffix == ".docx" and target in {"hwp", "hwpx"}:
                report = docx_to_hwp(source, output)
            else:
                raise ValueError(f"{suffix} → .{target} 변환 조합은 지원하지 않습니다.")
            if not report.ok or not output.is_file() or output.stat().st_size <= 0:
                raise RuntimeError(" / ".join(report.notes) or "변환에 실패했습니다.")

        workflow_monitor.finish_run(run_id, {"output": str(output), "method": report.method})
        return FileResponse(path=str(output), filename=output.name)
    except Exception as exc:
        workflow_monitor.fail_run(run_id, f"{type(exc).__name__}: {exc}")
        return RedirectResponse(url=f"/console?error={quote(str(exc)[:500], safe='')}", status_code=303)


@app.get("/console/results/{project_id}", response_class=HTMLResponse)
async def operator_result(request: Request, project_id: str):
    result = _result_docx(project_id)
    if not result:
        raise HTTPException(status_code=404, detail="결과 DOCX를 찾을 수 없습니다.")
    lock_path = _project_output_dir(project_id) / "user_locks.json"
    blocks = docx_editor.load_blocks(result)
    locks = docx_editor.load_locks(lock_path)
    for block in blocks:
        block["locked"] = block["id"] in locks
    run_id = request.query_params.get("run_id", "")
    return templates.TemplateResponse(
        request,
        "operator_result.html",
        _ctx(
            request,
            project_id=project_id,
            result_name=result.name,
            result_size=result.stat().st_size,
            blocks=blocks,
            sources=_reference_rows(project_id),
            run=workflow_monitor.get_run(run_id) if run_id else None,
            message=request.query_params.get("message", ""),
        ),
    )


@app.get("/console/results/{project_id}/download/{name}")
async def operator_download(project_id: str, name: str):
    safe = Path(name).name
    candidates = [
        _project_output_dir(project_id) / safe,
        storage.results_dir(project_id) / safe,
    ]
    for path in candidates:
        if path.is_file():
            return FileResponse(path=str(path), filename=path.name)
    raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")


@app.post("/console/results/{project_id}/edit")
async def operator_edit_result(request: Request, project_id: str):
    source = _result_docx(project_id)
    if not source:
        raise HTTPException(status_code=404, detail="수정할 DOCX를 찾을 수 없습니다.")
    form = await request.form()
    edits = {}
    for key, value in form.items():
        if str(key).startswith("block__"):
            edits[str(key)[7:]] = str(value)
    output_dir = _project_output_dir(project_id)
    version = 1
    output = output_dir / "output_user_edited.docx"
    while output.exists() and source.resolve() == output.resolve():
        version += 1
        output = output_dir / f"output_user_edited_v{version}.docx"
    lock_path = output_dir / "user_locks.json"
    report = docx_editor.apply_edits(source, edits, output, lock_path)
    message = quote(f"사용자 수정 {report['applied_count']}건 저장 및 USER_LOCKED 처리", safe="")
    return RedirectResponse(url=f"/console/results/{project_id}?message={message}", status_code=303)


@app.post("/console/results/{project_id}/sources")
async def operator_add_source(
    project_id: str,
    source_file: str = Form(...),
    source_page: str = Form(...),
    source_note: str = Form(default=""),
):
    path = _source_override_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = _load_source_overrides(project_id)
    rows.append(
        {
            "file": Path(source_file).name,
            "page": source_page.strip(),
            "note": source_note.strip(),
        }
    )
    path.write_text(json.dumps({"sources": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return RedirectResponse(url=f"/console/results/{project_id}", status_code=303)


@app.get("/console/lrules", response_class=HTMLResponse)
async def operator_lrules(
    request: Request,
    q: str = "",
    domain: str = "",
    category: str = "",
    impact: str = "",
):
    summary = lrule_console.summary()
    rules = lrule_console.list_rules(query=q, domain=domain, category=category, impact=impact)
    return templates.TemplateResponse(
        request,
        "operator_rules.html",
        _ctx(
            request,
            rules=rules,
            summary=summary,
            filters={"q": q, "domain": domain, "category": category, "impact": impact},
        ),
    )


@app.get("/console/lrules/{code}", response_class=HTMLResponse)
async def operator_lrule_detail(request: Request, code: str):
    try:
        rule = lrule_console.get_rule(code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    history = git_sync.rule_history(code.upper(), str(lrule_console.REGISTRY_RELATIVE).replace("\\", "/"))
    return templates.TemplateResponse(
        request,
        "operator_rule_detail.html",
        _ctx(
            request,
            rule=rule,
            history=history,
            message=request.query_params.get("message", ""),
            error=request.query_params.get("error", ""),
        ),
    )


@app.post("/console/lrules/{code}")
async def operator_lrule_update(
    code: str,
    base_remote_sha: str = Form(...),
    summary: str = Form(...),
    mechanizable: str = Form(default=""),
    category: str = Form(default=""),
    guard_ref: str = Form(default=""),
    gap_desc: str = Form(default=""),
    impact: str = Form(default=""),
    domain: str = Form(default=""),
):
    before_text = ""
    try:
        git_sync.assert_write_base(base_remote_sha)
        _, before_text = lrule_console.update_rule(
            code,
            {
                "summary": summary,
                "mechanizable": mechanizable,
                "category": category,
                "guard_ref": guard_ref,
                "gap_desc": gap_desc,
                "impact": impact,
                "domain": domain,
            },
        )
        test = lrule_console.run_registry_tests()
        if not test.ok:
            lrule_console.restore_text(before_text)
            raise GitSyncError(f"관련 테스트 실패로 registry를 원복했습니다.\n{test.output[-1800:]}")
        commit = git_sync.commit_and_push(
            [lrule_console.REGISTRY_RELATIVE],
            message=f"web: update {code.upper()} rule",
            expected_base_remote_sha=base_remote_sha,
        )
        msg = f"{code.upper()} 변경을 {commit['branch']} / {commit['commit_sha'][:8]}에 반영했습니다."
        if commit.get("pr_url"):
            msg += f" PR: {commit['pr_url']}"
        elif commit.get("pr_error"):
            msg += " 브랜치 push는 완료됐지만 PR 자동 생성은 실패했습니다."
        return RedirectResponse(
            url=f"/console/lrules/{code.upper()}?message={quote(msg, safe='')}",
            status_code=303,
        )
    except Exception as exc:
        if before_text:
            try:
                if git_sync.current_branch() == git_sync.base_branch:
                    lrule_console.restore_text(before_text)
            except Exception:
                pass
        return RedirectResponse(
            url=f"/console/lrules/{code.upper()}?error={quote(str(exc)[:1800], safe='')}",
            status_code=303,
        )


@app.post("/console/lrules/{code}/rollback")
async def operator_lrule_rollback(
    code: str,
    commit_sha: str = Form(...),
    base_remote_sha: str = Form(...),
):
    before_text = ""
    try:
        git_sync.assert_write_base(base_remote_sha)
        old_text = git_sync.show_file(f"{commit_sha}^", str(lrule_console.REGISTRY_RELATIVE).replace("\\", "/"))
        _, before_text = lrule_console.restore_rule_from_registry_text(code, old_text)
        test = lrule_console.run_registry_tests()
        if not test.ok:
            lrule_console.restore_text(before_text)
            raise GitSyncError(f"롤백 테스트 실패로 원복했습니다.\n{test.output[-1800:]}")
        commit = git_sync.commit_and_push(
            [lrule_console.REGISTRY_RELATIVE],
            message=f"web: rollback {code.upper()} from {commit_sha[:8]}",
            expected_base_remote_sha=base_remote_sha,
        )
        msg = f"{code.upper()} 규칙 롤백을 {commit['branch']}에 반영했습니다."
        return RedirectResponse(
            url=f"/console/lrules/{code.upper()}?message={quote(msg, safe='')}",
            status_code=303,
        )
    except Exception as exc:
        if before_text:
            try:
                if git_sync.current_branch() == git_sync.base_branch:
                    lrule_console.restore_text(before_text)
            except Exception:
                pass
        return RedirectResponse(
            url=f"/console/lrules/{code.upper()}?error={quote(str(exc)[:1800], safe='')}",
            status_code=303,
        )


@app.get("/console/architecture", response_class=HTMLResponse)
async def operator_architecture(request: Request):
    overview = system_map.overview()
    return templates.TemplateResponse(
        request,
        "operator_architecture.html",
        _ctx(request, overview=overview),
    )


@app.get("/console/workflows", response_class=HTMLResponse)
async def operator_workflows(request: Request):
    workflows = system_map.workflows()
    return templates.TemplateResponse(
        request,
        "operator_workflows.html",
        _ctx(request, workflows=workflows),
    )


@app.get("/console/monitor", response_class=HTMLResponse)
async def operator_monitor(request: Request):
    return templates.TemplateResponse(
        request,
        "operator_monitor.html",
        _ctx(request, runs=workflow_monitor.list_runs(30)),
    )


@app.get("/api/operator/runs")
async def operator_runs_api():
    return {"runs": workflow_monitor.list_runs(30)}


@app.get("/console/settings", response_class=HTMLResponse)
async def operator_settings(request: Request):
    return templates.TemplateResponse(
        request,
        "operator_settings.html",
        _ctx(
            request,
            rule_summary=lrule_console.summary(),
            architecture=system_map.overview(),
            message=request.query_params.get("message", ""),
            error=request.query_params.get("error", ""),
        ),
    )


@app.post("/console/git/sync")
async def operator_git_sync():
    try:
        snapshot = git_sync.sync_from_remote()
        message = f"GitHub 동기화 완료: {snapshot.status} / {snapshot.local_sha[:8]}"
        return RedirectResponse(url=f"/console/settings?message={quote(message, safe='')}", status_code=303)
    except Exception as exc:
        return RedirectResponse(url=f"/console/settings?error={quote(str(exc)[:1200], safe='')}", status_code=303)
