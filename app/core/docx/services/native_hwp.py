"""Native HWP/HWPX I/O. Never calls Hancom COM or a DOCX converter.

P0 기본은 rhwp 를 쓰지 않는다. ``AUTO_WRITE_ENABLE_RHWP=1`` 일 때만
``RHWP_EXE`` 또는 PATH 의 rhwp 를 찾는다. 렌더 성공은 화면 승인과 별개다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any


def file_sha256(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rhwp_enabled() -> bool:
    """확장 단계에서만 rhwp 를 켠다. 기본값은 끄짐."""
    raw = os.environ.get("AUTO_WRITE_ENABLE_RHWP", "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _rhwp_basename_ok(path: Path) -> bool:
    """Accept rhwp / rhwp.exe. Never treat soffice as rhwp."""
    name = path.name.lower()
    if "soffice" in name or "libreoffice" in name:
        return False
    return name == "rhwp" or name.startswith("rhwp.")


def resolve_rhwp_executable() -> str | None:
    """RHWP_EXE 가 실제 파일이면 그 경로, 아니면 PATH 의 rhwp.

    ``AUTO_WRITE_ENABLE_RHWP`` 가 없으면 설치 여부와 관계없이 None.
    RHWP_EXE 가 비어 있지 않은데 파일이 없으면 PATH 로 넘어가지 않는다.
    LibreOffice(soffice) 는 반환하지 않는다.
    """
    if not rhwp_enabled():
        return None
    raw = os.environ.get("RHWP_EXE")
    if raw is not None and raw.strip():
        path = Path(raw.strip().strip('"'))
        if path.is_file() and _rhwp_basename_ok(path):
            return str(path)
        return None
    found = shutil.which("rhwp")
    if found:
        path = Path(found)
        if path.is_file() and _rhwp_basename_ok(path):
            return str(path)
    return None


class UnsupportedRhwpError(RuntimeError):
    """설치된 rhwp 가 ``--json`` 계약을 말하지 않는다."""


# 실행 파일 경로 → (JSON 가능 여부, 버전 또는 오류 문장). 프로세스당 1회.
_CAPABILITY: dict[str, tuple[bool, str]] = {}
_CAPABILITY_LOCK = threading.Lock()
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+(?:\.\d+)*)")
# 문서 없이 JSON 객체를 돌려주는 현재 rhwp 계약. 0.7.19 는 이 명령을 모른다.
_JSON_CAPABILITY_ARGS = ("capabilities", "--search", "info", "--json")


def clear_rhwp_capability_cache() -> None:
    """테스트가 같은 경로의 목 응답을 바꿀 때 캐시를 비운다."""
    with _CAPABILITY_LOCK:
        _CAPABILITY.clear()


def _run_rhwp(executable: str, args: list[str] | tuple[str, ...], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _version_label(text: str) -> str:
    match = _VERSION_RE.search(text or "")
    return match.group(1) if match else "unknown"


def _read_rhwp_version(executable: str) -> str:
    try:
        proc = _run_rhwp(executable, ["--version"], timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return _version_label(f"{proc.stdout or ''}\n{proc.stderr or ''}")


def _unsupported_message(version: str, stderr: str, stdout: str = "") -> str:
    err = (stderr or "").strip()
    out = (stdout or "").strip()
    text = f"unsupported rhwp version {version}: stderr: {err[-800:] if err else '(empty)'}"
    if out and not _json_object(out):
        text += f" stdout: {out[-800:]}"
    return text


def _json_object(stdout: str) -> dict[str, Any] | None:
    text = (stdout or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _unsupported_protocol(stdout: str, stderr: str, returncode: int) -> bool:
    """exit 0 인데 stdout 이 비었거나 JSON 이 아니거나 stderr 가 있으면 미지원.

    0.7.19 는 ``--json`` 을 무시하고 한국어 평문을 stdout 에 쓰거나,
    오류를 stderr 에만 쓰고 exit 0 을 반환한다.
    """
    if returncode:
        return False
    if (stderr or "").strip():
        return True
    return _json_object(stdout) is None


def _remember_capability(executable: str, ok: bool, detail: str) -> None:
    with _CAPABILITY_LOCK:
        _CAPABILITY[executable] = (ok, detail)


def _cached_capability(executable: str) -> tuple[bool, str] | None:
    with _CAPABILITY_LOCK:
        found = _CAPABILITY.get(executable)
        return None if found is None else (found[0], found[1])


def _probe_rhwp_capability(executable: str) -> tuple[bool, str]:
    """실행 파일마다 JSON 지원을 한 번만 확인하고 캐시한다."""
    cached = _cached_capability(executable)
    if cached is not None:
        return cached
    version = _read_rhwp_version(executable)
    try:
        proc = _run_rhwp(executable, list(_JSON_CAPABILITY_ARGS), timeout=20)
    except subprocess.TimeoutExpired:
        detail = f"unsupported rhwp version {version}: capability probe timeout"
        _remember_capability(executable, False, detail)
        return False, detail
    except OSError as exc:
        detail = f"unsupported rhwp version {version}: {exc}"
        _remember_capability(executable, False, detail)
        return False, detail
    payload = _json_object(proc.stdout or "")
    if proc.returncode == 0 and payload is not None and not (proc.stderr or "").strip():
        reported = payload.get("version")
        if isinstance(reported, str) and reported.strip():
            version = reported.strip()
        elif version == "unknown":
            version = _version_label(proc.stdout or "")
        _remember_capability(executable, True, version)
        return True, version
    if proc.returncode:
        err = (proc.stderr or proc.stdout or "").strip()
        detail = (
            f"unsupported rhwp version {version}: exit {proc.returncode}: "
            f"{err[-1200:] or '(stderr empty)'}"
        )
    else:
        detail = _unsupported_message(version, proc.stderr or "", proc.stdout or "")
    _remember_capability(executable, False, detail)
    return False, detail


def rhwp_available() -> bool:
    """JSON 계약을 말하는 rhwp 만 설치된 것으로 본다.

    기본값은 False 다. ``AUTO_WRITE_ENABLE_RHWP=1`` 이 아니면 프로세스를
    띄우지 않는다. 바이너리는 있으나 ``--json`` 을 모르는 버전(예: 0.7.19)은
    미설치와 같다. ``RHWP_EXE`` 가 비어 있지 않은데 파일이 없으면 PATH 로
    넘어가지 않는다.
    """
    if not rhwp_enabled():
        return False
    executable = resolve_rhwp_executable()
    if not executable:
        return False
    ok, _detail = _probe_rhwp_capability(executable)
    return ok


def _rhwp_json(*args: str, timeout: int = 60) -> dict[str, Any]:
    if not rhwp_enabled():
        raise FileNotFoundError(
            "rhwp disabled: AUTO_WRITE_ENABLE_RHWP=1 이 없으면 rhwp 를 실행하지 않습니다."
        )
    executable = resolve_rhwp_executable()
    if not executable:
        raise FileNotFoundError("rhwp 미설치: RHWP_EXE에 실행 파일 경로를 지정하세요.")
    capable, detail = _probe_rhwp_capability(executable)
    if not capable:
        raise UnsupportedRhwpError(detail)
    try:
        proc = _run_rhwp(executable, [*args, "--json"], timeout=timeout)
    except OSError as exc:
        raise FileNotFoundError(f"rhwp 실행 실패: {exc}") from exc
    if proc.returncode:
        raise ValueError(f"rhwp {args[0]} 실패(exit {proc.returncode}): {(proc.stderr or '')[-1200:]}")
    if _unsupported_protocol(proc.stdout or "", proc.stderr or "", proc.returncode):
        message = _unsupported_message(detail or "unknown", proc.stderr or "", proc.stdout or "")
        _remember_capability(executable, False, message)
        raise UnsupportedRhwpError(message)
    payload = _json_object(proc.stdout or "")
    if payload is None:
        message = _unsupported_message(detail or "unknown", proc.stderr or "", proc.stdout or "")
        _remember_capability(executable, False, message)
        raise UnsupportedRhwpError(message)
    return payload


def prepare_native_source(source: str | Path, output: str | Path) -> tuple[Path, dict[str, Any]]:
    """Parse HWP natively and verify the HWPX working copy before using it."""
    src, dst = Path(source), Path(output)
    original_hash = file_sha256(src)
    if src.suffix.lower() == ".hwpx":
        return src, {"source_sha256": original_hash, "conversion": "NOT_NEEDED"}
    if src.suffix.lower() != ".hwp" or dst.suffix.lower() != ".hwpx":
        raise ValueError("HWP 입력과 HWPX 출력 경로가 필요합니다.")
    if src.resolve() == dst.resolve() or (dst.exists() and os.path.samefile(src, dst)):
        raise ValueError("원본 덮어쓰기는 금지입니다.")
    if dst.exists():
        raise FileExistsError(dst)
    before = _rhwp_json("info", str(src.resolve()))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-convert-", dir=dst.parent) as folder:
        candidate = Path(folder) / "candidate.hwpx"
        conversion = _rhwp_json(
            "export-hwpx", str(src.resolve()), str(candidate.resolve()),
            "--verify", "--verify-pages",
        )
        if (conversion.get("verify", {}).get("identical") is not True
                or conversion.get("verifyPages", {}).get("identical") is not True):
            raise ValueError("HWP→HWPX 구조/쪽수 보존 검증 미통과")
        reopened = _rhwp_json("info", str(candidate.resolve()))
        if reopened.get("format") != "hwpx" or reopened.get("pageCount") != before.get("pageCount"):
            raise ValueError("변환 HWPX 재열기 또는 쪽수 검증 실패")
        if file_sha256(src) != original_hash:
            raise ValueError("변환 중 원본 변경 감지")
        # Copy only the verified candidate, retaining the immutable HWP upload.
        with candidate.open("rb") as incoming, dst.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    return dst, {"source_sha256": original_hash, "working_sha256": file_sha256(dst),
                 "conversion": "VERIFIED", "source_info": before,
                 "verify": conversion["verify"], "verify_pages": conversion["verifyPages"]}


def _disabled_render_evidence() -> dict[str, Any]:
    """기본 끔. REVIEW_REQUIRED 로 올리지 않고 rhwp 를 호출하지 않는다."""
    return {
        "ok": False,
        "severity": "PASS",
        "renderer": "disabled",
        "render_status": "NOT_RUN",
        "reopen_status": "NOT_RUN",
        "visual_review": "NOT_RUN",
        "pdf": "",
        "page_count": 0,
        "l005_pixel": "NOT_RUN",
        "l050_pdf": "NOT_RUN",
        "pixel_reopen_claimed": False,
        "disabled": True,
        "message": (
            "rhwp disabled — AUTO_WRITE_ENABLE_RHWP=1 이 없으면 "
            "재열기/렌더를 실행하지 않음(NOT_RUN)"
        ),
    }


def verify_hwpx_native(path: str | Path) -> dict[str, Any]:
    """Reopen and render the exact candidate; never use a stale sibling PDF.

    기본값은 검사를 실행하지 않는다. 결과는 NOT_RUN/disabled 이고
    REVIEW_REQUIRED 가 아니다.
    """
    if not rhwp_enabled():
        return _disabled_render_evidence()
    candidate = Path(path)
    evidence: dict[str, Any] = {
        "ok": False, "severity": "REVIEW_REQUIRED", "renderer": "rhwp",
        "render_status": "NOT_RUN", "reopen_status": "NOT_RUN",
        "visual_review": "NOT_RUN", "pdf": "", "page_count": 0,
        # L005 픽셀·L050 동일 stem PDF는 이 함수의 PASS가 아니다.
        "l005_pixel": "NOT_RUN", "l050_pdf": "NOT_RUN",
        "pixel_reopen_claimed": False,
        "disabled": False,
    }
    try:
        if candidate.suffix.lower() != ".hwpx":
            raise ValueError("최종 HWPX 파일 자체만 검수할 수 있습니다.")
        expected = file_sha256(candidate)
        evidence["candidate_sha256"] = expected
        reopened = _rhwp_json("info", str(candidate.resolve()))
        pages = reopened.get("pageCount")
        if reopened.get("format") != "hwpx" or not isinstance(pages, int) or pages < 1:
            raise ValueError("HWPX 재열기 결과의 형식/쪽수가 유효하지 않습니다.")
        evidence.update(reopen_status="PASS", page_count=pages)
        # A unique run directory prevents concurrent or previous renders being reused.
        folder = Path(tempfile.mkdtemp(prefix="native-preview-", dir=candidate.parent))
        snapshot = folder / "candidate.hwpx"
        shutil.copyfile(candidate, snapshot)
        if file_sha256(snapshot) != expected:
            raise ValueError("렌더 스냅샷 hash 불일치")
        pdf = folder / "preview.pdf"
        rendered = _rhwp_json("export-pdf", str(snapshot.resolve()), "-o", str(pdf.resolve()))
        from pypdf import PdfReader

        actual_pages = len(PdfReader(str(pdf)).pages)
        if (rendered.get("format") != "pdf" or actual_pages != pages
                or rendered.get("pageCount") != pages or rendered.get("renderedCount") != pages):
            raise ValueError("HWPX 전체 페이지와 렌더 PDF 쪽수가 일치하지 않습니다.")
        if file_sha256(snapshot) != expected or file_sha256(candidate) != expected:
            raise ValueError("검수 도중 후보 파일 변경 감지 — 이전 렌더 무효")
        evidence.update(
            render_status="PASS", pdf=str(pdf), pdf_sha256=file_sha256(pdf),
            render_source_sha256=expected, rendered_count=actual_pages,
            visual_review="NOT_RUN", l005_pixel="JUDGMENT", l050_pdf="NOT_SIBLING",
            pixel_reopen_claimed=False,
            message=(
                "HWPX 재열기·전체 쪽 렌더 완료. 실제 페이지 품질 검토가 필요합니다. "
                "L005 한글 픽셀과 L050 동일명 PDF는 이 결과로 PASS가 아닙니다."
            ),
        )
    except (FileNotFoundError, UnsupportedRhwpError) as exc:
        # 미설치와 미지원 버전은 같다. REVIEW_REQUIRED/_DRAFT 로 올리지 않는다.
        evidence.update(
            render_status="UNAVAILABLE",
            reopen_status="NOT_RUN",
            visual_review="ENV_BLOCKED",
            l005_pixel="ENV_BLOCKED",
            l050_pdf="ENV_BLOCKED",
            pixel_reopen_claimed=False,
            message=str(exc),
        )
    except subprocess.TimeoutExpired:
        evidence.update(render_status="TIMEOUT", message="HWPX 재열기/렌더 시간 초과")
    except Exception as exc:
        evidence.update(render_status="FAIL", message=f"{type(exc).__name__}: {exc}")
    return evidence
