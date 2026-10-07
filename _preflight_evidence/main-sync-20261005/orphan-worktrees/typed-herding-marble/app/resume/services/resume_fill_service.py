"""resume_fill_service.py — 이력서 양식(HWPX) 자동 채움(신상정보 + 반복행 리스트).

범용 이력서 자동작성기 P2(M3). ``fill_resume_form`` 이 빈 양식 HWPX 와 프로필
(profile.json / ResumeProfile)을 받아 제출 가능한 HWPX 를 만든다.

두 종류의 채움을 결합한다:
1. **신상정보 라벨-값 칸** — 기존 ``hwpx_fill.fill_hwpx(identity=...)`` 를 그대로
   재사용한다(성명·연락처·이메일 등). 표준 키(name/phone/…)는 한국어 라벨로 변환.
2. **반복행 리스트 표** — ``resume_form_map`` 이 인식한 학력/경력/자격/강의/수행
   표의 빈 데이터행에 프로필 리스트를 순서대로 기입한다.

원칙(불변)
---------
- **원본 미수정**: out==in(하드링크·samefile 포함)이면 ValueError. 입력은 읽기만.
- **원본 1회 읽기·출력 1개**: 신상정보 채움(src→out) 후 반복행은 out 을 제자리 수정.
- **빈 셀만 채움**: 실값 셀은 덮지 않는다(``_cell_is_fillable`` 가드). run 텍스트만 교체.
- **날조 0**: 프로필에 있는 값만 기입. 빈 행이 부족하면 남은 항목을 '미수록'으로
  명시(침묵 절단 금지). 행 추가·병합 변경 금지(격자 훼손 방지).
- **격자 검증**: 채운 표는 ``validate_table_grid`` 로 확인. 실패면 ok=False + 사유.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from auto_write.services.hwpx_fill import (
    _SECTION_RE,
    _BlackCharPr,
    _cell_addr,
    _cell_is_fillable,
    _detect_standalone,
    _direct,
    _q,
    _same_file,
    _set_cell_text,
    _strip_linesegarray,
    fill_hwpx,
)
from auto_write.services.hwpx_layout_fix import validate_table_grid
from .resume_form_map import map_form_sections

__all__ = ["FillReport", "fill_resume_form"]

# 프로필 표준 identity 키 → 한국어 라벨(fill_hwpx 매칭용). fill_hwpx 가 동의어·장식
# 라벨을 정규화 매칭하므로 대표 라벨 1개면 충분하다.
_STD_TO_LABEL = {
    "name": "성명",
    "name_en": "성명(영문)",
    "org": "소속",
    "gender": "성별",
    "position": "직위",
    "phone": "연락처",
    "birth": "생년월일",
    "email": "이메일",
    "address_work": "주소(사업장)",
    "address_home": "주소",
    "field": "전문분야",
    "fax": "팩스",
}

# 반복행 섹션 kind → 한국어 이름(미수록 리포트용).
_KIND_LABEL = {
    "education": "학력", "career": "경력", "certs": "자격",
    "lectures": "강의", "projects": "수행", "trainings": "교육수료",
}


@dataclass
class FillReport:
    """양식 채움 결과."""

    out: str
    ok: bool = False
    sections: list = field(default_factory=list)   # [{kind, filled, total, overflow, empty_rows}]
    residual: list = field(default_factory=list)   # 행 부족으로 못 넣은 항목(미수록)
    identity_filled: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "out": self.out,
            "ok": self.ok,
            "sections": [dict(s) for s in self.sections],
            "residual": list(self.residual),
            "identity_filled": dict(self.identity_filled),
            "notes": list(self.notes),
        }


def _as_profile_dict(profile: Any) -> dict:
    """profile(dict | ResumeProfile | ProfileBuildResult) → 표준 dict."""
    if isinstance(profile, dict):
        return profile
    if hasattr(profile, "as_dict"):
        d = profile.as_dict()
        if isinstance(d, dict):
            return d
    raise TypeError("profile 은 dict 또는 as_dict() 를 가진 객체여야 합니다.")


def _identity_labels(identity: dict) -> dict:
    """표준 identity 키/값 → {한국어 라벨: 값}(빈 값 제외)."""
    out: dict[str, str] = {}
    for key, val in (identity or {}).items():
        if val is None or not str(val).strip():
            continue
        label = _STD_TO_LABEL.get(key, key)
        out.setdefault(label, str(val))
    return out


def _item_get(item: Any, field_name: str) -> Optional[str]:
    if isinstance(item, dict):
        return item.get(field_name)
    return getattr(item, field_name, None)


def _residual_desc(kind: str, item: Any,
                   reason: str = "양식 빈 행 부족(직접 추가 필요)") -> str:
    label = _KIND_LABEL.get(kind, kind)
    if isinstance(item, dict):
        parts = [str(v) for v in item.values() if v]
    else:
        parts = [str(item)]
    summary = " / ".join(parts[:3]) if parts else "(빈 항목)"
    return f"[미수록] {label}: {summary} — {reason}"


def _fill_row(tr, col_field_map: dict, item: Any, black: Optional[_BlackCharPr]) -> bool:
    """데이터행 tr 의 매핑 열에 item 값을 기입. 하나라도 채웠으면 True.

    빈(채움 가능) 셀에만 기입한다(실값 덮어쓰기 금지). 값이 없는 필드는 건너뛴다(날조0).
    """
    by_key: dict = {}
    for pos, tc in enumerate(_direct(tr, "tc")):
        addr = _cell_addr(tc)
        by_key[addr if addr is not None else pos] = tc
    wrote = False
    for colkey, field_name in col_field_map.items():
        tc = by_key.get(colkey)
        if tc is None:
            continue
        val = _item_get(item, field_name)
        if val is None or not str(val).strip():
            continue
        if not _cell_is_fillable(tc):
            continue  # 실값 셀·폼컨트롤 칸 — 덮어쓰기 금지
        if _set_cell_text(tc, str(val), black):
            wrote = True
    return wrote


def _fill_rows_inplace(
    path: Path, prof: dict, report: FillReport, normalize_black: bool
) -> None:
    """out HWPX(path)를 제자리로 열어 반복행 리스트 표를 채운다(원자적 재작성).

    path 를 메모리로 통째로 읽은 뒤 수정·재압축하므로 same-file 재작성이 안전하다.
    """
    with zipfile.ZipFile(path) as zin:
        infos = zin.infolist()
        data: dict[str, bytes] = {i.filename: zin.read(i.filename) for i in infos}

    header_name = "Contents/header.xml"
    black: Optional[_BlackCharPr] = None
    if normalize_black and header_name in data:
        try:
            black = _BlackCharPr(etree.fromstring(data[header_name]))
        except etree.XMLSyntaxError:
            black = None

    section_names = [i.filename for i in infos if _SECTION_RE.search(i.filename)]
    cursor: dict[str, int] = {}   # kind별 이미 소비한 프로필 항목 수(다중 표 캐스케이드)
    last_section_idx: dict[str, int] = {}  # kind → report.sections 내 마지막 표 인덱스
    changed_names: set[str] = set()
    grid_ok = True

    for name in section_names:
        try:
            root = etree.fromstring(data[name])
        except etree.XMLSyntaxError as exc:
            report.notes.append(f"{name} 파싱 실패(건너뜀): {exc}")
            continue
        sections = map_form_sections(root)
        if not sections:
            continue
        changed = False
        touched_tables: list = []
        for fs in sections:
            items = list(prof.get(fs.kind) or [])
            start = cursor.get(fs.kind, 0)
            remaining = items[start:]
            n_fill = min(len(remaining), len(fs.empty_rows))
            filled_here = 0
            for i in range(n_fill):
                if _fill_row(fs.empty_rows[i], fs.col_field_map, remaining[i], black):
                    filled_here += 1
            cursor[fs.kind] = start + n_fill
            report.sections.append({
                "kind": fs.kind,
                "filled": filled_here,
                "total": len(remaining),
                "overflow": 0,          # 최종값은 루프 뒤 kind 단위로 산정(이중계산 방지)
                "empty_rows": len(fs.empty_rows),
            })
            # 같은 kind 표가 여럿이면 뒤 표가 이어 채우므로 미수록은 표 단위로 세지
            # 않는다. 마지막 표 인덱스만 기억하고 전체 순회 뒤 kind 단위로 산정한다.
            last_section_idx[fs.kind] = len(report.sections) - 1
            if filled_here:
                changed = True
                touched_tables.append(fs.table)
        if not changed:
            continue
        # L074: 채운 표만 lineseg 제거(섹션 전역 strip 금지 — 안내박스 PDF 겹침 방지).
        _strip_linesegarray(root, only_under=touched_tables)
        for tbl in touched_tables:
            v = validate_table_grid(tbl)
            if not v.get("ok"):
                grid_ok = False
                report.notes.append(
                    f"{name} 표 격자 검증 실패(overlaps={v.get('overlaps')}, "
                    f"empties={v.get('empties')})")
        standalone = _detect_standalone(data[name])
        data[name] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=standalone)
        changed_names.add(name)

    # (전체 표 순회 종료 후) kind 단위 최종 미수록 산정 — 같은 kind 의 여러 표를 모두
    # 채운 뒤 남은 항목만 미수록으로 신고한다(표 단위 이중계산 방지).
    for kind, idx in last_section_idx.items():
        items = list(prof.get(kind) or [])
        leftover = items[cursor.get(kind, 0):]
        report.sections[idx]["overflow"] = len(leftover)
        for item in leftover:
            report.residual.append(_residual_desc(kind, item))

    report.ok = grid_ok
    if not changed_names:
        return

    # 검정 클론이 생겼으면 헤더도 갱신(기존 항목 불변·클론 추가만).
    if black is not None and black.changed and header_name in data:
        standalone = _detect_standalone(data[header_name])
        data[header_name] = etree.tostring(
            black.root, xml_declaration=True, encoding="UTF-8", standalone=standalone)

    # 원자적 재작성 — mimetype 선두+STORED, 그 외 원본 압축방식·순서 유지.
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.rowfill.tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            if "mimetype" in data:
                zi = zipfile.ZipInfo("mimetype")
                zi.compress_type = zipfile.ZIP_STORED
                zout.writestr(zi, data["mimetype"])
            for info in infos:
                nm = info.filename
                if nm == "mimetype":
                    continue
                zi = zipfile.ZipInfo(nm, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zout.writestr(zi, data[nm])
        os.replace(tmp, path)
    except BaseException:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def fill_resume_form(
    src_hwpx: str | Path,
    out_hwpx: str | Path,
    profile: Any,
    *,
    identity_fill: bool = True,
    normalize_black: bool = True,
) -> FillReport:
    """빈 이력서 양식(HWPX)을 프로필로 채워 제출 가능한 HWPX 를 만든다.

    Args:
        src_hwpx: 입력 빈 양식(.hwpx, 원본 절대 미수정).
        out_hwpx: 출력(.hwpx). out==in(하드링크 포함)이면 ValueError.
        profile: dict 또는 ResumeProfile/ProfileBuildResult(as_dict 보유).
                 형식: {"identity": {...}, "education": [...], "career": [...], ...}.
        identity_fill: True(기본)면 신상정보 라벨-값 칸을 fill_hwpx 로 먼저 채운다.
        normalize_black: True(기본)면 채운 값의 유색 예시체를 검정 클론으로 바꾼다.

    Returns:
        FillReport — 섹션별 채움 수·미수록·신상정보 채움·격자 검증(ok)·비고.
    """
    src = Path(src_hwpx)
    dst = Path(out_hwpx)
    report = FillReport(out=str(dst))
    prof = _as_profile_dict(profile)

    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    if _same_file(src, dst):
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    if src.suffix.lower() != ".hwpx":
        raise ValueError(f"HWPX 입력만 지원합니다: {src.name}")
    if dst.suffix.lower() != ".hwpx":
        raise ValueError(f"출력은 .hwpx 만 지원합니다: {dst.name}")
    if not zipfile.is_zipfile(src):
        raise ValueError(f"올바른 HWPX(ZIP)가 아닙니다: {src.name}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    # 1) 신상정보 라벨-값 채움(fill_hwpx 재사용, src→out). 없으면 원본 복사로 out 확보.
    identity_labels = _identity_labels(prof.get("identity") or {})
    if identity_fill and identity_labels:
        hrep = fill_hwpx(
            src, dst, identity=identity_labels, force_black=normalize_black)
        report.identity_filled = dict(hrep.filled)
        report.notes.extend(hrep.notes)
    else:
        shutil.copyfile(src, dst)

    # 2) 반복행 리스트 표 채움(out 제자리 수정).
    _fill_rows_inplace(dst, prof, report, normalize_black)

    # L046 연계: resume_extract 가 '과정 이수/수료'(교육수료)를 certs 에서 trainings 로
    # 분리했으나, 교육수료는 자격 표에 기재하지 않는다(L046). 반복행 표 매핑 대상도
    # 아니므로 침묵 유실을 막기 위해 profile 의 trainings 를 미수록으로 명시한다.
    for item in (prof.get("trainings") or []):
        report.residual.append(_residual_desc(
            "trainings", item,
            reason="이력서 양식에 교육수료 표 없음(자격과 별도, 직접 추가 필요)"))
    return report


def format_fill_korean(report: FillReport) -> str:
    """CLI 요약용 한국어 리포트."""
    lines = ["=== 이력서 양식 채움 결과 ===", f"출력: {report.out}"]
    if report.identity_filled:
        lines.append(f"신상정보 채움: {len(report.identity_filled)}개 "
                     f"({', '.join(report.identity_filled)})")
    if report.sections:
        lines.append("반복행 표:")
        for s in report.sections:
            extra = (f" · 빈행 {s['empty_rows']} · 미수록 {s['overflow']}"
                     if s["overflow"] else "")
            kname = _KIND_LABEL.get(s["kind"], s["kind"])
            lines.append(f"  · {kname}: {s['filled']}/{s['total']} 행 채움{extra}")
    else:
        lines.append("반복행 표: 인식된 리스트 표 없음")
    if report.residual:
        lines.append(f"⚠ 미수록 {len(report.residual)}건(양식 빈 행 부족):")
        for r in report.residual:
            lines.append(f"  - {r}")
    lines.append(f"격자 검증: {'통과' if report.ok else '실패'}")
    if report.notes:
        lines.append("비고:")
        for n in report.notes:
            lines.append(f"  · {n}")
    return "\n".join(lines)
