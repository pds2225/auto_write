from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from core.docx.services.cross_form_autofill import autofill_from_source, extract_source_fields
from core.docx.services.hwp_docx_convert import docx_to_hwp, hwp_to_docx

from .access_gate import git_writes_allowed
from .document_ingest import is_supported_template_file, template_upload_detail
from .domains.domain_router import DomainRouter
from .main import app, openai_service, project_service, settings, storage, templates
from .services.docx_edit_service import DocxEditService
from .services.git_sync_service import GitSyncError, GitSyncService
from .services.lrule_console_service import LRuleConsoleService
from .services.system_map_service import SystemMapService
from .services.workflow_monitor import WorkflowMonitor
from .services import module_workspace
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


def _git_write_blocked(target: str):
    if git_writes_allowed():
        return None
    message = quote("Render에서는 L규칙과 Git 변경이 꺼져 있습니다.", safe="")
    return RedirectResponse(url=f"{target}?error={message}", status_code=303)


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


def _form_checked(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def _hangul_origin(project_id: str) -> bool:
    """HWP/HWPX 프로젝트는 다운로드도 한글 산출을 먼저 보여 준다."""
    snapshot = storage.project_dir(project_id) / "template_snapshot.json"
    if not snapshot.is_file():
        return False
    try:
        data = json.loads(snapshot.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    native = data.get("native_source") if isinstance(data.get("native_source"), dict) else {}
    name = str(data.get("template_name") or "").lower()
    if data.get("source_hwpx") or name.endswith(".hwpx"):
        return True
    if name.endswith(".hwp") and not native.get("hwp_docx_opt_in"):
        return True
    return False


def _preferred_result(project_id: str) -> Path | None:
    if _hangul_origin(project_id):
        return _result_hangul(project_id) or _result_docx(project_id)
    return _result_docx(project_id) or _result_hangul(project_id)


def _result_hangul(project_id: str) -> Path | None:
    """사용자 산출 한글(HWPX/HWP). 편집기용 DOCX 와 별개."""
    output_dir = _project_output_dir(project_id)
    for name in ("output.hwpx", "output.hwp"):
        path = output_dir / name
        if path.is_file() and path.stat().st_size > 0:
            return path
    results_dir = storage.results_dir(project_id)
    if results_dir.exists():
        for path in sorted(results_dir.glob("*.hwpx")) + sorted(results_dir.glob("*.hwp")):
            if path.is_file() and path.stat().st_size > 0:
                return path
    return None


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


def _hwpx_identity_from_references(
    refs: list[tuple[str, bytes]], organization_name: str = ""
) -> dict[str, str]:
    """Build direct-fill labels from supplied DOCX facts only.

    The target HWPX is never converted. Company facts keep numeric values
    (사업자등록번호·설립일) that extract_source_fields drops. 팀명 is captured
    before the 기업명 synonym cluster. Other source labels (서명 등) stay, so
    protected cells still record UNFILLED instead of being dropped. HWP/HWPX
    references stay provenance only and are not guessed into fields.
    """
    from .services.company_identity import company_profile_identity, identity_from_reference_path

    identity = company_profile_identity(
        {"name": organization_name} if organization_name.strip() else {}
    )
    for name, content in refs:
        if Path(name).suffix.lower() != ".docx" or not content:
            continue
        with tempfile.TemporaryDirectory(prefix="auto_write_hwpx_source_") as work_dir:
            source = Path(work_dir) / Path(name).name
            try:
                source.write_bytes(content)
                fields = identity_from_reference_path(source)
                broad = extract_source_fields(source)
            except Exception:
                continue
        for label, value in fields.items():
            if str(value).strip():
                identity.setdefault(str(label), str(value))
        # 기업 화이트리스트에 없는 라벨(서명 등)은 넓은 추출을 유지한다.
        # 숫자 사실값은 identity_from_reference_path 가 이미 넣었으므로 덮지 않는다.
        for label, value in broad.items():
            if str(value).strip():
                identity.setdefault(str(label), str(value))
    return identity


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
    allow_docx_for_hwp: bool = False,
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
        template_suffix = Path(template_name).suffix.lower()
        is_hangul_upload = template_suffix in {".hwp", ".hwpx"}
        if is_hangul_upload and not allow_docx_for_hwp:
            cross_form_stats["mode"] = "hwpx_direct_fill"
            cross_form_stats["reason"] = (
                "HWP/HWPX 원본을 source of truth로 유지하고 기존 direct-fill을 사용"
            )
        skip_cross_form = is_hangul_upload and not allow_docx_for_hwp
        if run_kind == "write" and not skip_cross_form:
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
            profile = project_service.analyze_uploaded_template(
                template_name,
                template_bytes,
                allow_docx_for_hwp=allow_docx_for_hwp,
            )
        hangul_direct = bool(profile.source_hwpx)
        if hangul_direct:
            cross_form_stats["mode"] = "hwpx_direct_fill"
            cross_form_stats["reason"] = (
                "HWP/HWPX 원본을 HWPX로 고정하고 기존 direct-fill을 사용"
            )
        elif allow_docx_for_hwp and template_suffix == ".hwp":
            cross_form_stats["mode"] = "hwp_docx_opt_in"
            cross_form_stats["reason"] = "사용자가 HWP 양식의 DOCX 진행을 선택"

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
                hwpx_identity=(
                    _hwpx_identity_from_references(refs, organization_name)
                    if hangul_direct
                    else None
                ),
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

        result = _preferred_result(project_id)
        hangul = _result_hangul(project_id)
        if (
            (not result or not result.is_file() or result.stat().st_size <= 0)
            and (not hangul or not hangul.is_file() or hangul.stat().st_size <= 0)
        ):
            raise RuntimeError("생성 엔진이 비어 있지 않은 DOCX/HWPX 산출물을 만들지 못했습니다.")
        user_facing = hangul if hangul is not None else result

        workflow_monitor.finish_run(
            run_id,
            {
                "project_id": project_id,
                "result": str(user_facing),
                "result_size": user_facing.stat().st_size,
                "result_hangul": str(hangul) if hangul else "",
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
    workspace_id = request.query_params.get("workspace_id", "")
    workspace = None
    if workspace_id:
        try:
            workspace = module_workspace.get(workspace_id)
        except (ValueError, FileNotFoundError, KeyError):
            workspace = None
    return templates.TemplateResponse(
        request,
        "operator_home.html",
        _ctx(
            request,
            architecture=architecture,
            rule_summary=rule_summary,
            recent_runs=runs,
            workspace=workspace,
            error=request.query_params.get("error", ""),
        ),
    )




def _aw009_error(message: str, workspace_id: str = "") -> RedirectResponse:
    target = "/console"
    if workspace_id:
        target += f"?workspace_id={quote(workspace_id, safe='')}&error={quote(message[:500], safe='')}"
    else:
        target += f"?error={quote(message[:500], safe='')}"
    return RedirectResponse(url=target, status_code=303)


@app.post("/console/modules/start")
async def module_start(
    template_file: UploadFile = File(...),
    announcement_file: UploadFile | None = File(default=None),
    reference_files: list[UploadFile] | None = File(default=None),
    combined: str = Form(default=""),
    role_confirmed: str = Form(default=""),
    toc_override: str = Form(default=""),
):
    """Store sources and preview the form TOC/modules. Absolutely no generation here."""
    try:
        template = await _read_upload(template_file)
        announcement = (await _read_upload(announcement_file)) if announcement_file and announcement_file.filename else None
        refs = [await _read_upload(item) for item in (reference_files or []) if item.filename]
        state = module_workspace.start(
            announcement, template, refs,
            combined=_form_checked(combined),
            roles_confirmed=_form_checked(role_confirmed),
            toc_override=toc_override,
        )
        return RedirectResponse(url=f"/console?workspace_id={state['id']}", status_code=303)
    except Exception as exc:
        return _aw009_error(f"{type(exc).__name__}: {exc}")


@app.post("/console/modules/plan")
async def module_compose(request: Request):
    """Create a visible, non-executing plan from exact selected block IDs."""
    form = await request.form()
    wid = str(form.get("workspace_id", ""))
    try:
        module_workspace.plan(
            wid,
            str(form.get("section_id", "")),
            [str(x) for x in form.getlist("material_ids")],
            str(form.get("instruction", "")),
        )
        return RedirectResponse(url=f"/console?workspace_id={wid}", status_code=303)
    except Exception as exc:
        return _aw009_error(f"{type(exc).__name__}: {exc}", wid)


def _aw009_section_question(profile, section_title: str):
    """Never silently fill a different section on an uncertain heading match."""
    from difflib import SequenceMatcher
    import re
    def normalize(text):
        return re.sub(r"[^가-힣a-z0-9]+", "", str(text).lower())
    target = normalize(section_title)
    candidates = []
    for question in profile.questions:
        if str(question.target.get("kind", "")) != "section":
            continue
        name = normalize(question.label)
        if not name:
            continue
        score = SequenceMatcher(None, target, name).ratio()
        if target == name:
            score = 1.0
        elif min(len(target), len(name)) >= 5 and (target in name or name in target):
            score = max(score, 0.9)
        candidates.append((score, question))
    candidates.sort(key=lambda row: row[0], reverse=True)
    if not candidates or candidates[0][0] < 0.72:
        raise ValueError("현재 양식 대목차와 엔진 question_id를 안전하게 매칭할 수 없습니다. 오매칭 방지를 위해 작성 차단.")
    if len(candidates) > 1 and candidates[1][0] >= candidates[0][0] - 0.03:
        raise ValueError("대목차에 대응하는 엔진 대상이 2개 이상입니다. 임의 선택을 금지합니다.")
    return candidates[0][1]


def _aw009_execute_approved_part(state: dict) -> dict:
    """Use only the pre-existing section-scoped drafting engine, never generate() for whole document."""
    folder = module_workspace._base(state["id"])
    source = state["template_file"]
    source_name = str(source["filename"])
    suffix = Path(source_name).suffix.lower()
    if suffix != ".docx":
        raise ValueError(
            "HWP/HWPX 원본의 대목차 한정 채움 검증 게이트가 없어 실행하지 않았습니다. "
            "DOCX 파트 작성과 HWPX 실문서 증거를 분리 검증해야 합니다."
        )
    template_bytes = (folder / source["stored"]).read_bytes()
    if not template_bytes or __import__("hashlib").sha256(template_bytes).hexdigest() != source["sha256"]:
        raise ValueError("원본 양식 해시가 일치하지 않습니다.")
    section_id = state["plan"]["target_section"]
    section_title = next(item["title"] for item in state["toc"] if item["id"] == section_id)
    profile = project_service.analyze_uploaded_template(source_name, template_bytes)
    question = _aw009_section_question(profile, section_title)
    selected = state["plan"]["selected_materials"]
    if not selected and not state["plan"]["user_instruction"]:
        raise ValueError("선택한 근거가 없고 생성 지시도 없습니다.")
    selected_context = "\n\n".join(
        f"[{i+1}] {item['source_file']} / "
        f"{'p.' + str(item['page']) if item['page'] is not None else '페이지 미확인'}\n{item['text']}"
        for i, item in enumerate(selected)
    )
    context = (
        "AW-009 승인된 단일 대목차 작성. 대상: " + section_title + "\n"
        + "이 섹션만 작성하며 다른 섹션은 수정하지 않는다. 사실은 출처로 검증하고, "
        + "근거 없는 값은 만들지 않는다.\n"
        + "사용자 지시: " + state["plan"]["user_instruction"] + "\n"
        + "선택된 원문 재료:\n" + selected_context
    )
    project_id = project_service.create_project(profile.template_id, f"AW009 · {section_title[:50]}")
    project_service.save_project_form(
        project_id=project_id,
        answers={"user_brief": context, "user_notes": context},
        project_title=f"AW009 · {section_title[:50]}",
        organization_name="",
        evidence_topics="",
        reference_files=[("AW009_selected_materials.txt", selected_context.encode("utf-8"))]
        if selected_context else [],
        improve_partial=False,
        psst_only=False,
        disable_images=True,
    )
    artifact = project_service.regenerate_sections(
        project_id, [question.question_id], refinement_context=context,
    )
    actual = storage.load_project_input(project_id).answers.get(question.question_id, "")
    if not str(actual).strip():
        raise ValueError("현재 파트에 실제로 작성된 답안이 없어 완료할 수 없습니다.")
    path = _preferred_result(project_id)
    if not path or not path.is_file():
        raise ValueError("기존 엔진이 실제 결과 파일을 생성하지 못했습니다.")
    return {"project_id": project_id, "question_id": question.question_id,
            "target_section": section_title, "artifact": str(path),
            "artifact_size": path.stat().st_size,
            "generation_label_required": state["plan"]["generation_label_required"],
            "status": "ENGINE_OUTPUT_UNVERIFIED",
            "note": "실제 MODULE/LOCATOR E2E와 원본 HWPX 채움 증거 전에는 DONE 금지."}


@app.post("/console/modules/approve")
async def module_approve(request: Request):
    form = await request.form()
    wid = str(form.get("workspace_id", ""))
    try:
        state = module_workspace.approve(wid)
        # Engine invocation is reachable exclusively after persisted user approval.
        module_workspace.record_execution(wid, "RUNNING")
        result = _aw009_execute_approved_part(state)
        module_workspace.record_execution(wid, "ENGINE_OUTPUT_UNVERIFIED", **result)
        return RedirectResponse(url=f"/console?workspace_id={wid}", status_code=303)
    except Exception as exc:
        try:
            state = module_workspace.get(wid)
            if state.get("approved"):
                module_workspace.record_execution(wid, "BLOCKED", reason=str(exc))
        except Exception:
            pass
        return _aw009_error(f"{type(exc).__name__}: {exc}", wid)


@app.post("/console/documents/write")
async def operator_write_document(
    template_file: UploadFile = File(...),
    reference_files: list[UploadFile] | None = File(default=None),
    project_title: str = Form(default=""),
    organization_name: str = Form(default=""),
    instruction: str = Form(default=""),
    allow_docx_for_hwp: str = Form(default=""),
):
    try:
        project_id, run_id = await _run_document_generation(
            template_file=template_file,
            reference_files=reference_files or [],
            project_title=project_title,
            organization_name=organization_name,
            instruction=instruction,
            run_kind="write",
            allow_docx_for_hwp=_form_checked(allow_docx_for_hwp),
        )
    except Exception as exc:
        return RedirectResponse(url=f"/console?error={quote(str(exc)[:500], safe='')}", status_code=303)
    return RedirectResponse(url=f"/console/results/{project_id}?run_id={run_id}", status_code=303)


@app.post("/console/documents/revise")
async def operator_revise_document(
    document_file: UploadFile = File(...),
    instruction: str = Form(...),
    project_title: str = Form(default=""),
    allow_docx_for_hwp: str = Form(default=""),
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
            allow_docx_for_hwp=_form_checked(allow_docx_for_hwp),
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
    result = _preferred_result(project_id)
    if not result:
        raise HTTPException(status_code=404, detail="결과 HWPX/HWP/DOCX를 찾을 수 없습니다.")
    lock_path = _project_output_dir(project_id) / "user_locks.json"
    blocks = docx_editor.load_blocks(result) if result.suffix.lower() == ".docx" else []
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
            message=request.query_params.get("message", ""),
            error=request.query_params.get("error", ""),
        ),
    )


@app.get("/console/lrules/verify/status")
async def operator_lrules_verify_status():
    """로컬 기본값(access_gate)과 같은 콘솔 경로. 공개 바인드는 비밀번호 없이 열리지 않는다."""
    return lrule_console.verify_status()


@app.post("/console/lrules/verify")
async def operator_lrules_verify():
    message = quote(lrule_console.start_verify(None), safe="")
    return RedirectResponse(url=f"/console/lrules?message={message}", status_code=303)


@app.post("/console/lrules/{code}/verify")
async def operator_lrule_verify(code: str):
    message = quote(lrule_console.start_verify([code]), safe="")
    return RedirectResponse(url=f"/console/lrules/{code.upper()}?message={message}", status_code=303)


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


@app.post("/console/lrules/{code}/preview", response_class=HTMLResponse)
async def operator_lrule_preview(
    request: Request,
    code: str,
    base_remote_sha: str = Form(...),
    summary: str = Form(...),
    mechanizable: str = Form(default=""),
    category: str = Form(default=""),
    guard_ref: str = Form(default=""),
    gap_desc: str = Form(default=""),
    change_reason: str = Form(default=""),
    impact: str = Form(default=""),
    domain: str = Form(default=""),
):
    blocked = _git_write_blocked(f"/console/lrules/{code}")
    if blocked:
        return blocked
    before_text = ""
    updates = {
        "summary": summary,
        "mechanizable": mechanizable,
        "category": category,
        "guard_ref": guard_ref,
        "gap_desc": gap_desc,
        "impact": impact,
        "domain": domain,
    }
    preview = {**updates, "change_reason": change_reason.strip()}
    try:
        git_sync.assert_write_base(base_remote_sha)
        _, before_text = lrule_console.update_rule(code, updates)
        test = lrule_console.run_registry_tests()
        diff = git_sync._run(
            "diff",
            "--",
            str(lrule_console.REGISTRY_RELATIVE).replace("\\", "/"),
            check=False,
        )
        if not diff.strip():
            raise GitSyncError("실제 파일 변경사항이 없습니다.")
    except Exception as exc:
        if before_text:
            try:
                lrule_console.restore_text(before_text)
            except Exception:
                pass
        return RedirectResponse(
            url=f"/console/lrules/{code.upper()}?error={quote(str(exc)[:1800], safe='')}",
            status_code=303,
        )

    try:
        lrule_console.restore_text(before_text)
    except Exception as exc:
        return RedirectResponse(
            url=f"/console/lrules/{code.upper()}?error={quote(str(exc)[:1800], safe='')}",
            status_code=303,
        )

    return templates.TemplateResponse(
        request,
        "operator_rule_preview.html",
        _ctx(
            request,
            code=code.upper(),
            base_remote_sha=base_remote_sha,
            preview=preview,
            test=test.as_dict(),
            diff=diff,
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
    blocked = _git_write_blocked(f"/console/lrules/{code}")
    if blocked:
        return blocked
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
    blocked = _git_write_blocked(f"/console/lrules/{code}")
    if blocked:
        return blocked
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
    blocked = _git_write_blocked("/console/settings")
    if blocked:
        return blocked
    try:
        snapshot = git_sync.sync_from_remote()
        message = f"GitHub 동기화 완료: {snapshot.status} / {snapshot.local_sha[:8]}"
        return RedirectResponse(url=f"/console/settings?message={quote(message, safe='')}", status_code=303)
    except Exception as exc:
        return RedirectResponse(url=f"/console/settings?error={quote(str(exc)[:1200], safe='')}", status_code=303)
