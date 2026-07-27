# -*- coding: utf-8 -*-
"""HWPX 작성영역 스타일 복원 도구 (범용) — 어떤 정부양식에도 쓸 수 있습니다.

■ 이 스크립트가 하는 일 (쉽게 말하면)
  값을 다 채운 한글 파일(HWPX)에서, 지정한 구간(예: 붙임1 사업계획서)의
  ① 작성 안내용 상자(☞·❑ 같은 기호로 시작하는 점선 박스)를 지우고
  ② 소제목(예: 1-1. 2-3.)을 굵게 + 원하는 크기로 바꿉니다.
  나머지(신청서·다른 붙임·본문 내용·표·체크박스)는 건드리지 않습니다.

■ 사용 예 (PowerShell — 2026 온랩에서 실제로 쓴 옵션)
  py -3.11 -X utf8 scripts\hwpx_restyle_writing_area.py 입력.hwpx 출력.hwpx `
      --region-start 붙임1 --region-end 붙임2 `
      --delete-guide-prefixes "☞,❑" --subhead-pattern "^\\d-\\d\\." `
      --subhead-pt 12 --subhead-bold

■ 서식 크기를 정하는 규칙 (오답노트 L008, 2026-07-23 사용자 확정)
  1순위 = 공고·양식 작성요령이 명시한 기준(예: "글자 크기 12pt")
  2순위 = 사용자 지정 위계(소제목 14pt 등, 공고가 침묵할 때만)

■ 과거 실수에서 배운 안전장치 (오답노트)
  · 새 글자 스타일은 목록 "맨 끝"에만 추가 — 중간에 끼우면 문서 전체 서식이
    한 칸씩 밀려 깨집니다(L076, 실제 사고).
  · 원본의 줄배치 정보(lineseg)는 지우지 않습니다 — 지우면 rhwp PDF 변환에서
    안내 상자 글자가 겹칩니다(L074). 이 도구는 lineseg 를 전혀 건드리지 않습니다.
  · 원본 파일은 절대 덮어쓰지 않습니다(입력=출력이면 에러).
  · 실행 후에는 반드시 hwpx_doctor 진단 + PDF 렌더 눈검증까지 하세요(L005).
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import sys
import zipfile
from collections import Counter

from lxml import etree

# 한글 파일(HWPX) 내부 XML 이 쓰는 이름표(네임스페이스)
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"   # 본문(문단) 쪽
HH = "http://www.hancom.co.kr/hwpml/2011/head"        # 서식 정의(헤더) 쪽
NS = {"hp": HP, "hh": HH}


def ptext(p) -> str:
    """문단 안의 글자만 이어붙여 돌려줍니다(어떤 문단인지 알아보는 용도)."""
    return "".join(t.text or "" for t in p.findall(".//hp:t", NS)).strip()


def norm(s: str) -> str:
    """공백을 지워 비교하기 쉽게 만듭니다."""
    return s.replace(" ", "")


def add_bold_charpr(header_xml: bytes, base_id: str, height: int) -> tuple[bytes, str]:
    """서식 정의(header.xml)에 '굵은 소제목' 스타일을 새로 등록하고 새 번호를 돌려줍니다.

    base_id 스타일(보통 본문 스타일)을 복제해 크기만 바꾸고 굵게 표시를 넣습니다.
    ⚠ 반드시 목록 맨 끝에 추가합니다 — 중간에 끼우면 번호=순서 정렬이 깨져
      문서 전체 서식이 밀립니다(L076).
    """
    hroot = etree.fromstring(header_xml)
    props = hroot.find(".//hh:charProperties", NS)
    base = next((cp for cp in props if cp.get("id") == base_id), None)
    if base is None:
        raise SystemExit(f"기준 글자 스타일 charPr id={base_id} 를 찾지 못했습니다.")
    new_id = str(max(int(cp.get("id")) for cp in props) + 1)
    clone = copy.deepcopy(base)
    clone.set("id", new_id)
    clone.set("height", str(height))
    # "굵게" 요소를 규격상 올바른 자리(offset 또는 fontRef 뒤)에 넣습니다.
    bold = etree.SubElement(clone, f"{{{HH}}}bold")
    clone.remove(bold)
    anchor = clone.find("hh:offset", NS)
    if anchor is None:
        anchor = clone.find("hh:fontRef", NS)
    anchor.addnext(bold)
    props.append(clone)                       # ← 맨 끝 추가(핵심)
    props.set("itemCnt", str(len(props)))     # 개수 표기를 안 맞추면 파일 손상 판정
    out = etree.tostring(hroot, xml_declaration=True, encoding="UTF-8", standalone=True)
    return out, new_id


def main() -> int:
    ap = argparse.ArgumentParser(description="HWPX 작성영역 안내상자 삭제 + 소제목 굵게/크기 (범용)")
    ap.add_argument("src", help="입력 HWPX (원본은 수정하지 않음)")
    ap.add_argument("dst", help="출력 HWPX (새 파일)")
    ap.add_argument("--region-start", default=None, help="구간 시작 제목(예: 붙임1). 생략 시 문서 처음부터")
    ap.add_argument("--region-end", default=None, help="구간 끝 제목(예: 붙임2). 생략 시 문서 끝까지")
    ap.add_argument("--delete-guide-prefixes", default="",
                    help='삭제할 안내상자 시작 기호(쉼표 구분, 예: "☞,❑"). 표 컨테이너 문단만 지움. 빈값이면 삭제 안 함')
    ap.add_argument("--subhead-pattern", default=None,
                    help=r'소제목 정규식(예: "^\d-\d\."). 생략하면 소제목 서식 변경 안 함')
    ap.add_argument("--subhead-pt", type=float, default=12.0,
                    help="소제목 크기 pt (기본 12 — 1순위 공고 명시, 2순위 사용자 위계로 결정할 것)")
    ap.add_argument("--subhead-bold", action="store_true", help="소제목 굵게")
    ap.add_argument("--base-charpr", default="auto",
                    help="복제 기반 글자 스타일 id. auto = 소제목 문단들이 쓰는 최빈값 자동 선택")
    ap.add_argument("--blank-before-subheads", action="store_true",
                    help="소제목이 바뀔 때 빈 줄 1개 추가(단, 큰 제목 바로 다음 소제목 앞에는 안 넣음)")
    ap.add_argument("--hanging-indent", default="",
                    help='내어쓰기 지정 "기호=단위,기호=단위" (예: "ㅇ=1800,-=2400"). '
                         "해당 기호로 시작하는 문단의 둘째 줄부터를 첫 줄 텍스트 시작에 맞춘다"
                         "(한글 shift+tab 과 동일). 단위=1/7200인치, 12pt 전각 1자≈1200")
    args = ap.parse_args()

    # 원본 보호: 입력과 출력이 같은 파일이면 중단합니다.
    if os.path.exists(args.dst) and os.path.samefile(args.src, args.dst):
        raise SystemExit("입력과 출력이 같은 파일입니다 — 원본 덮어쓰기 금지.")

    with zipfile.ZipFile(args.src) as z:
        names = z.namelist()
        payload = {n: z.read(n) for n in names}

    root = etree.fromstring(payload["Contents/section0.xml"])
    top = [p for p in root if p.tag == f"{{{HP}}}p"]

    # 대상 구간(시작 제목 ~ 끝 제목)을 잡습니다. 못 찾으면 즉시 에러(엉뚱한 곳 수정 방지).
    b1 = 0
    b2 = len(top)
    if args.region_start:
        b1 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_start)))
    if args.region_end:
        b2 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_end)))

    # ① 안내상자 삭제 — 지정 기호로 시작하고 표(상자)를 품은 문단만
    removed = 0
    prefixes = tuple(s for s in args.delete_guide_prefixes.split(",") if s)
    if prefixes:
        for p in top[b1:b2]:
            t = ptext(p)
            if t.startswith(prefixes) and p.findall(".//hp:tbl", NS):
                root.remove(p)
                removed += 1
    print(f"① 안내상자 삭제: {removed}개 (기호={','.join(prefixes) if prefixes else '없음'})")

    # ② 소제목 굵게/크기
    sub = 0
    if args.subhead_pattern:
        top = [p for p in root if p.tag == f"{{{HP}}}p"]
        b1 = 0
        b2 = len(top)
        if args.region_start:
            b1 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_start)))
        if args.region_end:
            b2 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_end)))
        targets = [p for p in top[b1:b2] if re.match(args.subhead_pattern, ptext(p))]
        if not targets:
            raise SystemExit("소제목 정규식에 걸린 문단이 0개 — 패턴을 확인하세요.")
        # 기반 스타일 결정: auto 면 소제목들이 지금 쓰는 스타일 중 최빈값(=그 문서의 본문 스타일)
        if args.base_charpr == "auto":
            cnt = Counter(r.get("charPrIDRef") for p in targets for r in p.findall("hp:run", NS))
            base_id = cnt.most_common(1)[0][0]
        else:
            base_id = args.base_charpr
        payload["Contents/header.xml"], new_id = add_bold_charpr(
            payload["Contents/header.xml"], base_id, int(args.subhead_pt * 100))
        if not args.subhead_bold:
            print("  (참고: --subhead-bold 없이 크기만 바꾸는 경우도 새 스타일에 굵게가 들어갑니다"
                  " — 굵게 원치 않으면 알려주세요)")
        for p in targets:
            for run in p.findall("hp:run", NS):
                run.set("charPrIDRef", new_id)
            sub += 1
        print(f"② 소제목 {sub}개 → 새 스타일 charPr {new_id} ({args.subhead_pt:g}pt, 기반 id {base_id})")

    # ③ 소제목 앞 빈 줄 — 문단 덩어리가 눈에 잘 들어오게(사용자 확정 2026-07-23)
    blanks = 0
    if args.blank_before_subheads and args.subhead_pattern:
        top = [p for p in root if p.tag == f"{{{HP}}}p"]
        b1 = 0
        b2 = len(top)
        if args.region_start:
            b1 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_start)))
        if args.region_end:
            b2 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_end)))
        # 빈 줄로 쓸 틀: 문서에 이미 있는 "빈 문단"을 복제(서식 일관·안전)
        tmpl = next((p for p in top if not ptext(p)
                     and not p.findall(".//hp:tbl", NS) and not p.findall(".//hp:pic", NS)), None)
        if tmpl is None:
            raise SystemExit("빈 문단 틀을 찾지 못했습니다 — 빈 줄 추가 불가.")
        for p in list(top[b1:b2]):
            if not re.match(args.subhead_pattern, ptext(p)):
                continue
            idx = top.index(p)
            prev_txt = ""
            for q in reversed(top[b1:idx]):          # 바로 위 '내용 있는' 문단을 찾는다
                if ptext(q):
                    prev_txt = ptext(q)
                    break
                else:
                    prev_txt = ""                     # 바로 위가 이미 빈 줄이면 중복 삽입 안 함
                    break
            # 큰 제목(예: "1. 문제인식") 바로 다음 소제목 앞에는 빈 줄을 넣지 않는다
            if prev_txt and not (re.match(r"^\d+\.", prev_txt) and not re.match(args.subhead_pattern, prev_txt)):
                blank = copy.deepcopy(tmpl)
                for seg in blank.findall(".//hp:linesegarray", NS):   # 복제본의 낡은 줄배치 캐시 제거
                    seg.getparent().remove(seg)
                p.addprevious(blank)
        blanks = sum(1 for _ in ())  # 아래에서 다시 센다
        top2 = [p for p in root if p.tag == f"{{{HP}}}p"]
        blanks = len(top2) - len(top)
        print(f"③ 소제목 앞 빈 줄 {blanks}개 추가")

    # ④ 내어쓰기(hanging indent) — 둘째 줄부터 첫 줄 텍스트 시작 위치에 정렬(한글 shift+tab)
    if args.hanging_indent:
        hroot2 = etree.fromstring(payload["Contents/header.xml"])
        pprops = hroot2.find(".//hh:paraProperties", NS)
        top = [p for p in root if p.tag == f"{{{HP}}}p"]
        b1 = 0
        b2 = len(top)
        if args.region_start:
            b1 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_start)))
        if args.region_end:
            b2 = next(i for i, p in enumerate(top) if norm(ptext(p)).startswith(norm(args.region_end)))
        rules = []
        for item in args.hanging_indent.split(","):
            mark, _, val = item.partition("=")
            rules.append((mark, int(val)))
        made = {}   # 들여쓰기값 -> 새 paraPr id (같은 값이면 스타일 재사용)
        applied = Counter()
        for p in top[b1:b2]:
            t = ptext(p)
            if not t or re.match(args.subhead_pattern or r"$^", t):
                continue
            for mark, unit in rules:
                if not t.startswith(mark):
                    continue
                if unit not in made:
                    base_pid = p.get("paraPrIDRef")
                    base_pp = next(pp for pp in pprops if pp.get("id") == base_pid)
                    npp = copy.deepcopy(base_pp)
                    nid = str(max(int(pp.get("id")) for pp in pprops) + 1)
                    npp.set("id", nid)
                    # 왼쪽여백 = unit, 첫줄들여쓰기 = -unit → 첫 줄만 원위치(=내어쓰기)
                    for el in npp.iter():
                        tag = etree.QName(el).localname
                        if tag == "left":
                            el.set("value", str(unit))
                        elif tag == "intent":
                            el.set("value", str(-unit))
                    pprops.append(npp)                     # ⚠ 반드시 맨 끝(L076 — charPr 와 동일 원리)
                    pprops.set("itemCnt", str(len(pprops)))
                    made[unit] = nid
                p.set("paraPrIDRef", made[unit])
                applied[mark] += 1
                break
        payload["Contents/header.xml"] = etree.tostring(
            hroot2, xml_declaration=True, encoding="UTF-8", standalone=True)
        print(f"④ 내어쓰기 적용: " + ", ".join(f"'{m}' {n}개" for m, n in applied.items())
              + f" (새 문단 스타일 {len(made)}종)")

    # 저장 — mimetype 만은 무압축이 규격(압축하면 한글이 파일을 거부)
    payload["Contents/section0.xml"] = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(args.dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            if n == "mimetype":
                zout.writestr(n, payload[n], compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(n, payload[n])
    print(f"→ {args.dst}")
    print("다음 단계: hwpx_doctor 진단 + rhwp export-pdf 렌더 눈검증을 꼭 하세요(L005·L074).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
