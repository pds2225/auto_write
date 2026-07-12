r"""strip_notebooklm.py — 제출 직전, 문서에 남은 NotebookLM 작업용 블록을 제거한다.

apply_images 가 삽입한 슬라이드 프롬프트 블록(구분선·헤더·안내·프롬프트)을
usage_acceptance 의 self_inserted_blocks 검출과 같은 정의로 찾아 지운 사본을 만든다.
원본은 수정하지 않는다.

US-6 정책:
- 지우기 전에 프롬프트 본문을 <이름>_슬라이드프롬프트.md 로 보존한다(손실 0 —
  extract 와 strip 이 같은 식별 함수를 공유).
- 산출 이름은 수용검사 결과가 결정한다: 통과 시에만 '_제출용', fail 잔존 시 '_DRAFT'.
  ('_제출용_DRAFT' 같은 모순명 금지 — 검사 전 중립명 '_정리본' 사용)

사용법 (PowerShell):
    cd D:\auto_write\app
    python strip_notebooklm.py "문서.docx"            # 통과 → 문서_제출용.docx / fail → _DRAFT
    python strip_notebooklm.py "문서.docx" -o "제출본.docx"
    python strip_notebooklm.py "문서.docx" --no-gate  # 구 동작(검사·이름 게이팅 없음)

종료코드: 0 = 제출가능 / 2 = 제출불가(DRAFT) / 3 = 검사불능 (--no-gate 면 항상 0)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auto_write.services.image_apply import extract_notebooklm_prompts, strip_notebooklm_blocks
from auto_write.services.usage_acceptance import (
    backup_existing_output, force_draft_name, run_acceptance,
)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="NotebookLM 작업용 블록 제거(원본 보존) + 프롬프트 md 보존 + 수용검사 게이팅")
    parser.add_argument("docx", help="대상 DOCX 경로")
    parser.add_argument("-o", "--out", help="출력 경로(기본: 게이트 통과 시 <이름>_제출용.docx)")
    parser.add_argument("--no-gate", action="store_true",
                        help="수용검사 재검사·이름 게이팅 생략(구 동작)")
    args = parser.parse_args(argv)

    src = Path(args.docx)

    # 1) 프롬프트 보존(손실 0) — strip 과 같은 식별을 쓰므로 지워질 본문은 반드시 추출된다
    prompts = extract_notebooklm_prompts(str(src))
    if prompts:
        md = src.with_name(f"{src.stem}_슬라이드프롬프트.md")
        backup_existing_output(md)
        md.write_text("\n\n---\n\n".join(prompts), encoding="utf-8")
        print(f"프롬프트 보존: {md.name} ({len(prompts)}건)")

    # 2) 제거 — 사용자가 -o 를 지정하면 그 이름, 아니면 중립명(_정리본)
    out = Path(args.out) if args.out else src.with_name(f"{src.stem}_정리본{src.suffix}")
    report = strip_notebooklm_blocks(str(src), str(out))
    print(f"마커 단락 제거: {report.markers_removed}개 / 총 삭제 단락: {report.paragraphs_removed}개")
    if report.markers_removed == 0:
        print("(제거할 NotebookLM 블록이 없었습니다 — 사본만 생성)")
    if args.no_gate:
        print(f"저장: {out}")
        return 0

    # 3) 재검사 — 다른 fail 결함이 남아 있으면 '_제출용' 명명을 차단한다(LEDG-4)
    try:
        acc = run_acceptance(str(out))
    except Exception as exc:
        print(f"[오류] 검사 불능({type(exc).__name__}) — 판정 불가, 제출 금지")
        new_path, err = force_draft_name(out)
        print(f"저장: {new_path if not err else out}")
        return 3
    if acc.submittable:
        if args.out is None:
            final = src.with_name(f"{src.stem}_제출용{src.suffix}")
            backup_existing_output(final)
            out.replace(final)
            out = final
        print(f"수용검사: 제출가능 → {out.name}")
        print(f"저장: {out}")
        return 0
    new_path, err = force_draft_name(out)
    if not err:
        out = new_path
    print(f"수용검사: 제출불가 (fail {acc.fail_defects}건) → {out.name} — 결함 해결 전 제출 금지")
    for r in acc.results:
        if r.severity == "fail" and not r.passed:
            print(f"  · {r.label}: {r.detail}")
    print(f"저장: {out}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
