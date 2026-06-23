"""cross_form_fill.py — 소스 사업계획서 A 의 값을 빈 양식 B 의 빈 칸에 전사하는 CLI.

완성된 문서 A 의 라벨-값을 빈 양식 B 의 유사 항목 칸에 자동으로 옮겨 적는다.
보수적 매칭(오매칭은 빈칸보다 나쁘다)·날조 0(소스 실값만)·원본 미수정.
**표 칸**과 **본문 단락형 빈칸("○ 라벨 : ____")** 을 모두 채운다(단락은 콜론 뒤가
빈칸일 때만 — 이미 채워짐·마스킹 ○○○·문장은 보존).
**한 줄에 여러 칸이 나란히 있어도**(예: "기업명 : ____    대표자 : ____") 각 칸을
개별 인식해 채운다(빈칸만, 이미 채워진/마스킹 칸과 칸 사이 간격은 그대로 보존).

사용법 (PowerShell):
    cd D:\auto_write\app
    python cross_form_fill.py --source A.docx --target B.docx -o out.docx
    python cross_form_fill.py --source A.hwp  --target B.hwp  -o out.hwp

    # needs_confirm(퍼지/충돌) 후보를 사람이 골라 적용:
    python cross_form_fill.py --source A.docx --target B.docx -o out.docx \
        --confirm "제품명칭=제품명" --confirm "연락처=휴대폰"
    python cross_form_fill.py --source A.docx --target B.docx -o out.docx \
        --confirm-file confirm.json     # {"제품명칭": "제품명", ...}

결과는 AutofillReport(JSON)로 출력한다. 종료코드: 0=성공, 2=실패(ok=False/예외).
예외(없는 파일·원본덮어쓰기·손상 파일·확정 형식오류 등)도 raw traceback 대신
JSON 리포트+exit 2.
"""

from __future__ import annotations

import argparse
import json
import sys

from auto_write.services.cross_form_autofill import autofill_from_source


def _parse_confirmations(
    confirm: list[str] | None, confirm_file: str | None
) -> dict[str, str]:
    """--confirm / --confirm-file 입력을 {타깃: 소스} 확정 맵으로 합친다.

    - --confirm "타깃=소스" (반복 가능): 첫 '=' 기준 분리. '=' 없으면 ValueError.
    - --confirm-file PATH: JSON. dict({타깃:소스}) 또는
      list([{"target":..., "source":...}, ...]) 둘 다 허용.
    - 파일 → --confirm 순으로 병합(뒤가 우선).
    """
    merged: dict[str, str] = {}
    if confirm_file:
        with open(confirm_file, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            for k, v in data.items():
                merged[str(k)] = str(v)
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict) or "target" not in item or \
                        "source" not in item:
                    raise ValueError(
                        "확정 파일 list 항목은 {\"target\":..., \"source\":...} 형식이어야 합니다")
                merged[str(item["target"])] = str(item["source"])
        else:
            raise ValueError("확정 파일은 JSON dict 또는 list 여야 합니다")
    for entry in confirm or []:
        if "=" not in entry:
            raise ValueError(f"--confirm 형식 오류('{entry}'): \"타깃=소스\" 형태여야 합니다")
        tgt, src = entry.split("=", 1)
        tgt, src = tgt.strip(), src.strip()
        if not tgt or not src:
            raise ValueError(f"--confirm 형식 오류('{entry}'): 타깃·소스가 비어 있습니다")
        merged[tgt] = src
    return merged


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="소스 A 의 라벨-값을 빈 양식 B 의 유사 칸에 전사(결정론·보수적·날조0)")
    parser.add_argument("--source", required=True, help="소스(값이 채워진) DOCX/HWP/HWPX")
    parser.add_argument("--target", required=True, help="타깃(빈 양식) DOCX/HWP/HWPX")
    parser.add_argument("-o", "--out", required=True, help="출력 경로(원본과 같으면 거부)")
    parser.add_argument("--use-ai", action="store_true",
                        help="AI 사용(v1 미지원 슬롯 — 기본은 결정론 매칭)")
    parser.add_argument("--confirm", action="append", metavar="타깃=소스",
                        help="needs_confirm 후보 확정 적용(반복 가능). 예: --confirm \"제품명칭=제품명\"")
    parser.add_argument("--confirm-file", metavar="PATH",
                        help="확정 맵 JSON 파일({타깃:소스} 또는 [{target,source}])")
    args = parser.parse_args(argv)

    # M5: 예외를 raw traceback/exit1 로 흘리지 않고 JSON 리포트+exit 2 로 통일.
    try:
        confirmations = _parse_confirmations(args.confirm, args.confirm_file)
        report = autofill_from_source(
            args.source, args.target, args.out, use_ai=args.use_ai,
            confirmations=confirmations or None)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        err = {
            "source": args.source,
            "target": args.target,
            "output": args.out,
            "ok": False,
            "error": str(exc),
            "notes": [str(exc)],
        }
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 2


if __name__ == "__main__":
    sys.exit(main())
