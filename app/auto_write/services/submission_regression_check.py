# -*- coding: utf-8 -*-
"""submission_regression_check — 제출 패키지 회귀 전수점검 (L077 잠금용 라이브러리+CLI).

스크립트 진입점은 ``scripts/submission_regression_check.py`` 가 이 모듈을 호출한다.
테스트는 PDF 없이 순수 헬퍼(find_pdf·parse_kv·text 매칭)를 검증한다.
"""
from __future__ import annotations

import argparse
import glob
import os
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CheckResult:
    fails: int = 0
    lines: list[str] = field(default_factory=list)

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        mark = "OK" if ok else "!! 회귀"
        if not ok:
            self.fails += 1
        self.lines.append(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")


def find_pdf(base: str, key: str) -> Optional[str]:
    """서류명 키워드로 폴더 안 PDF 파일을 찾는다."""
    hits = [p for p in glob.glob(os.path.join(base, "*.pdf")) if key in os.path.basename(p)]
    return hits[0] if hits else None


def parse_pages_spec(spec: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for item in filter(None, spec.split(",")):
        key, _, exp = item.partition("=")
        if key and exp:
            out.append((key, int(exp)))
    return out


def parse_text_spec(spec: str) -> list[tuple[str, list[str]]]:
    """'서류:값1|값2,...' → [(서류, [값…]), …]."""
    out: list[tuple[str, list[str]]] = []
    for item in filter(None, spec.split(",")):
        key, _, vals = item.partition(":")
        if not key:
            continue
        out.append((key, [v for v in vals.split("|") if v]))
    return out


def text_has_value(doc_text: str, value: str) -> bool:
    """공백 무시 부분문자열 매칭."""
    return value.replace(" ", "") in (doc_text or "").replace(" ", "")


def run_checks(
    *,
    directory: str,
    pages: str = "",
    require_image: str = "",
    require_text: str = "",
    forbid_text: str = "",
    zips: str = "",
    open_pdf: Optional[Callable] = None,
    pdf_text: Optional[Callable[[str], str]] = None,
    pdf_image_count: Optional[Callable[[str], int]] = None,
) -> CheckResult:
    """회귀 점검 실행. open_pdf/pdf_* 는 테스트용 주입점(기본 PyMuPDF)."""
    result = CheckResult()

    def _open(path: str):
        if open_pdf is not None:
            return open_pdf(path)
        import fitz  # type: ignore
        return fitz.open(path)

    def _text(path: str) -> str:
        if pdf_text is not None:
            return pdf_text(path)
        doc = _open(path)
        return "".join(pg.get_text() for pg in doc)

    def _images(path: str) -> int:
        if pdf_image_count is not None:
            return pdf_image_count(path)
        doc = _open(path)
        return sum(len(pg.get_images(full=True)) for pg in doc)

    for key, exp in parse_pages_spec(pages):
        path = find_pdf(directory, key)
        if path is None:
            result.check(False, f"{key} 파일 존재", "PDF 없음")
            continue
        n = len(_open(path))
        result.check(n == exp, f"{key} 페이지 {n} (기대 {exp})")

    for key in filter(None, require_image.split(",")):
        path = find_pdf(directory, key)
        if path is None:
            result.check(False, f"{key} 파일 존재", "PDF 없음")
            continue
        cnt = _images(path)
        result.check(cnt >= 1, f"{key} 서명 이미지 {cnt}개")

    for must, spec in ((True, require_text), (False, forbid_text)):
        for key, vals in parse_text_spec(spec):
            path = find_pdf(directory, key)
            if path is None:
                result.check(False, f"{key} 파일 존재", "PDF 없음")
                continue
            text = _text(path)
            for v in vals:
                found = text_has_value(text, v)
                if must:
                    result.check(found, f"{key} 필수값 '{v}'")
                else:
                    result.check(not found, f"{key} 금지값 '{v}' 없음")

    for item in filter(None, zips.split(",")):
        key, _, exp = item.partition("=")
        hits = [p for p in glob.glob(os.path.join(directory, "*.zip")) if key in os.path.basename(p)]
        if not hits:
            result.check(False, f"{key} zip 존재", "없음")
            continue
        n = len(zipfile.ZipFile(hits[0]).namelist())
        result.check(n == int(exp), f"{key} zip 파일 {n}개 (기대 {exp})")

    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="제출 패키지 회귀 전수점검 (exit 0=통과/2=회귀)")
    ap.add_argument("--dir", required=True, help="제출본 폴더")
    ap.add_argument("--pages", default="", help='"서류명=쪽수,..." 페이지 수 기대값')
    ap.add_argument("--require-image", default="", help="서명 등 이미지가 반드시 있어야 할 서류명(쉼표)")
    ap.add_argument("--require-text", default="", help='"서류명:값1|값2,..." 반드시 있어야 할 텍스트')
    ap.add_argument("--forbid-text", default="", help='"서류명:값1|값2,..." 있으면 안 되는 텍스트')
    ap.add_argument("--zip", dest="zips", default="", help='"zip이름키워드=파일수,..."')
    args = ap.parse_args(argv)

    result = run_checks(
        directory=args.dir,
        pages=args.pages,
        require_image=args.require_image,
        require_text=args.require_text,
        forbid_text=args.forbid_text,
        zips=args.zips,
    )
    for line in result.lines:
        print(line)
    print(f"\n결과: {'전부 통과' if result.fails == 0 else f'회귀 {result.fails}건'}")
    print("※ 굵기·정렬·서명 위치는 자동판정 불가 — 크롭 렌더 눈검증 병행(L005).")
    return 0 if result.fails == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
