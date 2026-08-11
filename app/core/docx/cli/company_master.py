"""company_master.py — P3 CLI: 참고자료(들) → company_master.json (기업정보 자산화).

사용 (PowerShell)
-----------------
cd D:\\auto_write\\app
py -3.11 company_master.py 회사소개.pdf 사업계획서.docx -o company_master.json
py -3.11 company_master.py "C:\\기업자료폴더"                 # 폴더 안 문서 전부(우선순위=최신)
py -3.11 company_master.py A.docx B.docx --key 밸류업파트너스   # 기업키 지정

동작
----
1) 각 파일에서 기업 정체성 필드(기업명·대표자·사업자등록번호·설립일·업종·주소·연락처·
   이메일·홈페이지·직원수·자본금·팩스)를 추출 → partials/partial_NNN.json
2) 우선순위(폴더 입력 시 최신 파일 우선) 병합 → company_master.json
   (파일 간 값 불일치는 conflict 로 드러냄, 없는 필드는 missing, 전부 confirmed=false)

종료코드: 0=성공(추출 0건이어도 정상) / 1=입력·쓰기 오류. 원본 미수정(읽기 전용).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.document_ingest import REFERENCE_SUFFIXES
from auto_write.services import company_extract


def _collect_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            cand = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in REFERENCE_SUFFIXES]
            # 폴더 입력: 최신 수정본 우선(우선순위 병합의 1위가 되도록).
            cand.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            files.extend(cand)
        elif p.is_file():
            files.append(p)
    return files


def main(argv: list[str] | None = None) -> int:
    from auto_write.utils import force_utf8_console
    force_utf8_console()

    parser = argparse.ArgumentParser(description="P3 — 참고자료(들) → company_master.json")
    parser.add_argument("inputs", nargs="+", help="문서 파일들 또는 폴더(우선순위=먼저 온 것/최신)")
    parser.add_argument("-o", "--out", default=None, help="출력 경로(기본 <첫입력폴더>/company_master.json)")
    parser.add_argument("--key", default="", help="기업키(미지정 시 기업명 값 사용)")
    parser.add_argument("--no-partials", action="store_true", help="partial_NNN.json 저장 생략")
    parser.add_argument("--coverage", default=None, metavar="양식파일",
                        help="②역설계: 이 기업 마스터로 지정 양식을 얼마나 채울 수 있는지 대조(coverage.json 저장)")
    args = parser.parse_args(argv)

    files = _collect_files(args.inputs)
    if not files:
        print("[오류] 처리할 파일이 없습니다(경로 확인).", file=sys.stderr)
        return 1

    try:
        master, partials, notes = company_extract.build_company_master(files, company_key=args.key)
    except Exception as exc:  # noqa: BLE001
        print(f"[오류] 기업 마스터 생성 실패: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else (Path(files[0]).parent / "company_master.json")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(company_extract.master_to_json(master), encoding="utf-8")
        if not args.no_partials:
            pdir = out_path.parent / "partials"
            pdir.mkdir(parents=True, exist_ok=True)
            for idx, (source, partial) in enumerate(partials, 1):
                (pdir / f"partial_{idx:03d}.json").write_text(
                    json.dumps({"source": source, "fields": partial}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
    except OSError as exc:
        print(f"[오류] 파일 쓰기 실패: {exc}", file=sys.stderr)
        return 1

    print(company_extract.format_korean(master))
    for note in notes:
        if note.startswith("[skip]"):
            print(f"  {note}")
    print(f"\n저장: {out_path}")

    # ②역설계: 지정 양식을 이 마스터로 얼마나 채울 수 있는지 대조.
    # 정부양식은 표 중심이라 표 칸 빈칸을 찾는 find_target_fields 를 쓴다
    # (form_analyzer.writable_item_details 는 본문 항목만 담아 표 셀을 놓침).
    if args.coverage:
        try:
            from auto_write.document_ingest import ensure_template_docx
            from auto_write.services.cross_form_autofill import find_target_fields
            from auto_write.services.form_analyzer import classify_field_kind

            docx_form, _conv_notes = ensure_template_docx(Path(args.coverage))
            targets = find_target_fields(docx_form)
            fact_labels = [
                str(t.get("orig_label", ""))
                for t in targets
                if str(t.get("orig_label", "")).strip()
                and classify_field_kind(str(t.get("orig_label", ""))) == "fact"
            ]
            cov = company_extract.coverage(master, fact_labels)
            print("\n" + company_extract.format_coverage_korean(cov, Path(args.coverage).name))
            cov_path = out_path.parent / "coverage.json"
            cov_path.write_text(
                json.dumps({"form": Path(args.coverage).name, **cov}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"저장: {cov_path}")
        except Exception as exc:  # noqa: BLE001 — 커버리지 실패가 마스터 생성(성공)을 무효화하지 않음
            print(f"[경고] 커버리지 대조 실패(무시): {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
