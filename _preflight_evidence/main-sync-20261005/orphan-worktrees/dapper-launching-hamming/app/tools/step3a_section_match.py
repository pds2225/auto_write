# -*- coding: utf-8 -*-
"""STEP 3A matcher CLI — 합성 STEP 2 결과로 섹션 매칭 한글 리포트를 출력한다.

글을 쓰지 않는다. HWP/Writer/UI를 호출하지 않는다.
실제 STEP 2 추출기 파일이 아니라 JSON fixture만 읽는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.services.section_matcher import (  # noqa: E402
    format_human_report,
    match_from_step2,
)
from auto_write.services.step2_output_contract import Step2ContractError  # noqa: E402


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} 최상위는 object여야 합니다.")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="합성 STEP 2 JSON과 양식 섹션을 매칭해 비개발자용 한글 리포트를 출력합니다."
    )
    parser.add_argument("--bundle", help="sections + step2 + requirements 를 한 JSON에 담은 파일")
    parser.add_argument("--step2", help="STEP 2 출력 JSON (facts / narrative_evidence / conflicts)")
    parser.add_argument("--sections", help="양식 섹션 JSON (sections 배열 또는 {sections:[...]})")
    parser.add_argument("--requirements", help="공고 요구사항 JSON (선택)")
    parser.add_argument("--json-out", help="기계용 매칭 결과 JSON 경로 (선택)")
    args = parser.parse_args(argv)

    try:
        if args.bundle:
            bundle = _load_json(Path(args.bundle).expanduser().resolve())
            sections = bundle.get("sections")
            step2 = bundle.get("step2") or bundle.get("step2_output")
            if not isinstance(step2, dict):
                step2 = {
                    "facts": bundle.get("facts") or [],
                    "narrative_evidence": bundle.get("narrative_evidence")
                    or bundle.get("evidence")
                    or [],
                    "conflicts": bundle.get("conflicts") or [],
                }
            requirements = bundle.get("requirements")
        else:
            if not args.step2 or not args.sections:
                print("--bundle 또는 --step2 와 --sections 가 필요합니다.", file=sys.stderr)
                return 2
            step2 = _load_json(Path(args.step2).expanduser().resolve())
            section_payload = _load_json(Path(args.sections).expanduser().resolve())
            sections = (
                section_payload.get("sections")
                if isinstance(section_payload.get("sections"), list)
                else None
            )
            if sections is None and isinstance(section_payload, dict) and "section_id" in section_payload:
                sections = [section_payload]
            requirements = None
            if args.requirements:
                req_payload = _load_json(Path(args.requirements).expanduser().resolve())
                requirements = req_payload.get("requirements", req_payload)

        if not isinstance(sections, list) or not sections:
            print("양식 섹션 배열이 비어 있습니다.", file=sys.stderr)
            return 2
        if not isinstance(step2, dict):
            print("STEP 2 출력이 object가 아닙니다.", file=sys.stderr)
            return 2
        if requirements is not None and not isinstance(requirements, list):
            print("requirements는 array여야 합니다.", file=sys.stderr)
            return 2

        matches = match_from_step2(sections, step2, requirements)
    except (OSError, json.JSONDecodeError, ValueError, Step2ContractError) as exc:
        print(f"STEP 3A 매칭 실패: {exc}", file=sys.stderr)
        return 2

    report = format_human_report(matches)
    print(report, end="" if report.endswith("\n") else "\n")

    if args.json_out:
        out = Path(args.json_out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps([row.as_dict() for row in matches], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
