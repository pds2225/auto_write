"""strip_notebooklm.py — 제출 직전, 문서에 남은 NotebookLM 작업용 블록을 제거한다.

apply_images 가 삽입한 슬라이드 프롬프트 블록(구분선·헤더·안내·프롬프트)을
usage_acceptance 의 self_inserted_blocks 검출과 같은 정의로 찾아 지운 '제출용 사본'을
만든다. 원본은 수정하지 않는다.

사용법 (PowerShell):
    cd D:\auto_write\app
    python strip_notebooklm.py "문서.docx"                  # → 문서_제출용.docx
    python strip_notebooklm.py "문서.docx" -o "제출본.docx"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auto_write.services.image_apply import strip_notebooklm_blocks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NotebookLM 작업용 블록 제거(원본 보존, 제출용 사본 생성)")
    parser.add_argument("docx", help="대상 DOCX 경로")
    parser.add_argument("-o", "--out", help="출력 경로(기본: <이름>_제출용.docx)")
    args = parser.parse_args(argv)

    src = Path(args.docx)
    out = Path(args.out) if args.out else src.with_name(f"{src.stem}_제출용{src.suffix}")
    report = strip_notebooklm_blocks(str(src), str(out))

    print(f"마커 단락 제거: {report.markers_removed}개 / 총 삭제 단락: {report.paragraphs_removed}개")
    print(f"저장: {report.output_docx}")
    if report.markers_removed == 0:
        print("(제거할 NotebookLM 블록이 없었습니다 — 사본만 생성)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
