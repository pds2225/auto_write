"""hwpx_self_diagnose — HWPX 제출 가능성·L규칙 게이팅 (읽기 전용).

종료코드: 0=제출가능(경고 가능) / 1=입력오류 / 2=제출불가 / 3=검사불능
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from auto_write.services.hwpx_fill_coverage import score_hwpx_coverage
from auto_write.services.hwpx_form_extract import looks_like_notice_blob
from auto_write.services.hancom_com_guard import snapshot_hancom_com


@dataclass
class GateItem:
    rule: str
    status: str  # pass|fail|warn
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "status": self.status, "detail": self.detail}


@dataclass
class HwpxDiagnoseReport:
    path: str
    ok: bool = False
    gates: list[GateItem] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ok": self.ok,
            "gates": [g.as_dict() for g in self.gates],
            "coverage": self.coverage,
            "notes": self.notes,
        }


def diagnose_hwpx(path: str | Path, *, require_specialty_checked: bool = False) -> HwpxDiagnoseReport:
    p = Path(path)
    rep = HwpxDiagnoseReport(path=str(p))
    if not p.is_file():
        rep.gates.append(GateItem("input", "fail", "파일 없음"))
        return rep
    if p.suffix.lower() != ".hwpx":
        rep.gates.append(GateItem("input", "fail", f"HWPX 아님: {p.suffix}"))
        return rep

    try:
        with zipfile.ZipFile(p) as z:
            blob = "".join(
                z.read(n).decode("utf-8", "replace")
                for n in z.namelist()
                if "section" in n and n.endswith(".xml")
            )
    except Exception as exc:
        rep.gates.append(GateItem("zip", "fail", str(exc)))
        rep.notes.append("검사불능")
        return rep

    # L037 서식만
    if looks_like_notice_blob(blob):
        rep.gates.append(GateItem("L037", "fail", "공고 본문 잔존(모집공고/수당 등)"))
    else:
        rep.gates.append(GateItem("L037", "pass", "서식 위주"))

    # 플레이스홀더
    ph = []
    if "(yyyy/mm/dd)" in blob:
        ph.append("(yyyy/mm/dd)")
    if re.search(r"년\s+월\s+\(졸업", blob):
        ph.append("학력 플레이스홀더")
    if ph:
        rep.gates.append(GateItem("L024", "warn", "잔여 플레이스홀더: " + ", ".join(ph)))
    else:
        rep.gates.append(GateItem("L024", "pass", "학력/날짜 플레이스홀더 없음"))

    # 인적 최소
    for kw in ("성명", "박다솜"):  # 일반화: 성명 칸에 값이 있는지는 coverage로
        pass
    cov = score_hwpx_coverage(p)
    rep.coverage = cov.as_dict()
    human = next((s for s in cov.sections if s.name == "인적"), None)
    if human and human.filled >= 3:
        rep.gates.append(GateItem("인적", "pass", f"filled={human.filled}"))
    else:
        rep.gates.append(
            GateItem("인적", "fail", f"채움 부족 filled={getattr(human, 'filled', 0)}")
        )

    specialty = next((s for s in cov.sections if s.name == "모집분야"), None)
    if specialty and specialty.filled == 0:
        if require_specialty_checked:
            rep.gates.append(GateItem("L034", "fail", "모집분야 미체크·confirm 필요"))
        else:
            rep.gates.append(GateItem("L034", "warn", "모집분야 미체크(confirm 후 체크)"))
    elif specialty and specialty.filled > 0:
        rep.gates.append(GateItem("L034", "pass", f"checked={specialty.filled}"))

    # L061/L062 — 환경 게이트(파일과 무관, 참고)
    snap = snapshot_hancom_com()
    if snap.hwpframe_is_2024:
        rep.gates.append(GateItem("L062", "warn", "COM이 HOffice130(2024) — Dispatch 차단됨"))
    elif snap.hwpframe_is_2022:
        rep.gates.append(GateItem("L062", "pass", "COM=HOffice120"))
    else:
        rep.gates.append(GateItem("L062", "warn", f"COM={snap.hwpframe_localserver32!r}"))

    fails = [g for g in rep.gates if g.status == "fail"]
    rep.ok = len(fails) == 0
    return rep


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="HWPX 자가진단·L규칙 게이트")
    ap.add_argument("hwpx", help="진단할 .hwpx")
    ap.add_argument("--json", dest="json_out", help="결과 JSON 경로")
    ap.add_argument(
        "--require-specialty",
        action="store_true",
        help="모집분야 체크 필수(미체크=fail)",
    )
    args = ap.parse_args(argv)
    src = Path(args.hwpx)
    if not src.exists():
        print(f"입력 오류: {src}", file=sys.stderr)
        return 1
    try:
        rep = diagnose_hwpx(src, require_specialty_checked=args.require_specialty)
    except Exception as exc:
        print(f"검사불능: {exc}", file=sys.stderr)
        return 3

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(rep.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"=== HWPX 진단: {src.name} ===")
    print(f"ok={rep.ok} overall_rate={rep.coverage.get('overall_rate')}")
    for g in rep.gates:
        print(f"  [{g.status}] {g.rule}: {g.detail}")
    for s in rep.coverage.get("sections") or []:
        print(f"  coverage {s['name']}: {s['filled']}/{s['total']} ({s['rate']})")

    if any("검사불능" in n for n in rep.notes):
        return 3
    return 0 if rep.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
