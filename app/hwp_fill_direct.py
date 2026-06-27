"""hwp_fill_direct.py — 원본 HWP/HWPX 양식을 '변환 왕복 없이' 직접 채우는 CLI.

원본 양식을 훼손하지 않고 값만 입력한다(원본 미수정·날조0·덮어쓰기금지).

  - .hwpx  → hwpx_fill.fill_hwpx     (변환 없이 ZIP/XML 직접, 한글 불필요)
  - .hwp   → hwp_com_fill.fill_hwp_com(한글 COM 누름틀, 한글 설치 PC 필요)

사용 예 (PowerShell):
  py -3.11 hwp_fill_direct.py 양식.hwpx -o 결과.hwpx --set "기업명=도보네비게이션(주)" --set "대표자=홍길동"
  py -3.11 hwp_fill_direct.py 양식.hwp  -o 결과.hwp  --identity identity.json
  py -3.11 hwp_fill_direct.py 양식.hwpx -o 결과.hwpx --replace "EXAMPLE=실제값"

identity.json 형식: {"기업명": "...", "대표자": "...", "주소": "..."}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# app/ 를 import 기준으로 (이 파일이 app/ 에 있음)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_write.services.hwp_com_fill import fill_hwp_com  # noqa: E402
from auto_write.services.hwpx_fill import fill_hwpx  # noqa: E402


def _parse_kv(items: list[str]) -> dict[str, str]:
    """['라벨=값', ...] → {라벨: 값}. '=' 없는 항목은 건너뛴다."""
    out: dict[str, str] = {}
    for it in items or []:
        if "=" not in it:
            print(f"  (무시) '=' 없는 항목: {it}", file=sys.stderr)
            continue
        k, v = it.split("=", 1)
        if k.strip():
            out[k.strip()] = v
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="원본 HWP/HWPX 양식을 변환 왕복 없이 직접 채운다(원본 미수정·날조0).")
    ap.add_argument("input", help="입력 양식(.hwpx 또는 .hwp)")
    ap.add_argument("-o", "--output", help="출력 경로(미지정 시 <원본>_채움.<확장자>)")
    ap.add_argument("--set", dest="sets", action="append", default=[],
                    metavar="라벨=값", help="라벨-값 직접 지정(반복 가능)")
    ap.add_argument("--identity", help="라벨-값 JSON 파일 경로")
    ap.add_argument("--replace", dest="replaces", action="append", default=[],
                    metavar="옛값=새값", help="직접 텍스트 치환(.hwpx 전용, 반복 가능)")
    ap.add_argument("--no-com", action="store_true",
                    help=".hwp 라도 COM 시도 없이 안내만(드라이런)")
    args = ap.parse_args(argv)

    # Windows 콘솔(cp949)에서 한글·기호 출력이 깨지거나 죽지 않도록 UTF-8 강제.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    src = Path(args.input)
    if not src.exists():
        print(f"[오류] 입력 파일이 없습니다: {src}", file=sys.stderr)
        return 1
    ext = src.suffix.lower()
    if ext not in {".hwp", ".hwpx"}:
        print(f"[오류] .hwp/.hwpx 만 지원합니다: {src.name}", file=sys.stderr)
        return 1

    identity: dict[str, str] = {}
    if args.identity:
        try:
            identity.update(json.loads(Path(args.identity).read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"[오류] identity JSON 읽기 실패: {exc}", file=sys.stderr)
            return 1
    identity.update(_parse_kv(args.sets))  # --set 이 JSON 보다 우선

    out = Path(args.output) if args.output else src.with_name(f"{src.stem}_채움{ext}")
    if out.resolve() == src.resolve():
        print("[오류] 출력이 입력과 같습니다(원본 덮어쓰기 금지).", file=sys.stderr)
        return 1

    if ext == ".hwpx":
        try:
            rep = fill_hwpx(src, out, identity=identity,
                            replacements=_parse_kv(args.replaces))
        except (ValueError, FileNotFoundError, OSError) as exc:
            print(f"[실패] {exc}", file=sys.stderr)
            return 2
        print(f"방식: HWPX 직접 채우기(변환 없음)")
        print(f"채운 칸: {rep.filled_count}  치환: {rep.replaced}  변경 섹션: {rep.sections_changed}")
        for lbl, val in rep.filled.items():
            print(f"  [v] {lbl} = {val}")
        if rep.residual:
            print(f"  남은 라벨(양식에 칸 없음/이미 값 있음): {', '.join(rep.residual)}")
        for n in rep.notes:
            print(f"  · {n}")
        print(f"출력: {rep.output}  (성공={rep.ok})")
        return 0 if rep.ok else 2

    # .hwp → COM
    try:
        rep2 = fill_hwp_com(src, out, identity=identity, use_com=not args.no_com)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"[실패] {exc}", file=sys.stderr)
        return 2
    print(f"방식: 한글 COM 누름틀 채우기")
    if rep2.fields_found:
        print(f"발견한 누름틀: {', '.join(rep2.fields_found)}")
    for fname, val in rep2.filled.items():
        print(f"  [v] {fname} = {val}")
    if rep2.residual:
        print(f"  남은 라벨: {', '.join(rep2.residual)}")
    for n in rep2.notes:
        print(f"  · {n}")
    print(f"출력: {rep2.output}  (성공={rep2.ok})")
    return 0 if rep2.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
