# -*- coding: utf-8 -*-
"""제출 패키지 회귀 전수점검 게이트 (범용) — "이전 버전엔 됐는데 지금은 안 되는 것" 자동 탐지.

■ 왜 필요한가 (오답노트 L077, 2026-07-23 사용자 의무화)
  산출물을 다시 만들 때마다(버전 재생성) 직전 확정판에서 되던 것이 조용히
  사라질 수 있다 — 실제 사례: 서명 누락 의심, 소제목 굵게·안내상자 삭제 소실(L075).
  그래서 재생성 후에는 이 점검을 **의무**로 돌려 통과해야 "완성"이라 말할 수 있다.

■ 무엇을 점검하나
  · 각 PDF 의 페이지 수가 기대값과 같은가
  · 서명(이미지)이 들어가야 할 PDF 에 실제로 이미지가 있는가
  · 있어야 할 텍스트(팀명·성명·연락처·날짜 등)가 있는가
  · 있으면 안 되는 텍스트(❑·☞ 안내상자, [확인필요]·OOO 마커)가 없는가
  · ZIP 안 파일 개수가 맞는가
  ※ 굵기·정렬 같은 시각 속성은 자동으로 못 잡는다(변환기가 글자를 쪼개 저장) —
    반드시 크롭 렌더 눈검증을 병행하라(L005).

■ 사용 예 (2026 온랩 실전 옵션)
  py -3.11 -X utf8 scripts\submission_regression_check.py --dir "온랩\온랩_전달패키지\제출본" `
    --pages "참가신청서=1,사업계획서=5,상금및지원금=1,개인정보수집이용동의서=1,참가서약서=1" `
    --require-image "참가신청서,참가서약서,개인정보수집이용동의서" `
    --require-text "참가신청서:마켓게이트|박다솜|010-2930-6666|pds2225@naver.com|2026년7월24일" `
    --forbid-text "사업계획서:❑|☞|[확인필요]|OOO|010-0000" `
    --zip "기타서류=3"
  exit 0 = 전부 통과 / exit 2 = 회귀 발견(항목별 !! 표시)
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import zipfile

import fitz  # PyMuPDF


def find_pdf(base: str, key: str) -> str | None:
    """서류명 키워드(예: 사업계획서)로 폴더 안 PDF 파일을 찾습니다."""
    hits = [p for p in glob.glob(os.path.join(base, "*.pdf")) if key in os.path.basename(p)]
    return hits[0] if hits else None


def main() -> int:
    ap = argparse.ArgumentParser(description="제출 패키지 회귀 전수점검 (exit 0=통과/2=회귀)")
    ap.add_argument("--dir", required=True, help="제출본 폴더")
    ap.add_argument("--pages", default="", help='"서류명=쪽수,..." 페이지 수 기대값')
    ap.add_argument("--require-image", default="", help="서명 등 이미지가 반드시 있어야 할 서류명(쉼표)")
    ap.add_argument("--require-text", default="", help='"서류명:값1|값2,..." 반드시 있어야 할 텍스트(공백 무시 비교)')
    ap.add_argument("--forbid-text", default="", help='"서류명:값1|값2,..." 있으면 안 되는 텍스트')
    ap.add_argument("--zip", dest="zips", default="", help='"zip이름키워드=파일수,..."')
    args = ap.parse_args()

    fails = 0

    def check(ok: bool, label: str, detail: str = "") -> None:
        nonlocal fails
        mark = "OK" if ok else "!! 회귀"
        if not ok:
            fails += 1
        print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")

    # 1) 페이지 수
    for item in filter(None, args.pages.split(",")):
        key, _, exp = item.partition("=")
        path = find_pdf(args.dir, key)
        if path is None:
            check(False, f"{key} 파일 존재", "PDF 없음")
            continue
        n = len(fitz.open(path))
        check(n == int(exp), f"{key} 페이지 {n} (기대 {exp})")

    # 2) 서명(이미지) 존재
    for key in filter(None, args.require_image.split(",")):
        path = find_pdf(args.dir, key)
        if path is None:
            check(False, f"{key} 파일 존재", "PDF 없음")
            continue
        cnt = sum(len(pg.get_images(full=True)) for pg in fitz.open(path))
        check(cnt >= 1, f"{key} 서명 이미지 {cnt}개")

    # 3) 있어야 할 텍스트 / 4) 있으면 안 되는 텍스트 (공백 무시 비교)
    def doc_text(key: str) -> str | None:
        path = find_pdf(args.dir, key)
        if path is None:
            return None
        return "".join(pg.get_text() for pg in fitz.open(path)).replace(" ", "")

    for spec, must in [(args.require_text, True), (args.forbid_text, False)]:
        for item in filter(None, spec.split(",")):
            key, _, vals = item.partition(":")
            text = doc_text(key)
            if text is None:
                check(False, f"{key} 파일 존재", "PDF 없음")
                continue
            for v in filter(None, vals.split("|")):
                found = v.replace(" ", "") in text
                if must:
                    check(found, f"{key} 필수값 '{v}'")
                else:
                    check(not found, f"{key} 금지값 '{v}' 없음")

    # 5) ZIP 파일 수
    for item in filter(None, args.zips.split(",")):
        key, _, exp = item.partition("=")
        hits = [p for p in glob.glob(os.path.join(args.dir, "*.zip")) if key in os.path.basename(p)]
        if not hits:
            check(False, f"{key} zip 존재", "없음")
            continue
        n = len(zipfile.ZipFile(hits[0]).namelist())
        check(n == int(exp), f"{key} zip 파일 {n}개 (기대 {exp})")

    print(f"\n결과: {'전부 통과' if fails == 0 else f'회귀 {fails}건'}")
    print("※ 굵기·정렬·서명 위치는 자동판정 불가 — 크롭 렌더 눈검증 병행(L005).")
    return 0 if fails == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
