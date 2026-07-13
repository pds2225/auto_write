"""sft_export.py — SFT 데이터 레이어 P2 CLI: 축적된 trace+feedback → 학습셋.

사용 (PowerShell)
-----------------
cd D:\\auto_write\\app
py -3.11 sft_export.py                        # 기본: workspace/learning/ 에서 읽어 같은 폴더에 씀
py -3.11 sft_export.py -o out.jsonl --mask    # PII·수치 마스킹한 학습셋
py -3.11 sft_export.py --no-learned           # learned_snippets(생성 소비자용) 생략

산출물
------
1) sft_dataset.jsonl   — (system,user,assistant) chat 학습셋(사람 승인본 우선).
2) learned_snippets.json — generate 가 few-shot 으로 소비하는 항목별 승인 예시(항상 마스킹).

종료코드: 0=성공(0건이어도 정상) / 1=입력·쓰기 오류. 읽기 전용(학습데이터만 생성).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.services import sft_export
from auto_write.services.learning_store import LEARNING_ROOT


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="SFT 데이터 레이어 P2 — trace+feedback → 학습셋")
    parser.add_argument("--root", default=None, help="learning 데이터 루트(기본 workspace/learning)")
    parser.add_argument("-o", "--out", default=None, help="SFT JSONL 출력 경로(기본 <root>/sft_dataset.jsonl)")
    parser.add_argument("--learned", default=None, help="learned_snippets 출력 경로(기본 <root>/learned_snippets.json)")
    parser.add_argument("--mask", action="store_true", help="SFT 학습셋에도 PII·수치 마스킹 적용(기본 미적용)")
    parser.add_argument("--no-learned", action="store_true", help="learned_snippets 생성 생략")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else LEARNING_ROOT
    out_path = Path(args.out) if args.out else root / "sft_dataset.jsonl"
    learned_path = Path(args.learned) if args.learned else root / "learned_snippets.json"

    try:
        result = sft_export.export_all(root=root, mask=args.mask)
    except Exception as exc:  # noqa: BLE001
        print(f"[오류] 학습셋 생성 실패: {exc}", file=sys.stderr)
        return 1

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result["jsonl"], encoding="utf-8")
        if not args.no_learned:
            learned_path.parent.mkdir(parents=True, exist_ok=True)
            learned_path.write_text(
                json.dumps({"snippets": result["learned"]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except OSError as exc:
        print(f"[오류] 파일 쓰기 실패: {exc}", file=sys.stderr)
        return 1

    c = result["counts"]
    print(
        f"[완료] trace={c['traces']} feedback={c['feedbacks']} → "
        f"학습예시 {c['examples']}건(사람승인 {c['human_approved']}·AI {c['ai_only']}) "
        f"| learned 항목 {c['learned_labels']}개"
    )
    print(f"  SFT: {out_path}")
    if not args.no_learned:
        print(f"  learned_snippets: {learned_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
