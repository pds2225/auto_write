"""hwpx_submit.py — HWPX 양식 채움→수용검사 게이트→제출본 완성 원-커맨드 CLI.

fill_hwpx(채움) 뒤 run_hwpx_acceptance(게이트)로 판정하고, fail/검사불능이면
force_draft_name 으로 ``_DRAFT`` 를 강제한다(fail-closed — 제출 이름 세탁 금지).

사용 예 (PowerShell):
  py -3.11 hwpx_submit.py 양식.hwpx -o 결과.hwpx --identity identity.json
  py -3.11 hwpx_submit.py 양식.hwpx -o 결과.hwpx --set "기업명=도보네비게이션(주)" --set "대표자=홍길동"
  py -3.11 hwpx_submit.py 양식.hwpx -o 결과.hwpx --replace "예시토큰=실제값" --no-acceptance

identity.json 형식: {"기업명": "...", "대표자": "...", "주소": "..."}

종료코드: 0=제출가능 / 1=입력오류(파일없음·채울 값 없음 등) /
          2=제출불가(_DRAFT) / 3=검사불능(fail-closed _DRAFT)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# app/ 를 import 기준으로 (이 파일이 app/ 에 있음)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_write.services.hwpx_submit import submit_hwpx  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="HWPX 양식을 채우고 수용검사 게이트로 판정해 제출본을 완성한다"
                    "(원본 미수정·날조0·fail-closed).")
    ap.add_argument("input", help="입력 양식(.hwpx)")
    ap.add_argument("-o", "--output", help="출력 경로(미지정 시 <원본>_제출.hwpx)")
    ap.add_argument("--identity", help="라벨-값 JSON 파일 경로")
    ap.add_argument("--set", dest="sets", action="append", default=[],
                    metavar="라벨=값", help="라벨-값 직접 지정(반복 가능)")
    ap.add_argument("--replace", dest="replaces", action="append", default=[],
                    metavar="예시=실제", help="직접 텍스트 치환(반복 가능)")
    ap.add_argument("--no-acceptance", action="store_true",
                    help="수용검사 게이트 생략(이름 유지 — 제출 전 별도 점검 필요)")
    ap.add_argument("--no-normalize-colors", action="store_true",
                    help="잔존 예시 유색체 자동 검정화 생략(기본은 검정 정규화 ON)")
    ap.add_argument("--no-submission-cleanup", action="store_true",
                    help="제출 cleanup(안내문구·lineseg·유색) 생략 — 기본 ON")
    args = ap.parse_args(argv)

    # Windows 콘솔(cp949)에서 한글·기호 출력이 깨지거나 죽지 않도록 UTF-8 강제.
    from auto_write.utils import force_utf8_console
    force_utf8_console()

    src = Path(args.input)
    if not src.exists():
        print(f"[입력오류] 입력 파일이 없습니다: {src}", file=sys.stderr)
        return 1

    identity: dict[str, str] = {}
    if args.identity:
        try:
            identity.update(
                json.loads(Path(args.identity).read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"[입력오류] identity JSON 읽기 실패: {exc}", file=sys.stderr)
            return 1
    from auto_write.utils import parse_kv
    identity.update(parse_kv(args.sets))   # --set 이 JSON 보다 우선
    replacements = parse_kv(args.replaces)

    if not identity and not replacements:
        print("[입력오류] 채울 값이 없습니다 — --identity JSON 또는 "
              "--set 라벨=값 을 지정하세요(빈 제출 방지).", file=sys.stderr)
        return 1

    out = Path(args.output) if args.output else src.with_name(f"{src.stem}_제출.hwpx")

    try:
        rep = submit_hwpx(src, out, identity=identity, replacements=replacements,
                          acceptance_gate=not args.no_acceptance,
                          normalize_colors=not args.no_normalize_colors,
                          submission_cleanup=not args.no_submission_cleanup)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"[입력오류] {exc}", file=sys.stderr)
        return 1

    # 사람용 요약: 채운 칸·잔여·게이트 판정·최종 파일명.
    print(f"채운 칸: {len(rep.filled)}")
    for lbl, val in rep.filled.items():
        print(f"  [v] {lbl} = {val}")
    if rep.residual:
        print(f"  남은 라벨(양식에 칸 없음/이미 값 있음): {', '.join(rep.residual)}")
    for n in rep.notes:
        print(f"  · {n}")

    acc = rep.acceptance
    if args.no_acceptance:
        print("게이트: 생략(--no-acceptance) — 제출 전 별도 점검 필요")
    elif acc.get("exception"):
        print(f"게이트: 검사불능 → fail-closed(_DRAFT 강제): {acc['exception']}")
    else:
        print(f"게이트 판정: {acc.get('verdict', '?')} "
              f"(유색 {acc.get('colored', 0)}·안내문구 {acc.get('guides', 0)}"
              f"·linesegarray {acc.get('linesegarray', 0)})")
    if rep.draft_reason:
        print(f"  사유: {rep.draft_reason}")
    if rep.error:
        print(f"  [경고] {rep.error}", file=sys.stderr)
    print(f"최종 파일: {rep.final}  (제출가능={rep.ok})")

    if rep.ok:
        return 0
    if acc.get("exception"):
        return 3    # 검사불능(fail-closed — 파일은 _DRAFT 로 강제됨)
    return 2        # 제출불가(_DRAFT)


if __name__ == "__main__":
    raise SystemExit(main())
