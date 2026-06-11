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
}


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


def _dispatch_hwp():
    """한글 COM 객체를 띄운다(테스트에서 monkeypatch 하는 분리점)."""
    import win32com.client as win32

    return win32.Dispatch(_COM_PROGID)


def _convert_via_com(src: Path, dst: Path, save_formats: tuple[str, ...]) -> None:
    """한글 COM 으로 src 를 열어 dst 로 저장한다. 실패는 예외로 알린다.

    주의: 백그라운드/서비스 세션에서는 한글 GUI COM 서버가 안 떠서
    Dispatch/Open 단계에서 실패할 수 있다(호출측이 폴백을 처리한다).
    """
    hwp = _dispatch_hwp()
    try:
        # 보안 대화상자 억제(모듈이 등록돼 있으면 성공, 없으면 무시)
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        try:
            hwp.SetMessageBoxMode(0x00000020)
        except Exception:
            pass

        if not hwp.Open(str(src), "", ""):
            # 형식 자동 인식 실패 시 확장자 필터 명시 재시도
            if not hwp.Open(str(src), src.suffix.lstrip(".").upper(), ""):
                raise RuntimeError(f"한글에서 열기 실패: {src}")
        for fmt in save_formats:
            try:
                if hwp.SaveAs(str(dst), fmt, ""):
                    return
            except Exception:
                continue
        raise RuntimeError(f"한글 저장 실패(시도 포맷 {save_formats}): {dst}")
    finally:
        try:
            hwp.Clear(1)
        except Exception:
            pass
        try:
            hwp.Quit()
        except Exception:
            pass


# --- 경로/검증 도우미 ---------------------------------------------------------

def _resolve_paths(in_path: str | Path, out_path: Optional[str | Path],
                   default_suffix: str) -> tuple[Path, Path]:
    src = Path(in_path)
    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    dst = Path(out_path) if out_path else src.with_suffix(default_suffix)
    if src.resolve() == dst.resolve():
        raise ValueError("입력과 출력 경로가 같습니다. 원본 덮어쓰기는 금지입니다.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    return src, dst


def _nonempty_file(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


# --- HWP/HWPX → DOCX ----------------------------------------------------------

def hwp_to_docx(in_path: str | Path, out_path: Optional[str | Path] = None,
                *, use_com: bool = True) -> ConvertReport:
    """HWP/HWPX 를 DOCX 로 변환한다(COM → 구조 변환 → PrvText 순 폴백)."""
    src, dst = _resolve_paths(in_path, out_path, ".docx")
    ext = src.suffix.lower()
    if ext not in _HWP_EXTS:
        raise ValueError(f"HWP/HWPX 입력만 지원합니다: {src.name}")
    report = ConvertReport(direction="hwp->docx", output=str(dst))

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
        from ..document_ingest import _convert_hwp_to_docx, _convert_hwpx_to_docx

        if ext == ".hwp":
            _convert_hwp_to_docx(src, dst)
            report.method = "unhwp"
        else:
            _convert_hwpx_to_docx(src, dst)
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
            from ..document_ingest import _write_text_docx, extract_hwp_preview_text

            preview = extract_hwp_preview_text(src)
            if preview.strip():
                _write_text_docx(preview, dst, title=src.stem)
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
    src, dst = _resolve_paths(in_path, out_path, ".hwp")
    if src.suffix.lower() != ".docx":
        raise ValueError(f"DOCX 입력만 지원합니다: {src.name}")
    dst_ext = dst.suffix.lower()
    if dst_ext not in _HWP_EXTS:
        raise ValueError(f"출력은 .hwp/.hwpx 만 지원합니다: {dst.name}")
    report = ConvertReport(direction="docx->hwp", output=str(dst))

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
