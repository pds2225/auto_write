"""hwp_com_fill.py — 바이너리 .hwp 원본 양식을 한글(Hancom) COM 으로 직접 채운다.

목적
----
``hwpx_fill`` 은 HWPX(=ZIP/XML) 를 변환 없이 직접 채운다. 그러나 **바이너리 .hwp**
(HWP 5.0) 는 XML 이 아니라 직접 편집이 불가능하다. 한글 COM 만이 .hwp 를 변환 왕복
없이 열어 **누름틀(필드)에 값만 입력**하고 그대로 .hwp 로 저장할 수 있다.

대상
----
- **누름틀(field) 양식**: ``PutFieldText`` 로 필드명↔라벨 매칭해 값 입력(가장 안전).
- 표만 있고 누름틀이 없는 .hwp 는, 한글에서 1회 '다른 이름으로 저장(HWPX)' 후
  검증된 ``hwpx_fill`` 경로를 쓰는 것을 권한다(한글 네이티브 저장은 무손실).

안전 원칙(불변)
---------------
- **원본 미수정**: out==in 이면 ValueError. 원본은 열어서 읽기만, 저장은 새 경로로.
- **날조 0**: identity 의 비어있지 않은 값만 입력한다.
- **COM 종속 정직 보고**: 한글 미설치/백그라운드 세션 등으로 COM 이 안 뜨면 예외 대신
  ``ok=False`` + 사람이 할 일을 담는다(거짓 성공 금지).
- AI 호출 없음 — 결정론.

매칭 지능은 ``cross_form_autofill`` 에서 재사용한다(단일 출처):
``_key``(라벨 정규화)·``_cluster_rep``(동의어 클러스터).
COM 객체 생성은 ``hwp_docx_convert._dispatch_hwp`` 를 재사용(테스트 monkeypatch 분리점).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .cross_form_autofill import _cluster_rep, _key
from .hwp_docx_convert import _dispatch_hwp, hancom_com_available
from .hwpx_fill import _same_file

_HWP_EXTS = {".hwp", ".hwpx"}


@dataclass
class HwpComFillReport:
    input: str
    output: str = ""
    ok: bool = False
    method: str = ""                                  # "hancom_com_field" | ""
    filled: dict[str, str] = field(default_factory=dict)   # 필드명→값
    fields_found: list[str] = field(default_factory=list)  # 양식의 누름틀 목록
    residual: list[str] = field(default_factory=list)      # 매칭 못 한 identity 라벨
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "ok": self.ok,
            "method": self.method,
            "filled": dict(self.filled),
            "fields_found": list(self.fields_found),
            "residual": list(self.residual),
            "notes": list(self.notes),
        }


def _parse_field_list(raw: Any) -> list[str]:
    """한글 GetFieldList 결과를 필드명 리스트로 정규화한다.

    한글은 필드 목록을 개행 또는 '\x02' 구분 문자열로 돌려준다. 누름틀 인스턴스는
    "이름{{0}}" 처럼 인덱스 접미가 붙을 수 있어 '{{' 앞부분만 취한다.
    """
    if raw is None:
        return []
    text = str(raw)
    if not text.strip():
        return []
    tokens = text.replace("\x02", "\n").replace("\r", "\n").split("\n")
    names: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        name = tok.split("{{", 1)[0].strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _match_field(field_name: str, wants: list[tuple[str, str, str]],
                 used: set[str]) -> Optional[tuple[str, str, str]]:
    """필드명에 대응하는 (want_key, 원라벨, 값) 을 찾는다(정확일치 또는 동의어 클러스터).

    이미 사용된 want_key 는 건너뛴다 — 같은 필드/클러스터에 값이 중복 기입되지 않게.
    """
    fkey = _key(field_name)
    if not fkey:
        return None
    frep = _cluster_rep(fkey)
    for want_key, lbl, val in wants:
        if want_key in used:
            continue
        if fkey == want_key or (frep is not None and frep == _cluster_rep(want_key)):
            return want_key, lbl, val
    return None


def fill_hwp_com(
    in_hwp: str | Path,
    out_hwp: str | Path,
    *,
    identity: Optional[dict[str, str]] = None,
    use_com: bool = True,
) -> HwpComFillReport:
    """바이너리 .hwp 양식의 누름틀에 한글 COM 으로 값만 입력하고 .hwp 로 저장한다.

    Args:
        in_hwp: 입력 .hwp/.hwpx(원본, 미수정).
        out_hwp: 출력 경로(.hwp/.hwpx). out==in 이면 ValueError.
        identity: 라벨→값(필드명과 정규화/동의어 매칭).
        use_com: False 면 COM 시도 없이 안내만(테스트/드라이런).

    Returns:
        HwpComFillReport — 채운 필드·발견 필드·잔여·COM 가용성 안내.
    """
    src = Path(in_hwp)
    dst = Path(out_hwp)
    report = HwpComFillReport(input=str(src), output=str(dst))
    identity = dict(identity or {})

    # 1) 안전장치
    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    if _same_file(src, dst):
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    if src.suffix.lower() not in _HWP_EXTS:
        raise ValueError(f"HWP/HWPX 입력만 지원합니다: {src.name}")
    if dst.suffix.lower() not in _HWP_EXTS:
        raise ValueError(f"출력은 .hwp/.hwpx 만 지원합니다: {dst.name}")

    wants = [
        (_key(lbl), lbl, str(val))
        for lbl, val in identity.items()
        if str(val or "").strip()
    ]

    # 2) COM 가용성 — 없으면 정직하게 안내만(거짓 성공 금지)
    if not use_com or not hancom_com_available():
        report.notes.append(
            "한글(Hancom Office) COM 을 사용할 수 없습니다 — 바이너리 .hwp 직접 채움은 "
            "한글 COM 으로만 가능합니다. 대안: 한글에서 양식을 '다른 이름으로 저장 → "
            "HWPX' 한 뒤 hwpx_fill(변환 왕복 없는 직접 채우기) 을 사용하세요.")
        if not wants:
            report.notes.append("입력할 값(identity)이 없습니다.")
        return report

    # 3) 한글 COM 으로 열어 누름틀 채움
    dst.parent.mkdir(parents=True, exist_ok=True)
    used_want_keys: set[str] = set()
    hwp = _dispatch_hwp()
    try:
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        try:
            hwp.SetMessageBoxMode(0x00000020)
        except Exception:
            pass

        if not hwp.Open(str(src), "", ""):
            if not hwp.Open(str(src), src.suffix.lstrip(".").upper(), ""):
                report.notes.append(f"한글에서 원본 열기 실패: {src}")
                return report

        report.fields_found = _parse_field_list(hwp.GetFieldList(0, 0))
        if not report.fields_found:
            report.notes.append(
                "이 양식에는 누름틀(필드)이 없습니다 — 표만 있는 .hwp 는 한글에서 "
                "HWPX 로 저장 후 hwpx_fill 경로를 권합니다(표 칸 직접 채움).")

        for fname in report.fields_found:
            matched = _match_field(fname, wants, used_want_keys)
            if matched is None:
                continue
            want_key, lbl, val = matched
            try:
                hwp.PutFieldText(fname, val)
                report.filled[fname] = val
                used_want_keys.add(want_key)
            except Exception as exc:  # 개별 필드 실패는 건너뛰고 계속
                report.notes.append(f"필드 '{fname}' 입력 실패: {type(exc).__name__}")

        # 4) 같은 형식(.hwp/.hwpx)으로 저장 — 원본 형식 보존
        save_fmt = {"hwp": "HWP", "hwpx": "HWPX"}[dst.suffix.lower().lstrip(".")]
        if not hwp.SaveAs(str(dst), save_fmt, ""):
            report.notes.append(f"한글 저장 실패: {dst}")
            return report

        report.ok = dst.exists() and dst.stat().st_size > 0
        # 저장은 됐지만 채운 필드가 0개면 '원본 복사'임을 정직히 구분(과대보고 금지).
        if report.ok:
            report.method = "hancom_com_field" if report.filled else "copied_no_fields"
            if not report.filled:
                report.notes.append(
                    "저장은 됐으나 입력된 필드가 없습니다 — 원본 복사본입니다"
                    "(매칭되는 누름틀 없음).")
        else:
            report.method = ""
    except Exception as exc:
        report.notes.append(
            f"한글 COM 채움 실패({type(exc).__name__}: {exc}) — 대화형 PowerShell 에서 "
            "다시 실행하고, 한글 '보안 승인' 대화상자가 뜨면 '허용'을 누르세요.")
        return report
    finally:
        try:
            hwp.Clear(1)
        except Exception:
            pass
        try:
            hwp.Quit()
        except Exception:
            pass

    # 잔여: 실제로 기입되지 않은 라벨(정직 보고) — 같은 클러스터 중복 라벨도 누락 노출.
    report.residual = [lbl for wk, lbl, _v in wants if wk not in used_want_keys]
    return report
