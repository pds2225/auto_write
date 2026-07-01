"""hwpx_fill.py — HWPX 원본 양식을 '변환 왕복 없이' 직접 채우는 결정론 엔진.

목적 / 배경
-----------
정부지원사업 양식은 대개 HWP/HWPX 다. 기존 경로(``hwp_fill``)는
HWPX→DOCX→채움→DOCX→HWP 로 **변환을 왕복**하기 때문에 표·서식·이미지가
미세하게 틀어질 수 있었다(변환 일치도 100% 미달 = 평생개발목표 진행 중).

이 모듈은 변환을 전혀 하지 않는다. HWPX 가 본질적으로 ZIP(OWPML XML) 이라는 점을
이용해, 압축을 풀고 ``Contents/section*.xml`` 의 **값 칸 텍스트(hp:t)만** 바꾼 뒤
다시 압축한다. 표 구조·셀 속성·테두리/채우기·글꼴(header.xml)·이미지(BinData) 는
**한 바이트도 건드리지 않는다** → 원본 양식 100% 보존 + 값만 입력.

OWPML 표 구조(실측)
-------------------
``hp:tbl > hp:tr > hp:tc``. 각 ``hp:tc`` 는 ``hp:cellAddr``(colAddr/rowAddr)·
``hp:cellSpan``(colSpan/rowSpan) + ``hp:subList > hp:p > hp:run > hp:t``(텍스트).
값 칸은 **라벨 칸의 colAddr+colSpan 위치**(논리 그리드 오른쪽 이웃)로 찾는다 —
병합셀(colSpan>1)·다열(라벨-값-라벨-값) 양식에서도 엉뚱한 칸을 안 채운다.

안전 원칙(불변)
---------------
- **원본 미수정**: out==in 이면 ValueError. ``os.path.samefile``(inode) 로 하드링크·
  심링크·대소문자·상대경로 우회까지 차단. 입력 ZIP 은 읽기만 한다.
- **원자적 쓰기**: 임시파일에 쓰고 성공 시 ``os.replace`` 로 교체 — 중간 실패가
  기존 출력 파일을 손상시키지 않는다.
- **양식 보존**: 값 칸의 ``hp:t`` 텍스트만 수정. 그 외 모든 ZIP 엔트리는 내용 동일.
  mimetype 은 ZIP 선두 + 무압축(STORED) 으로 유지(HWPX 유효성 요건).
- **날조 0**: 사용자가 준 identity/replacements 값만 입력한다. 없으면 안 채운다.
- **덮어쓰기 금지**: 비었거나 '명백한 예시 플레이스홀더'인 칸에만 입력한다.
  실제 값이 든 칸·라벨 칸은 절대 덮지 않는다(오매칭<빈칸<덮어쓰기).
  replacements(직접 치환)도 채울 수 있는 칸 안에서만 적용한다(라벨/실값 보호).
- AI 호출 없음 — 동일 입력, 동일 결과(결정론).

매칭 지능은 ``cross_form_autofill`` 에서 그대로 가져온다(단일 출처):
``_key``·``_cluster_rep``·``_is_obvious_placeholder``·``_is_noise_label``.
"""

from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from .cross_form_autofill import (
    _cluster_rep,
    _is_noise_label,
    _is_obvious_placeholder,
    _key,
)

# OWPML 단락 네임스페이스(본문/표/텍스트 전부 hp:).
_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_STANDALONE_RE = re.compile(rb"standalone\s*=\s*['\"](yes|no)['\"]")


def _q(tag: str) -> str:
    return f"{{{_HP}}}{tag}"


def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _direct(el, name: str) -> list:
    """el 의 '직계' 자식 중 local-name 이 name 인 것."""
    return [c for c in el if _local(getattr(c, "tag", "")) == name]


def _cell_texts(tc) -> list:
    """셀 안의 모든 hp:t 요소(순서대로)."""
    return [el for el in tc.iter(_q("t"))]


def _cell_text(tc) -> str:
    """셀의 표시 텍스트(hp:t 결합, 공백 정규화)."""
    parts = [str(el.text or "") for el in _cell_texts(tc)]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _int_attr(el, name: str, default: int) -> int:
    if el is None:
        return default
    try:
        return int(str(el.get(name)))
    except (TypeError, ValueError):
        return default


def _cell_addr(tc) -> Optional[int]:
    """셀의 논리 열 위치(colAddr). cellAddr 미지정이면 None."""
    ca = next(iter(_direct(tc, "cellAddr")), None)
    if ca is None:
        return None
    return _int_attr(ca, "colAddr", -1) if ca.get("colAddr") is not None else None


def _cell_colspan(tc) -> int:
    cs = next(iter(_direct(tc, "cellSpan")), None)
    return _int_attr(cs, "colSpan", 1)


def _row_of(tc):
    """tc 의 조상 hp:tr."""
    cur = tc.getparent()
    while cur is not None:
        if _local(getattr(cur, "tag", "")) == "tr":
            return cur
        cur = cur.getparent()
    return None


def _inherit_charpr(tc) -> str:
    """빈 칸에 run 을 새로 만들 때 승계할 charPrIDRef.

    같은 행의 기존 run 글자속성을 재사용해 양식 폰트를 보존한다. 없으면 '0'.
    """
    row = _row_of(tc)
    scope = row if row is not None else tc
    for run in scope.iter(_q("run")):
        ref = run.get("charPrIDRef")
        if ref:
            return ref
    return "0"


def _set_cell_text(tc, value: str) -> bool:
    """셀의 텍스트를 value 로 설정한다(첫 hp:t 에 기입, 나머지 hp:t 는 비움).

    빈/플레이스홀더 칸에만 호출되므로 잔여 hp:t 를 비워도 실데이터 손실은 없다.
    hp:t/hp:run 이 없으면 단락 서식(charPrIDRef 승계)을 유지하며 최소 생성한다.
    """
    paras = list(tc.iter(_q("p")))
    if not paras:
        return False
    p = paras[0]
    ts = _cell_texts(tc)
    if ts:
        ts[0].text = value
        for extra in ts[1:]:
            extra.text = ""
        return True
    runs = list(p.iter(_q("run")))
    if runs:
        run = runs[0]
    else:
        run = etree.SubElement(p, _q("run"))
        run.set("charPrIDRef", _inherit_charpr(tc))
    t = etree.SubElement(run, _q("t"))
    t.text = value
    return True


def _cell_is_fillable(tc) -> bool:
    """그 칸에 값을 넣어도 되는가 — 비었거나 '명백한 예시 플레이스홀더'면 True.

    이미 실제 값이 있으면 False(덮어쓰기 금지). 빈칸 외에는 _is_obvious_placeholder
    (불가능 날짜·전부-0 수량·더미 등록번호)만 채울 대상으로 본다(O마스크 제외).
    """
    txt = _cell_text(tc)
    if not txt:
        return True
    return _is_obvious_placeholder(txt)


def _is_label_like(tc) -> bool:
    """그 칸이 값칸이 아니라 '라벨/안내' 칸으로 보이면 True(값 기입 금지 대상)."""
    txt = _cell_text(tc)
    if not txt:
        return False
    norm = _key(txt)
    return _cluster_rep(norm) is not None or _is_noise_label(txt, norm)


def _in_protected_cell(t) -> bool:
    """hp:t 가 '채울 수 없는'(라벨·실값) 표 셀 안에 있으면 True(치환 보호 대상).

    가장 가까운 조상 hp:tc 를 찾아 _cell_is_fillable 로 판정한다. 표 밖(본문)
    텍스트는 보호하지 않는다. id() 대신 조상 순회라 lxml proxy 재사용 영향 없음.
    """
    cur = t.getparent()
    while cur is not None:
        if _local(getattr(cur, "tag", "")) == "tc":
            return not _cell_is_fillable(cur)
        cur = cur.getparent()
    return False


def _label_matches(cell_key: str, want_key: str) -> bool:
    """정규화 라벨 cell_key 가 want_key 와 같은 항목인가(정확일치 또는 동의어 클러스터)."""
    if not cell_key or not want_key:
        return False
    if cell_key == want_key:
        return True
    rep_c = _cluster_rep(cell_key)
    rep_w = _cluster_rep(want_key)
    return rep_c is not None and rep_c == rep_w


def _value_cell(label_tc, cells: list):
    """라벨 칸의 값 칸을 찾는다 — cellAddr 우선(병합 안전), 없으면 위치 i+1 폴백.

    cellAddr 이 있으면 colAddr+colSpan 위치의 셀만 값칸으로 인정한다. 그 위치 셀이
    없으면(가로병합으로 사라졌거나 행 끝) None 을 돌려 '엉뚱한 칸 채움'을 차단한다.
    """
    addr = _cell_addr(label_tc)
    if addr is not None:
        want_col = addr + _cell_colspan(label_tc)
        for tc in cells:
            if _cell_addr(tc) == want_col:
                return tc
        return None  # 병합 등으로 값칸 위치가 비어있음 — 보수적으로 스킵
    # cellAddr 미지정 양식 — 위치 인덱스 폴백
    try:
        idx = cells.index(label_tc)
    except ValueError:
        return None
    return cells[idx + 1] if idx + 1 < len(cells) else None


@dataclass
class HwpxFillReport:
    input: str
    output: str = ""
    ok: bool = False
    filled: dict[str, str] = field(default_factory=dict)   # 채운 라벨→값
    filled_count: int = 0
    replaced: int = 0
    residual: list[str] = field(default_factory=list)      # 매칭 못 한 identity 라벨
    sections_changed: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "ok": self.ok,
            "filled": dict(self.filled),
            "filled_count": self.filled_count,
            "replaced": self.replaced,
            "residual": list(self.residual),
            "sections_changed": self.sections_changed,
            "notes": list(self.notes),
        }


def _fill_section_xml(
    xml_bytes: bytes,
    identity: dict[str, str],
    replacements: dict[str, str],
) -> tuple[bytes, dict[str, str], int, set[str]]:
    """한 섹션 XML 에서 표 라벨-값 칸 채움 + (보호된) 직접 치환을 수행한다.

    반환: (새 XML 바이트, 채운 라벨→값, 치환건수, 채운 identity 라벨키 집합).
    변경이 없으면 입력 바이트를 그대로 반환한다(불필요한 재직렬화·선언 변형 회피).
    """
    root = etree.fromstring(xml_bytes)
    filled: dict[str, str] = {}
    used_keys: set[str] = set()
    replaced = 0
    changed = False

    wants = [
        (_key(lbl), lbl, val)
        for lbl, val in identity.items()
        if str(val or "").strip()
    ]

    # 1) 표 라벨→값 칸 채움 (cellAddr 기반 값칸 선택 + 라벨칸 보호)
    for tbl in root.iter(_q("tbl")):
        for tr in _direct(tbl, "tr"):
            cells = _direct(tr, "tc")
            for tc in cells:
                cell_key = _key(_cell_text(tc))
                if not cell_key:
                    continue
                for want_key, lbl, val in wants:
                    if want_key in used_keys:
                        continue
                    if not _label_matches(cell_key, want_key):
                        continue
                    target = _value_cell(tc, cells)
                    if target is None or target is tc:
                        continue
                    if _is_label_like(target):
                        continue  # 값칸 후보가 또 라벨 → 기입 금지
                    if not _cell_is_fillable(target):
                        continue  # 실제 값 있는 칸 — 덮어쓰기 금지
                    if _set_cell_text(target, str(val)):
                        filled[lbl] = str(val)
                        used_keys.add(want_key)
                        changed = True
                    break

    # 2) 직접 텍스트 치환 — 라벨/실값 칸은 보호(채울 수 있는 칸·본문에만 적용).
    #    lxml proxy id 재사용을 피하려 id() 집합 대신 조상(tc) 순회로 판별한다.
    if replacements:
        for t in root.iter(_q("t")):
            cur = str(t.text or "")
            if not cur:
                continue
            if _in_protected_cell(t):       # 라벨·실값 칸의 hp:t 보호
                continue
            new = cur
            for old, rep in replacements.items():
                if old and str(rep or "").strip() and old in new:
                    new = new.replace(old, str(rep))
            if new != cur:
                t.text = new
                replaced += 1
                changed = True

    if not changed:
        return xml_bytes, filled, replaced, used_keys

    standalone = _detect_standalone(xml_bytes)
    out = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=standalone
    )
    return out, filled, replaced, used_keys


def _detect_standalone(xml_bytes: bytes) -> Optional[bool]:
    """원본 XML 선언의 standalone 값을 보존(yes→True/no→False/없음→None)."""
    m = _STANDALONE_RE.search(xml_bytes[:200])
    if not m:
        return None
    return m.group(1) == b"yes"


def _same_file(src: Path, dst: Path) -> bool:
    """src·dst 가 같은 실파일인가 — inode 비교(하드링크 포함)까지 잡는다."""
    try:
        if src.exists() and dst.exists() and os.path.samefile(src, dst):
            return True
    except OSError:
        pass
    return src.resolve() == dst.resolve()


def fill_hwpx(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    *,
    identity: Optional[dict[str, str]] = None,
    replacements: Optional[dict[str, str]] = None,
) -> HwpxFillReport:
    """HWPX 원본 양식의 빈 값 칸을 직접 채운다(변환 왕복 없음, 양식 100% 보존).

    Args:
        in_hwpx: 입력 HWPX(원본, 절대 미수정).
        out_hwpx: 출력 HWPX(.hwpx). out==in(하드링크 포함)이면 ValueError.
        identity: 라벨→값. 예: {"기업명": "도보네비게이션(주)", "대표자": "홍길동"}.
                  동의어(상호/회사명 …)·표 라벨 장식(○·1.)은 자동 정규화 매칭.
        replacements: 직접 치환 {예시토큰: 실제값}. 라벨/실값 칸은 보호된다(선택).

    Returns:
        HwpxFillReport — 채운 항목·치환수·잔여(미매칭 라벨)·변경 섹션수.
    """
    src = Path(in_hwpx)
    dst = Path(out_hwpx)
    report = HwpxFillReport(input=str(src), output=str(dst))

    identity = dict(identity or {})
    replacements = dict(replacements or {})

    # 1) 안전장치
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

    # 2) ZIP 전체를 읽어 들인다(엔트리 순서·압축방식·내용 보존용).
    with zipfile.ZipFile(src) as zin:
        infos = zin.infolist()
        data: dict[str, bytes] = {i.filename: zin.read(i.filename) for i in infos}

    section_names = [i.filename for i in infos if _SECTION_RE.search(i.filename)]
    if not section_names:
        report.notes.append("Contents/section*.xml 을 찾지 못했습니다(빈 양식?).")

    # 3) 섹션 XML 만 채움/치환
    all_used: set[str] = set()
    for name in section_names:
        try:
            new_bytes, filled, replaced, used = _fill_section_xml(
                data[name], identity, replacements
            )
        except etree.XMLSyntaxError as exc:
            report.notes.append(f"{name} 파싱 실패(건너뜀): {exc}")
            continue
        if new_bytes != data[name]:
            data[name] = new_bytes
            report.sections_changed += 1
        report.filled.update(filled)
        report.replaced += replaced
        all_used |= used

    report.filled_count = len(report.filled)
    report.residual = [
        lbl
        for lbl, val in identity.items()
        if str(val or "").strip() and _key(lbl) not in all_used
    ]

    # 4) 원자적 쓰기 — 임시파일에 다시 압축 후 os.replace.
    #    mimetype 선두 + STORED, 그 외 원본 압축방식·내용 유지.
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.stem}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            if "mimetype" in data:
                zi = zipfile.ZipInfo("mimetype")
                zi.compress_type = zipfile.ZIP_STORED
                zout.writestr(zi, data["mimetype"])
            for info in infos:
                name = info.filename
                if name == "mimetype":
                    continue
                zi = zipfile.ZipInfo(name, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zout.writestr(zi, data[name])
        os.replace(tmp, dst)
    except BaseException:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise

    report.ok = True
    if not report.filled and not report.replaced:
        report.notes.append(
            "채운 칸이 없습니다 — 라벨이 양식과 일치하지 않거나 칸에 이미 값이 "
            "있을 수 있습니다(덮어쓰기 금지). identity 라벨/값을 확인하세요.")
    return report
