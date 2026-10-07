# -*- coding: utf-8 -*-
"""hwp_to_hwpx_batch — 코퍼스의 .hwp 양식을 한글 COM 으로 .hwpx 로 일괄 변환.

원본(.hwp)은 절대 수정하지 않는다(읽기 전용). 변환 결과는 별도 staging 폴더에
`NNN_<원본stem>.hwpx` 로 저장한다(같은 이름 충돌 방지 인덱스 접두).

기본은 '양식 후보'(신청서·사업계획서·서식·양식·계획서)만 변환한다 — 공고문까지
전부 변환하는 건 --all. 파일마다 한글을 새로 띄워(_convert_via_com) 한 파일 실패가
다음 파일에 전이되지 않게 한다(느리지만 견고). 진행상황을 즉시 출력(flush).

사용
----
    cd D:\\auto_write-wt-hwpxparity\\app
    py -3.11 tools/hwp_to_hwpx_batch.py "C:\\...\\00. 공고" -o D:\\auto_write-wt-hwpxparity\\_corpus_hwpx [--limit N] [--all]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auto_write.services.hwp_docx_convert import (  # noqa: E402
    _SAVE_FORMATS,
    _convert_via_com,
    hancom_com_available,
)

_FORM_RE = re.compile(r"신청서|사업계획서|서식|양식|계획서|신청양식|참가신청|지원서|제출서류")


def _safe_stem(src: Path, idx: int) -> str:
    stem = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", src.stem)[:60]
    return f"{idx:03d}_{stem}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=".hwp 양식 → .hwpx 일괄 변환(한글 COM)")
    ap.add_argument("folder", help="원본 폴더(재귀 탐색)")
    ap.add_argument("-o", "--out", required=True, help="변환 결과 staging 폴더")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--all", action="store_true", help="양식뿐 아니라 모든 .hwp 변환")
    args = ap.parse_args(argv)

    folder = Path(args.folder)
    out_dir = Path(args.out)
    if not folder.is_dir():
        print(f"폴더가 아닙니다: {folder}", file=sys.stderr)
        return 2
    if not hancom_com_available():
        print("HANGUL_COM_NONE: 한글 COM 미설치 — 변환 불가", file=sys.stderr)
        return 3

    files = sorted(p for p in folder.rglob("*.hwp")
                   if args.all or _FORM_RE.search(p.name))
    if args.limit:
        files = files[:args.limit]
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"대상 .hwp: {len(files)}개  →  {out_dir}", flush=True)
    ok = fail = 0
    for i, src in enumerate(files, 1):
        dst = out_dir / f"{_safe_stem(src, i)}.hwpx"
        try:
            _convert_via_com(src, dst, _SAVE_FORMATS[".hwpx"])
            if dst.exists() and dst.stat().st_size > 0:
                ok += 1
                print(f"[{i}/{len(files)}] OK   {src.name}", flush=True)
            else:
                fail += 1
                print(f"[{i}/{len(files)}] FAIL(빈파일) {src.name}", flush=True)
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(files)}] FAIL {src.name}: "
                  f"{type(exc).__name__}: {str(exc)[:80]}", flush=True)

    print(f"\nDONE  ok={ok}  fail={fail}  total={len(files)}  out={out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
