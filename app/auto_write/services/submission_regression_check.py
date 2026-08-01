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


def _pdf_page_count(path: str, open_pdf: Optional[Callable]) -> int:
    if open_pdf is not None:
        return len(open_pdf(path))
    import fitz  # type: ignore
    return len(fitz.open(path))


def _pdf_flags_summary(path: str, open_pdf: Optional[Callable] = None) -> dict[str, int]:
    """L075: dict 텍스트 플래그로 굵기(bold) 스팬 수를 집계(이월 체크용).

    PyMuPDF ``get_text('dict')`` 의 span.flags bit4 = bold. 주입 open_pdf 가
    페이지에 get_text 를 제공하면 그걸 쓰고, 없으면 0.
    """
    bold_spans = 0
    try:
        if open_pdf is not None:
            doc = open_pdf(path)
        else:
            import fitz  # type: ignore
            doc = fitz.open(path)
        for pg in doc:
            get_text = getattr(pg, "get_text", None)
            if get_text is None:
                continue
            try:
                d = get_text("dict")
            except TypeError:
                continue
            for block in (d or {}).get("blocks", []) or []:
                for line in block.get("lines", []) or []:
                    for span in line.get("spans", []) or []:
                        flags = int(span.get("flags") or 0)
                        if flags & 2 ** 4:  # bold
                            bold_spans += 1
    except Exception:
        return {"bold_spans": 0}
    return {"bold_spans": bold_spans}


def compare_to_baseline(
    *,
    current_dir: str,
    baseline_dir: str,
    keys: str = "",
    open_pdf: Optional[Callable] = None,
    pdf_text: Optional[Callable[[str], str]] = None,
    pdf_image_count: Optional[Callable[[str], int]] = None,
    check_bold: bool = True,
) -> CheckResult:
    """L075: 직전 확정판(baseline) 대비 현재 산출물 이월 점검.

    서류 키워드마다 페이지 수·본문 길이(안내삭제 과다)·이미지 수·(가능하면) 볼드
    스팬 수를 대조한다. keys 비우면 현재 폴더 PDF 파일명 키워드를 자동 사용.
    """
    result = CheckResult()

    def _text(path: str) -> str:
        if pdf_text is not None:
            return pdf_text(path)
        if open_pdf is not None:
            doc = open_pdf(path)
            return "".join(getattr(pg, "get_text", lambda: "")() for pg in doc)
        import fitz  # type: ignore
        doc = fitz.open(path)
        return "".join(pg.get_text() for pg in doc)

    def _images(path: str) -> int:
        if pdf_image_count is not None:
            return pdf_image_count(path)
        if open_pdf is not None:
            doc = open_pdf(path)
            total = 0
            for pg in doc:
                get_images = getattr(pg, "get_images", None)
                if get_images is not None:
                    total += len(get_images(full=True))
            return total
        import fitz  # type: ignore
        doc = fitz.open(path)
        return sum(len(pg.get_images(full=True)) for pg in doc)

    key_list = [k for k in keys.split(",") if k]
    if not key_list:
        # 현재 폴더 PDF 파일명(확장자 제외)을 키로 — 동일 키워드로 baseline 조회
        for p in glob.glob(os.path.join(current_dir, "*.pdf")):
            stem = os.path.splitext(os.path.basename(p))[0]
            # 너무 긴 stem 은 앞 토큰만(서류명 키워드로 쓰기)
            key_list.append(stem.split("_")[0] if "_" in stem else stem)

    seen: set[str] = set()
    for key in key_list:
        if key in seen:
            continue
        seen.add(key)
        cur = find_pdf(current_dir, key)
        base = find_pdf(baseline_dir, key)
        if cur is None:
            result.check(False, f"{key} 현재 파일", "PDF 없음")
            continue
        if base is None:
            result.check(False, f"{key} 기준(확정판) 파일", "baseline PDF 없음")
            continue

        n_cur = _pdf_page_count(cur, open_pdf)
        n_base = _pdf_page_count(base, open_pdf)
        result.check(n_cur == n_base, f"{key} 페이지 이월", f"현재 {n_cur} / 확정 {n_base}")

        t_cur = _text(cur)
        t_base = _text(base)
        # 안내문구 과삭제: 본문이 확정판의 70% 미만이면 회귀 의심
        len_cur = len((t_cur or "").replace(" ", ""))
        len_base = len((t_base or "").replace(" ", ""))
        if len_base > 0:
            ratio = len_cur / len_base
            result.check(
                ratio >= 0.70,
                f"{key} 본문량 이월(안내삭제 과다 방지)",
                f"현재/확정={ratio:.2f} ({len_cur}/{len_base})",
            )
        else:
            result.check(True, f"{key} 본문량 이월", "확정판 본문 비어 있음 — skip")

        img_cur = _images(cur)
        img_base = _images(base)
        # 서명 등 이미지가 확정판에 있으면 현재도 최소 동일 수
        if img_base > 0:
            result.check(
                img_cur >= img_base,
                f"{key} 이미지 수 이월",
                f"현재 {img_cur} / 확정 {img_base}",
            )
        else:
            result.check(True, f"{key} 이미지 수 이월", f"확정 0 · 현재 {img_cur}")

        if check_bold:
            b_cur = _pdf_flags_summary(cur, open_pdf)["bold_spans"]
            b_base = _pdf_flags_summary(base, open_pdf)["bold_spans"]
            if b_base > 0:
                # 볼드가 확정판에 있으면 현재도 최소 절반 이상(폰트위계 이월)
                result.check(
                    b_cur >= max(1, b_base // 2),
                    f"{key} 볼드 스팬 이월",
                    f"현재 {b_cur} / 확정 {b_base}",
                )
            else:
                result.check(True, f"{key} 볼드 스팬 이월", f"확정 0 · 현재 {b_cur}")

    if not key_list:
        result.check(False, "비교 대상", "현재 폴더에 PDF 없음")
    return result


def run_checks(
    *,
    directory: str,
    pages: str = "",
    require_image: str = "",
    require_text: str = "",
    forbid_text: str = "",
    zips: str = "",
    baseline_dir: str = "",
    baseline_keys: str = "",
    open_pdf: Optional[Callable] = None,
    pdf_text: Optional[Callable[[str], str]] = None,
    pdf_image_count: Optional[Callable[[str], int]] = None,
) -> CheckResult:
    """회귀 점검 실행. open_pdf/pdf_* 는 테스트용 주입점(기본 PyMuPDF).

    baseline_dir 이 주어지면 L075 직전확정판 대비 모드를 추가로 실행한다.
    """
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

    if baseline_dir:
        base_res = compare_to_baseline(
            current_dir=directory,
            baseline_dir=baseline_dir,
            keys=baseline_keys,
            open_pdf=open_pdf,
            pdf_text=pdf_text,
            pdf_image_count=pdf_image_count,
        )
        result.fails += base_res.fails
        result.lines.extend(base_res.lines)

    return result


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="제출 패키지 회귀 전수점검 (exit 0=통과/2=회귀)")
    ap.add_argument("--dir", required=True, help="제출본 폴더")
    ap.add_argument("--pages", default="", help='"서류명=쪽수,..." 페이지 수 기대값')
    ap.add_argument("--require-image", default="", help="서명 등 이미지가 반드시 있어야 할 서류명(쉼표)")
    ap.add_argument("--require-text", default="", help='"서류명:값1|값2,..." 반드시 있어야 할 텍스트')
    ap.add_argument("--forbid-text", default="", help='"서류명:값1|값2,..." 있으면 안 되는 텍스트')
    ap.add_argument("--zip", dest="zips", default="", help='"zip이름키워드=파일수,..."')
    ap.add_argument(
        "--baseline-dir",
        default="",
        help="L075: 직전 확정판 폴더 — 페이지·본문량·이미지·볼드 이월 대조",
    )
    ap.add_argument(
        "--baseline-keys",
        default="",
        help='L075: 비교할 서류명 키워드(쉼표). 비우면 현재 폴더 PDF 자동',
    )
    args = ap.parse_args(argv)

    result = run_checks(
        directory=args.dir,
        pages=args.pages,
        require_image=args.require_image,
        require_text=args.require_text,
        forbid_text=args.forbid_text,
        zips=args.zips,
        baseline_dir=args.baseline_dir,
        baseline_keys=args.baseline_keys,
    )
    for line in result.lines:
        print(line)
    print(f"\n결과: {'전부 통과' if result.fails == 0 else f'회귀 {result.fails}건'}")
    print("※ 굵기·정렬·서명 위치는 자동판정 불가 — 크롭 렌더 눈검증 병행(L005).")
    return 0 if result.fails == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
