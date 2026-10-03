"""hwp_docx_convert.py — HWP/HWPX ↔ DOCX 양방향 변환 서비스.

기존 자산을 한 진입점으로 통합한다:

- HWP/HWPX → DOCX (3단 폴백, 위에서부터 시도)
    1. ``hancom_com``  : 한글(Hancom) COM 자동화 — 서식·표·이미지가 가장 충실.
                         단, 백그라운드/서비스 세션에서는 GUI COM 서버가 안 떠서
                         실패할 수 있다(이때 자동으로 다음 단계로 넘어간다).
    2. ``unhwp``/``hwpx_xml`` : ``document_ingest`` 의 구조 변환 재사용 —
                         문단·표(병합 포함)까지 복원, 서식은 제한.
    3. ``prvtext``     : HWP 미리보기 텍스트 폴백 — 본문 일부 누락 가능.
- DOCX → HWP/HWPX (한글 COM 이 유일한 자동 경로)
    COM 미가용/실패 시 예외 대신 ``ok=False`` 리포트 + 사람이 할 일 안내를 담는다.

안전 원칙
---------
- 입력 파일은 절대 수정하지 않는다(``out == in`` 이면 ``ValueError``).
- AI 호출 없음 — 동일 입력, 동일 결과(COM 가용성에 따른 method 차이만 존재).
- ``scripts/docx2hwp.py``(단발 스크립트)는 보존하며, 같은 COM 절차를 서비스로 일반화한 것이다.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_HWP_EXTS = {".hwp", ".hwpx"}
_COM_PROGID = "HWPFrame.HwpObject"

# 한글 SaveAs 포맷 인자는 버전에 따라 받아들이는 문자열이 달라 순서대로 시도한다.
_SAVE_FORMATS = {
    ".docx": ("DOCX", "OOXML", "MSWORD"),
    ".hwp": ("HWP",),
    ".hwpx": ("HWPX", "HWPML2X"),
    ".pdf": ("PDF",),
}

# HWP 양식 업로드가 변환 불가일 때 DOCX로 내려가지 않고 이 안내를 그대로 보여 준다.
HWP_TO_HWPX_UNAVAILABLE_NOTE = (
    "HWP 양식을 HWPX로 바꾸지 못해 DOCX로 진행하지 않았습니다. "
    "한글에서 이 파일을 연 다음 [다른 이름으로 저장]을 HWPX로 선택해 다시 업로드하세요. "
    "DOCX로 진행하려면 콘솔에서 'DOCX로 진행'을 선택한 뒤 같은 HWP를 다시 올리세요. "
    "DOCX 경로는 원본 양식 레이아웃을 보존하지 않습니다."
)

class HangulComTimeout(TimeoutError):
    """한글 COM 단계가 제한시간 안에 끝나지 않았을 때."""

    def __init__(self, stage: str, timeout_seconds: float) -> None:
        self.stage = stage
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Hangul COM timeout at {stage} ({timeout_seconds:g}s)")


# 변경 추적/저장 경고처럼 확인·취소형 메시지는 자동으로 확인/저장을 선택한다.
# SetMessageBoxMode 문서의 MB_OKCANCEL_IDOK 값.
_HANGUL_AUTO_CONFIRM_MODE = 0x00000010
_COM_STAGE_TIMEOUTS: dict[str, float] = {
    "Dispatch": 30.0,
    "RegisterModule": 10.0,
    "SetMessageBoxMode": 10.0,
    "Open": 60.0,
    "SaveAs": 120.0,
    "Clear": 15.0,
    "Quit": 15.0,
}

_COM_CONVERT_LOCK = threading.RLock()


def _com_stage_timeout(stage: str) -> float:
    base = stage.split("[", 1)[0]
    return float(_COM_STAGE_TIMEOUTS.get(base, 60.0))


def _run_com_stage(stage: str, operation, *, timeout_cleanup=None):
    """COM 호출은 같은 스레드에서 수행하고 watchdog으로 제한시간을 강제한다.

    watchdog은 제한시간을 넘기면 이번 호출의 Hwp PID만 종료하도록
    timeout_cleanup을 실행한다. 실제 COM 호출이 종료 뒤 예외를 내도 timeout으로 승격한다.
    """
    timeout = _com_stage_timeout(stage)
    timed_out = threading.Event()

    def _expire() -> None:
        timed_out.set()
        if timeout_cleanup is not None:
            try:
                timeout_cleanup()
            except Exception:
                pass

    timer = threading.Timer(timeout, _expire)
    timer.daemon = True
    timer.start()
    try:
        try:
            result = operation()
        except BaseException as exc:
            if timed_out.is_set():
                raise HangulComTimeout(stage, timeout) from exc
            raise
    finally:
        timer.cancel()
    if timed_out.is_set():
        raise HangulComTimeout(stage, timeout)
    return result



@dataclass
class ConvertReport:
    direction: str                 # "hwp->docx" | "docx->hwp"
    method: str = ""               # "hancom_com" | "unhwp" | "hwpx_xml" | "prvtext"
    ok: bool = False
    output: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction, "method": self.method,
            "ok": self.ok, "output": self.output, "notes": self.notes,
        }


# --- 한글(Hancom) COM ---------------------------------------------------------

def hancom_com_available() -> bool:
    """한글 COM ProgID 등록 여부(설치 여부)만 확인한다 — Dispatch 는 하지 않는다."""
    try:
        import winreg

        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, _COM_PROGID))
        return True
    except Exception:
        return False


def kill_hangul_processes() -> list[str]:
    """L003: Dispatch 직전 훅. 사용자의 한글 창은 닫지 않는다.

    열려 있는 한글을 이미지 이름 전체로 종료하지 않는다. 빈 목록을 돌려 주고,
    이번 호출이 새로 띄운 프로세스만 ``_convert_via_com`` 이 닫는다.
    """
    return []


def _query_hangul_tasklist() -> str:
    """Windows tasklist 원문 조회. 테스트에서 PID 조회 자체를 독립 patch하는 seam."""
    if sys.platform != "win32":
        return ""
    return subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq Hwp.exe", "/FO", "CSV", "/NH"],
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _hangul_image_pids() -> set[int]:
    """지금 떠 있는 Hwp.exe PID. 비-Windows 이거나 조회 실패면 빈 집합."""
    if sys.platform != "win32":
        return set()
    try:
        output = _query_hangul_tasklist()
    except Exception:
        return set()
    found: set[int] = set()
    for line in (output or "").splitlines():
        parts = [piece.strip().strip('"') for piece in line.split(",")]
        if len(parts) >= 2 and parts[0].lower() == "hwp.exe" and parts[1].isdigit():
            found.add(int(parts[1]))
    return found

def _kill_owned_pids(pids: set[int]) -> None:
    """이 호출이 새로 띄운 Hwp.exe PID 만 종료한다."""
    if sys.platform != "win32" or not pids:
        return
    still = _hangul_image_pids()
    for pid in pids:
        if pid not in still:
            continue
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )


def _hwp_object_pid(hwp) -> int | None:
    """Dispatch가 반환한 Hwp 객체의 첫 창 HWND에서 실제 프로세스 PID를 구한다."""
    if sys.platform != "win32":
        return None
    try:
        hwnd = int(hwp.XHwpWindows.Item(0).Handle)
        pid = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(
            ctypes.c_void_p(hwnd), ctypes.byref(pid)
        )
        return int(pid.value) or None
    except Exception:
        return None

def _dispatch_hwp(*, skip_com_guard: bool = False):
    """한글 COM 객체를 띄운다(테스트에서 monkeypatch 하는 분리점).

    기본: ``hancom_com_guard`` 로 HOffice130(2024·로그인) COM 기동을 차단한다.
  ``skip_com_guard=True`` 또는 ``AUTO_WRITE_ALLOW_HANCOM_2024_COM=1`` 로만 우회.
    L003: Dispatch 직전에 ``kill_hangul_processes``. 그 함수는 전역 종료를 하지 않는다.
    """
    kill_hangul_processes()
    if not skip_com_guard:
        from .hancom_com_guard import assert_safe_hwp_com_or_raise

        assert_safe_hwp_com_or_raise()
    import win32com.client as win32

    return win32.Dispatch(_COM_PROGID)


def export_pdf_via_com(src: str | Path, dst: str | Path) -> None:
    """한글 COM SaveAs PDF. 한글이 없으면 예외. 호출측이 없음을 먼저 가른다."""
    _convert_via_com(Path(src), Path(dst), _SAVE_FORMATS[".pdf"])


def _convert_via_com(src: Path, dst: Path, save_formats: tuple[str, ...]) -> None:
    """한글 COM 으로 src 를 열어 dst 로 저장한다. 실패는 예외로 알린다.

    문서 Open 전에 확인/취소형 메시지 자동응답을 켠다. Dispatch/Open/SaveAs/Quit
    각 단계에는 watchdog 제한시간을 적용하고, 초과 시 이번 호출이 새로 띄운
    Hwp PID만 종료해 블로킹 COM 호출을 깨운다.
    """
    with _COM_CONVERT_LOCK:
        before_pids = _hangul_image_pids()
    
        def _dispatch_timeout_cleanup() -> None:
            _kill_owned_pids(_hangul_image_pids() - before_pids)
    
        hwp = _run_com_stage(
            "Dispatch",
            _dispatch_hwp,
            timeout_cleanup=_dispatch_timeout_cleanup,
        )
        dispatch_pid = _hwp_object_pid(hwp)
        owned_pids = (
            {dispatch_pid}
            if dispatch_pid is not None and dispatch_pid not in before_pids
            else set()
        )
    
        def _owned_cleanup() -> None:
            _kill_owned_pids(set(owned_pids))
    
        try:
            hwp.XHwpWindows.Item(0).Visible = False
        except Exception:
            pass
        try:
            try:
                _run_com_stage(
                    "RegisterModule",
                    lambda: hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule"),
                    timeout_cleanup=_owned_cleanup,
                )
            except HangulComTimeout:
                raise
            except Exception:
                pass
            try:
                _run_com_stage(
                    "SetMessageBoxMode",
                    lambda: hwp.SetMessageBoxMode(_HANGUL_AUTO_CONFIRM_MODE),
                    timeout_cleanup=_owned_cleanup,
                )
            except HangulComTimeout:
                raise
            except Exception:
                pass
    
            opened = _run_com_stage(
                "Open",
                lambda: hwp.Open(str(src), "", ""),
                timeout_cleanup=_owned_cleanup,
            )
            if not opened:
                opened = _run_com_stage(
                    "Open[format]",
                    lambda: hwp.Open(str(src), src.suffix.lstrip(".").upper(), ""),
                    timeout_cleanup=_owned_cleanup,
                )
                if not opened:
                    raise RuntimeError(f"한글에서 열기 실패: {src}")
            for fmt in save_formats:
                try:
                    saved = _run_com_stage(
                        f"SaveAs[{fmt}]",
                        lambda fmt=fmt: hwp.SaveAs(str(dst), fmt, ""),
                        timeout_cleanup=_owned_cleanup,
                    )
                    if saved:
                        return
                except HangulComTimeout:
                    raise
                except Exception:
                    continue
            raise RuntimeError(f"한글 저장 실패(시도 포맷 {save_formats}): {dst}")
        finally:
            if owned_pids:
                try:
                    _run_com_stage(
                        "Clear",
                        lambda: hwp.Clear(1),
                        timeout_cleanup=_owned_cleanup,
                    )
                except Exception:
                    pass
                try:
                    _run_com_stage(
                        "Quit",
                        hwp.Quit,
                        timeout_cleanup=_owned_cleanup,
                    )
                except Exception:
                    pass
                _kill_owned_pids(owned_pids)

# --- 경로/검증 도우미 ---------------------------------------------------------

def _resolve_paths(in_path: str | Path, out_path: Optional[str | Path],
                   default_suffix: str) -> tuple[Path, Path, str]:
    src = Path(in_path)
    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    dst = Path(out_path) if out_path else src.with_suffix(default_suffix)
    if src.resolve() == dst.resolve():
        raise ValueError("입력과 출력 경로가 같습니다. 원본 덮어쓰기는 금지입니다.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    # 기존 출력 파일(사용자가 수정했을 수 있음)을 무경고로 덮어쓰지 않게 타임스탬프
    # 백업으로 보존한다(단일출처 usage_acceptance.backup_existing_output 재사용).
    from .usage_acceptance import backup_existing_output

    prev_backup = backup_existing_output(dst) if dst.exists() else ""
    return src, dst, prev_backup


def _nonempty_file(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# --- HWP/HWPX → DOCX ----------------------------------------------------------

def hwp_to_docx(in_path: str | Path, out_path: Optional[str | Path] = None,
                *, use_com: bool = True) -> ConvertReport:
    """HWP/HWPX 를 DOCX 로 변환한다(COM → 구조 변환 → PrvText 순 폴백)."""
    src, dst, prev_bak = _resolve_paths(in_path, out_path, ".docx")
    ext = src.suffix.lower()
    if ext not in _HWP_EXTS:
        raise ValueError(f"HWP/HWPX 입력만 지원합니다: {src.name}")
    report = ConvertReport(direction="hwp->docx", output=str(dst))
    if prev_bak:
        report.notes.append(f"기존 출력 파일을 백업했습니다: {prev_bak}")

    # 1) 한글 COM — 가장 충실한 변환
    if use_com and hancom_com_available():
        try:
            _convert_via_com(src, dst, _SAVE_FORMATS[".docx"])
            if _nonempty_file(dst):
                report.method, report.ok = "hancom_com", True
                return report
        except Exception as exc:
            report.notes.append(
                f"한글 COM 변환 실패({type(exc).__name__}) — 구조 변환으로 폴백합니다. "
                "(백그라운드 세션에서는 한글 COM 이 안 뜰 수 있습니다)")

    # 2) 구조 변환(unhwp / HWPX XML) — document_ingest 재사용
    try:
        # The legacy ingest module remains the shared compatibility seam while
        # the core/domain split is in progress. Existing callers and fixtures
        # patch that module, so resolving it here keeps both import paths in
        # the same runtime contract.
        from auto_write import document_ingest as _document_ingest

        if ext == ".hwp":
            _document_ingest._convert_hwp_to_docx(src, dst)
            report.method = "unhwp"
        else:
            _document_ingest._convert_hwpx_to_docx(src, dst)
            report.method = "hwpx_xml"
        if _nonempty_file(dst):
            report.ok = True
            report.notes.append("구조 변환(문단·표 복원) — 글꼴 등 세부 서식은 제한됩니다.")
            return report
    except Exception as exc:
        report.notes.append(f"구조 변환 실패: {exc}")

    # 3) PrvText 폴백(HWP 전용) — 텍스트만
    if ext == ".hwp":
        try:
            from auto_write import document_ingest as _document_ingest

            preview = _document_ingest.extract_hwp_preview_text(src)
            if preview.strip():
                _document_ingest._write_text_docx(preview, dst, title=src.stem)
                report.method, report.ok = "prvtext", True
                report.notes.append("미리보기 텍스트(PrvText)만 추출 — 본문 일부가 누락될 수 있습니다.")
                return report
        except Exception as exc:
            report.notes.append(f"PrvText 추출 실패: {exc}")

    report.notes.append("변환 실패 — 한글에서 직접 '다른 이름으로 저장(DOCX)' 후 재시도를 권장합니다.")
    return report


# --- DOCX → HWP/HWPX ----------------------------------------------------------

def docx_to_hwp(in_path: str | Path, out_path: Optional[str | Path] = None) -> ConvertReport:
    """DOCX 를 HWP(기본) 또는 HWPX(출력 확장자로 지정) 로 변환한다.

    한글 COM 이 유일한 자동 경로다. 미가용/실패 시 예외 대신 ``ok=False`` 와
    사람이 할 일(대화형 PowerShell 에서 실행, 보안 승인 클릭)을 notes 에 담는다.
    """
    src, dst, prev_bak = _resolve_paths(in_path, out_path, ".hwp")
    if src.suffix.lower() != ".docx":
        raise ValueError(f"DOCX 입력만 지원합니다: {src.name}")
    dst_ext = dst.suffix.lower()
    if dst_ext not in _HWP_EXTS:
        raise ValueError(f"출력은 .hwp/.hwpx 만 지원합니다: {dst.name}")
    report = ConvertReport(direction="docx->hwp", output=str(dst))
    if prev_bak:
        report.notes.append(f"기존 출력 파일을 백업했습니다: {prev_bak}")

    if not hancom_com_available():
        report.notes.append(
            "한글(Hancom Office)이 설치되어 있지 않거나 COM 이 등록되지 않았습니다 — "
            "DOCX→HWP 자동 변환은 한글 COM 으로만 가능합니다.")
        return report
    try:
        _convert_via_com(src, dst, _SAVE_FORMATS[dst_ext])
        if _nonempty_file(dst):
            report.method, report.ok = "hancom_com", True
            return report
        report.notes.append("변환은 끝났으나 결과 파일이 없습니다(권한/경로 확인).")
    except Exception as exc:
        report.notes.append(
            f"한글 COM 변환 실패({type(exc).__name__}: {exc}) — 대화형 PowerShell 에서 "
            "다시 실행하고, 한글 '보안 승인' 대화상자가 뜨면 '허용'을 누르세요.")
    return report


def hwp_to_hwpx(in_path: str | Path, out_path: Optional[str | Path] = None) -> ConvertReport:
    """HWP를 HWPX로 변환한다. DOCX로 폴백하지 않는다.

    P0 기본은 한글 COM ``_convert_via_com`` (XHwpWindows + HWPX SaveAs) 만 쓴다.
    ``AUTO_WRITE_ENABLE_RHWP=1`` 이고 JSON rhwp 가 있을 때만
    ``prepare_native_source`` 를 먼저 시도하고, 실패하면 COM 으로 넘긴다.
    둘 다 없으면 ``ok=False`` 와 한글 재저장/DOCX 명시 선택 안내만 반환한다.
    """
    from core.docx.services import native_hwp as _native_hwp

    src = Path(in_path)
    dst = Path(out_path) if out_path else src.with_suffix(".hwpx")
    if src.suffix.lower() != ".hwp":
        raise ValueError(f"HWP 입력만 HWPX로 변환합니다: {src.name}")
    if dst.suffix.lower() != ".hwpx":
        raise ValueError(f"출력은 .hwpx 만 지원합니다: {dst.name}")
    src, dst, prev_bak = _resolve_paths(src, dst, ".hwpx")
    report = ConvertReport(direction="hwp->hwpx", output=str(dst))
    if prev_bak:
        report.notes.append(f"기존 출력 파일을 백업했습니다: {prev_bak}")

    if _native_hwp.rhwp_available():
        try:
            prepared, _meta = _native_hwp.prepare_native_source(src, dst)
            if _nonempty_file(prepared):
                report.method, report.ok = "rhwp", True
                report.notes.append("rhwp로 HWP를 HWPX로 변환했습니다. 원본 HWP는 수정하지 않았습니다.")
                return report
            report.notes.append("rhwp 변환 결과가 비어 있습니다.")
        except Exception as exc:
            report.notes.append(f"rhwp HWP→HWPX 실패({type(exc).__name__}: {exc})")
        if dst.exists() and not report.ok:
            try:
                dst.unlink()
            except OSError:
                report.notes.append(HWP_TO_HWPX_UNAVAILABLE_NOTE)
                return report

    if hancom_com_available():
        try:
            _convert_via_com(src, dst, _SAVE_FORMATS[".hwpx"])
            if _nonempty_file(dst):
                report.method, report.ok = "hancom_com", True
                report.notes.append(
                    "한글 COM으로 HWPX를 저장했습니다. 원본 HWP는 수정하지 않았습니다."
                )
                return report
            report.notes.append("한글 COM 저장 결과가 비어 있습니다.")
        except Exception as exc:
            report.notes.append(
                f"한글 COM HWP→HWPX 실패({type(exc).__name__}: {exc}) — "
                "대화형 Windows에서 한글을 연 뒤 다시 시도하거나, HWPX로 직접 저장하세요."
            )
        if dst.exists() and dst.stat().st_size <= 0:
            try:
                dst.unlink()
            except OSError:
                pass

    report.notes.append(HWP_TO_HWPX_UNAVAILABLE_NOTE)
    return report


# --- 방향 자동 인식 진입점 ----------------------------------------------------

def convert(in_path: str | Path, out_path: Optional[str | Path] = None,
            *, use_com: bool = True) -> ConvertReport:
    """확장자로 방향을 자동 인식해 변환한다(.hwp/.hwpx→.docx, .docx→.hwp)."""
    ext = Path(in_path).suffix.lower()
    if ext in _HWP_EXTS:
        return hwp_to_docx(in_path, out_path, use_com=use_com)
    if ext == ".docx":
        return docx_to_hwp(in_path, out_path)
    raise ValueError(f"지원하지 않는 형식입니다(.hwp/.hwpx/.docx 만 가능): {ext}")
