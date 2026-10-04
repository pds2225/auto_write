# -*- coding: utf-8 -*-
"""Golden checks for the ten validation forms.

Facts in this module are coordinates and raw strings read from the HWPX XML.
The evaluator does not copy analyzer decisions into those facts. Every file
goes through the same checks.
"""

from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import assess_fields, classify_protected_regions, find_t02_auto_targets
from core.docx.services.hwpx_xml_scope_diff import (
    _PARSER,
    iter_section_paragraphs,
    paragraph_raw_text,
    run_raw_text,
    sha256_file,
)

_LOCKED_FAKE_LABELS = frozenset({
    "(서술 칸)", "(서술칸)", "(빈 칸)", "(빈칸)", "(이름 없음)", "(이름없음)",
})
_LOCKED_CHOICE_LABELS = frozenset({"해당", "여", "부", "예", "아니오", "확인"})
_SIGNATURE_RE = re.compile(
    r"[\(（]\s*(?:서명|날인|직인|인)(?:\s*[,，]\s*(?:서명|날인|직인|인))?\s*[\)）]"
)
_DATE_RE = re.compile(r"(?:\d{4}\s*)?년\s*월\s*일")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _t02(**kwargs) -> dict:
    return kwargs


def _anchor(**kwargs) -> dict:
    kwargs.setdefault("forbid_field_labels", [])
    kwargs.setdefault("expected_roles", [])
    kwargs.setdefault("expected_decision", "NOT_AUTO")
    kwargs.setdefault("never_auto", True)
    return kwargs


# Raw strings and coordinates were read from each file's section XML.
GOLDEN_CASES: tuple[dict, ...] = (
    {
        "file": "(서식09) 연구개발기관 대표의 참여의사 확인서_접수번호(기관명).hwpx",
        "source_sha256": "8d38f51ea5e36fd13435285aadf3af3065ebfd51767930470c1621163e5acfd4",
        "known_safe_t02": [
            _t02(field_label="연구개발과제번호", section_index=0, paragraph_index=7, run_index=0, table_index=0, row=1, col=3, label_paragraphs=(6,), label_text="연구개발과제번호"),
            _t02(field_label="연구개발과제명", section_index=0, paragraph_index=9, run_index=0, table_index=0, row=2, col=1, label_paragraphs=(8,), label_text="연구개발과제명"),
            _t02(field_label="주관연구개발기관명", section_index=0, paragraph_index=11, run_index=0, table_index=0, row=3, col=1, label_paragraphs=(10,), label_text="주관연구개발기관명"),
            _t02(field_label="주관연구개발기관연구책임자", section_index=0, paragraph_index=13, run_index=0, table_index=0, row=3, col=3, label_paragraphs=(12,), label_text="주관연구개발기관 연구책임자"),
            _t02(field_label="공동연구개발기관명", section_index=0, paragraph_index=15, run_index=0, table_index=0, row=4, col=1, label_paragraphs=(14,), label_text="공동연구개발기관명"),
            _t02(field_label="공동연구개발기관책임자", section_index=0, paragraph_index=18, run_index=0, table_index=0, row=4, col=3, label_paragraphs=(16, 17), label_text="공동연구개발기관책임자"),
        ],
        "anchors": [
            _anchor(id="seal-line", section_index=0, paragraph_index=39, run_index=0, pattern="SIGNATURE", structure_type="T06", text="                                                연구개발기관의 책임자 :                (직인)", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED"),
        ],
    },
    {
        "file": "(참여신청서, 개인정보동의서) 서울창업허브 성수, 창동×홈앤쇼핑 오픈이노베이션.hwpx",
        "source_sha256": "0e8647f5fc1a21e6d35da9bc4ce1c536d81d0cc6bf9775dc84ba753c31dce646",
        "known_safe_t02": [
            _t02(field_label="업체명", section_index=0, paragraph_index=5, run_index=0, table_index=1, row=1, col=1, label_paragraphs=(4,), label_text="업체명"),
            _t02(field_label="업종/업태(사업분야)", section_index=0, paragraph_index=7, run_index=0, table_index=1, row=2, col=1, label_paragraphs=(6,), label_text="업종/업태(사업분야)"),
            _t02(field_label="설립연도(연/월/일)", section_index=0, paragraph_index=9, run_index=0, table_index=1, row=3, col=1, label_paragraphs=(8,), label_text="설립연도(연/월/일)"),
            _t02(field_label="대표자명", section_index=0, paragraph_index=11, run_index=0, table_index=1, row=4, col=1, label_paragraphs=(10,), label_text="대표자명 "),
            _t02(field_label="대표자연락처", section_index=0, paragraph_index=13, run_index=0, table_index=1, row=5, col=1, label_paragraphs=(12,), label_text="대표자 연락처"),
            _t02(field_label="대표자이메일주소", section_index=0, paragraph_index=15, run_index=0, table_index=1, row=6, col=1, label_paragraphs=(14,), label_text="대표자 이메일주소"),
            _t02(field_label="상품/기술/서비스명", section_index=0, paragraph_index=17, run_index=0, table_index=1, row=7, col=1, label_paragraphs=(16,), label_text="상품/기술/서비스명"),
        ],
        "anchors": [
            _anchor(id="consent-signature", section_index=0, paragraph_index=81, run_index=0, pattern="SIGNATURE", structure_type="T06", text="동의자(대표자) 성명 :                   (인)", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED"),
        ],
    },
    {
        "file": "2025전담PM(자기기술서).hwpx",
        "source_sha256": "9a8c3f1b9eb33a2338d5efba921a43f8c15b460975e0e5b4819e043635748b53",
        "known_safe_t02": [],
        "anchors": [
            _anchor(id="career-heading", section_index=0, paragraph_index=4, run_index=0, pattern="GUIDANCE", structure_type="T07", text="□ 컨설팅 전문분야 경력사항(신청한 전문분야 위주 기술)", expected_roles=["UNCONFIRMED_CHOICE", "HEADING", "CHOICE_MARK"], expected_decision="NOT_AUTO"),
            _anchor(id="date-scaffold", section_index=0, paragraph_index=10, run_index=0, pattern="DATE_SCAFFOLD", structure_type="T05", text="2025년       월       일", expected_roles=["DATE_SCAFFOLD"], expected_decision="REVIEW_REQUIRED"),
            _anchor(id="same-run-signature", section_index=0, paragraph_index=12, run_index=0, pattern="SAME_RUN_LABEL", structure_type="T03", text="성 명 :                   (서명)", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED"),
        ],
    },
    {
        "file": "(첨부3) 성장촉진자금(자동화설비) 신청 자가진단표.hwpx",
        "source_sha256": "541ab4a948953f0c01cf8e65029407bd8b4568b0016898c138916d2627dfb1f9",
        "known_safe_t02": [],
        "anchors": [
            _anchor(id="choice-header", section_index=0, paragraph_index=10, run_index=0, pattern="CHOICE_HEADER", structure_type="T09", text="해 당", expected_roles=["CHOICE_HEADER", "UNCONFIRMED_CHOICE"], expected_decision="NOT_AUTO", forbid_field_labels=["해당"]),
            _anchor(id="choice-mark", section_index=0, paragraph_index=17, run_index=0, pattern="CHOICE_MARK", structure_type="T09", text=" □예", expected_roles=["CHOICE_MARK", "UNCONFIRMED_CHOICE"], expected_decision="NOT_AUTO", forbid_field_labels=["예", "아니오"]),
            _anchor(id="real-question", section_index=0, paragraph_index=28, run_index=0, pattern="CHOICE_HEADER", structure_type="T09", text="④ 비영리 법인 또는 비영리 개인사업자", expected_roles=["EXISTING_VALUE"], expected_decision="NO_TARGET", forbid_field_labels=["해당", "예", "아니오"]),
        ],
    },
    {
        "file": "(별첨1) 2024년도 창업중심대학 예비창업자 사업계획서 양식.hwpx",
        "source_sha256": "7e4f68fa9d040e32d3a2dd0c4a00f240c22d41bf23798edb8179a1d7718d378b",
        "known_safe_t02": [
            _t02(field_label="별첨", section_index=0, paragraph_index=507, run_index=0, table_index=43, row=0, col=1, label_paragraphs=(506,), label_text="별 첨"),
        ],
        "anchors": [
            _anchor(id="guidance-run", section_index=0, paragraph_index=51, run_index=0, pattern="GUIDANCE", structure_type="T07", text="※ 사업계획서는 목차(1페이지)를 제외하고 15페이지 이내로 작성(증빙서류는 제한 없음)", expected_roles=["GUIDANCE"], expected_decision="NO_TARGET", forbid_field_labels=["(서술 칸)", "(서술칸)"]),
            _anchor(id="guidance-empty-run", section_index=0, paragraph_index=51, run_index=1, pattern="GUIDANCE", structure_type="T07", text="", expected_roles=["GUIDANCE"], expected_decision="NO_TARGET", forbid_field_labels=["(서술 칸)"]),
        ],
    },
    {
        "file": "(붙임2) 신용취약소상공인자금 신청 서식.hwpx",
        "source_sha256": "758b3225f7ef3090100b539e686fc3a0ab7ea0c2198fc3ea3ac2d5826f1fd3e6",
        "known_safe_t02": [
            _t02(field_label="업체명", section_index=0, paragraph_index=268, run_index=0, table_index=12, row=0, col=2, label_paragraphs=(267,), label_text="업 체 명"),
            _t02(field_label="법인등록번호", section_index=0, paragraph_index=272, run_index=0, table_index=12, row=1, col=2, label_paragraphs=(271,), label_text="법인등록번호"),
            _t02(field_label="사업자등록번호", section_index=0, paragraph_index=276, run_index=0, table_index=12, row=2, col=2, label_paragraphs=(275,), label_text="사업자등록번호"),
        ],
        "anchors": [
            _anchor(id="section-title-customer", section_index=0, paragraph_index=251, run_index=0, pattern="SECTION_TITLE", structure_type="T10", text="고       객", expected_roles=[], expected_decision="NOT_AUTO"),
            _anchor(id="inline-company", section_index=0, paragraph_index=253, run_index=0, pattern="SAME_RUN_LABEL", structure_type="T03", text="기업체명 :", expected_roles=["LABEL"], expected_decision="NO_TARGET", forbid_field_labels=["고객"]),
            _anchor(id="inline-representative", section_index=0, paragraph_index=256, run_index=0, pattern="SAME_RUN_LABEL", structure_type="T03", text="대 표 자 :", expected_roles=["LABEL"], expected_decision="NO_TARGET", forbid_field_labels=["고객"]),
            _anchor(id="signature-scaffold", section_index=4, paragraph_index=32, run_index=0, pattern="SIGNATURE", structure_type="T06", text=" 대 표 자 :                     (인, 서명)", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED"),
        ],
    },
    {
        "file": "3. SBA 액셀러레이팅 정보 수집 및 이용 동의서 양식(2023년).hwpx",
        "source_sha256": "55db3e7da61b0918ec1ceca0b0c742fedb074e34902d7d6d1c461379091bbe6a",
        "known_safe_t02": [],
        "anchors": [
            _anchor(id="date-scaffold", section_index=0, paragraph_index=35, run_index=0, pattern="DATE_SCAFFOLD", structure_type="T05", text="2023년    월    일", expected_roles=["DATE_SCAFFOLD"], expected_decision="REVIEW_REQUIRED"),
            _anchor(id="company-label-run", section_index=0, paragraph_index=39, run_index=0, pattern="SAME_RUN_LABEL", structure_type="T03", text="                                기   업   명   :", expected_roles=["LABEL"], expected_decision="NO_TARGET"),
            _anchor(id="representative-label-run", section_index=0, paragraph_index=40, run_index=0, pattern="SAME_RUN_LABEL", structure_type="T06", text="                                대표자  성명   :                   ", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED"),
            _anchor(id="applicant-label-run", section_index=0, paragraph_index=41, run_index=0, pattern="SAME_RUN_LABEL", structure_type="T06", text="                                신청자  성명   :                   ", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED"),
        ],
    },
    {
        "file": "(공고)2024년 2030청년창업프로젝트 초기유형 모집 공고문.hwpx",
        "source_sha256": "1a9158cf5669072fc3605c3858383b52815e1f0d5c3e7a8cb2f98e383e58be49",
        "known_safe_t02": [
            _t02(field_label="대표자명", section_index=0, paragraph_index=395, run_index=0, table_index=23, row=5, col=1, label_paragraphs=(394,), label_text="대표자명"),
            _t02(field_label="주민등록번호", section_index=0, paragraph_index=397, run_index=0, table_index=23, row=5, col=4, label_paragraphs=(396,), label_text="주민등록번호"),
            _t02(field_label="기업명", section_index=0, paragraph_index=399, run_index=0, table_index=23, row=6, col=1, label_paragraphs=(398,), label_text="기업명"),
            _t02(field_label="고용인원", section_index=0, paragraph_index=407, run_index=0, table_index=23, row=8, col=1, label_paragraphs=(406,), label_text="고용인원"),
            _t02(field_label="고용보험가입여부", section_index=0, paragraph_index=410, run_index=0, table_index=23, row=8, col=4, label_paragraphs=(408, 409), label_text="고용보험가입여부"),
            _t02(field_label="사업분야", section_index=0, paragraph_index=416, run_index=0, table_index=23, row=10, col=1, label_paragraphs=(415,), label_text="사업 분야"),
            _t02(field_label="참고사항", section_index=0, paragraph_index=672, run_index=0, table_index=38, row=0, col=1, label_paragraphs=(671,), label_text="참고사항"),
        ],
        "anchors": [
            _anchor(id="section-title", section_index=0, paragraph_index=417, run_index=0, pattern="SECTION_TITLE", structure_type="T10", text="주요 사업 내용", expected_roles=[], expected_decision="NOT_AUTO"),
            _anchor(id="date-scaffold", section_index=0, paragraph_index=423, run_index=0, pattern="DATE_SCAFFOLD", structure_type="T05", text="년       월       일", expected_roles=["DATE_SCAFFOLD"], expected_decision="REVIEW_REQUIRED", forbid_field_labels=["주요사업내용"]),
            _anchor(id="signature-inline", section_index=0, paragraph_index=425, run_index=0, pattern="SIGNATURE", structure_type="T06", text="                               신청인(대표) :               (인)", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED", forbid_field_labels=["주요사업내용"]),
            _anchor(id="signature-later", section_index=0, paragraph_index=678, run_index=0, pattern="SIGNATURE", structure_type="T06", text="신청인(대표) :               (인)", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED", forbid_field_labels=["주요사업내용"]),
        ],
    },
    {
        "file": "(필수) 2. 연구개발계획서 본문1.hwpx",
        "source_sha256": "94c5822f82c5abe4e7602cfe1220a736ae84045e06c69e792f0bcf5c64d3a4c0",
        "known_safe_t02": [
            _t02(field_label="개발목표", section_index=0, paragraph_index=11, run_index=0, table_index=1, row=1, col=1, label_paragraphs=(10,), label_text="개발 목표"),
            _t02(field_label="개발방법", section_index=0, paragraph_index=13, run_index=0, table_index=1, row=2, col=1, label_paragraphs=(12,), label_text="개발 방법"),
            _t02(field_label="연구팀구성", section_index=0, paragraph_index=15, run_index=0, table_index=1, row=3, col=1, label_paragraphs=(14,), label_text="연구팀 구성"),
            _t02(field_label="기대효과", section_index=0, paragraph_index=17, run_index=0, table_index=1, row=4, col=1, label_paragraphs=(16,), label_text="기대효과 "),
        ],
        "anchors": [
            _anchor(id="guidance-run", section_index=0, paragraph_index=143, run_index=0, pattern="GUIDANCE", structure_type="T07", text="※ 자체 연구개발 실적 및 타 부처 지원 R&D 사업 포함 가능 ", expected_roles=["GUIDANCE"], expected_decision="NO_TARGET", forbid_field_labels=["(서술 칸)", "(서술칸)"]),
        ],
    },
    {
        "file": "2026년도 SaaS 개발환경 지원 수요기업 신청서.hwpx",
        "source_sha256": "f76d48e5a6201fe6e628c29235a0af479cf6cd4705ce81db1d7ce01c3a23ef9f",
        "known_safe_t02": [
            _t02(field_label="기업명", section_index=0, paragraph_index=6, run_index=0, table_index=1, row=0, col=2, label_paragraphs=(5,), label_text="기 업 명"),
        ],
        "anchors": [
            _anchor(id="section-title", section_index=0, paragraph_index=3, run_index=0, pattern="SECTION_TITLE", structure_type="T10", text="신청 기업", expected_roles=[], expected_decision="NOT_AUTO"),
            _anchor(id="date-scaffold", section_index=0, paragraph_index=86, run_index=0, pattern="DATE_SCAFFOLD", structure_type="T05", text="2026년    월    일", expected_roles=["DATE_SCAFFOLD"], expected_decision="REVIEW_REQUIRED", forbid_field_labels=["신청기업", "신청기업정보"]),
            _anchor(id="first-empty-run", section_index=0, paragraph_index=89, run_index=0, pattern="FIRST_EMPTY_RUN", structure_type="T04", text="         ", expected_roles=["SPACER"], expected_decision="NO_TARGET", forbid_field_labels=["신청기업", "신청기업정보"]),
            _anchor(id="signature-run", section_index=0, paragraph_index=89, run_index=2, pattern="SIGNATURE", structure_type="T06", text=" 대표이사 :               (인)", expected_roles=["SIGNATURE"], expected_decision="REVIEW_REQUIRED", forbid_field_labels=["신청기업", "신청기업정보"]),
            _anchor(id="later-date", section_index=0, paragraph_index=298, run_index=0, pattern="DATE_SCAFFOLD", structure_type="T05", text="2026년      월      일", expected_roles=["DATE_SCAFFOLD"], expected_decision="REVIEW_REQUIRED"),
        ],
    },
)


def default_data_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "data"


def _failure(case: dict, **kwargs) -> dict:
    payload = {
        "file": case["file"],
        "stage": "golden10",
        "field": "",
        "structure_type": "",
        "decision": "",
        "expected": "",
        "actual": "",
        "reason_code": "",
        "xml_location": "",
        "before": "",
        "after": "",
        "severity": "BLOCKER",
    }
    payload.update(kwargs)
    return payload


def _load_roots(path: Path, members: set[str]) -> dict:
    roots = {}
    with ZipFile(path) as archive:
        for member in members:
            roots[member] = etree.fromstring(archive.read(member), parser=_PARSER)
    return roots


def _run_text(roots: dict, member: str, paragraph_index: int, run_index: int) -> str:
    paragraphs = list(iter_section_paragraphs(roots[member]))
    runs = [child for child in paragraphs[paragraph_index] if str(child.tag).endswith("run")]
    return run_raw_text(runs[run_index])


def _joined_label(roots: dict, member: str, paragraphs: tuple[int, ...]) -> str:
    nodes = list(iter_section_paragraphs(roots[member]))
    return "".join(paragraph_raw_text(nodes[index]) for index in paragraphs)


def _location(member: str, section_index: int, paragraph_index: int, run_index: int) -> str:
    return f"{member}#s[{section_index}]/p[{paragraph_index}]/run[{run_index}]"


def evaluate_golden10(data_dir: Path | None = None) -> dict:
    """Check the ten forms. ``ok`` is false when any locked fact disagrees."""
    root = Path(data_dir) if data_dir is not None else default_data_dir()
    files = []
    failures: list[dict] = []
    unsafe = 0
    for case in GOLDEN_CASES:
        file_failures, file_unsafe = _evaluate_case(root / case["file"], case)
        files.append({
            "file": case["file"],
            "status": "PASS" if not file_failures else "FAIL",
            "failures": file_failures,
            "unsafe_auto_count": file_unsafe,
        })
        failures.extend(file_failures)
        unsafe += file_unsafe
    return {
        "ok": not failures,
        "files": files,
        "failures": failures,
        "unsafe_auto_count": unsafe,
        "file_count": len(GOLDEN_CASES),
    }


def format_golden_report(report: dict) -> str:
    lines = []
    for item in report["files"]:
        lines.append(f"{item['status']} {item['file']}")
        for failure in item["failures"]:
            lines.append(
                f"  - {failure['field']} {failure['reason_code']}: "
                f"expected {failure['expected']!r} actual {failure['actual']!r} "
                f"before {failure['before']!r} after {failure['after']!r} "
                f"at {failure['xml_location']}"
            )
    lines.append(f"UNSAFE_AUTO_COUNT={report['unsafe_auto_count']}")
    lines.append("GOLDEN_10=" + ("PASS" if report["ok"] else "FAIL"))
    return "\n".join(lines)


def _evaluate_case(path: Path, case: dict) -> tuple[list[dict], int]:
    failures: list[dict] = []
    unsafe = 0
    if not path.is_file():
        failures.append(_failure(case, field=case["file"], reason_code="FILE_MISSING", expected="present", actual="absent", severity="BLOCKER"))
        return failures, unsafe
    actual_sha = sha256_file(path)
    if actual_sha != case["source_sha256"]:
        failures.append(_failure(
            case, field="source_sha256", reason_code="SHA_MISMATCH", structure_type="SOURCE",
            expected=case["source_sha256"], actual=actual_sha, before=case["source_sha256"], after=actual_sha,
            severity="BLOCKER",
        ))
        return failures, unsafe
    before = path.read_bytes()
    index = index_hwpx_structure(path)
    if path.read_bytes() != before:
        failures.append(_failure(case, field="source", reason_code="SOURCE_MUTATED", severity="BLOCKER"))
        return failures, unsafe
    if index.analysis_status == "FAILED":
        failures.append(_failure(case, field="index", reason_code="INDEX_FAILED", actual=index.analysis_status, severity="BLOCKER"))
        return failures, unsafe
    members = {section.section_member for section in index.sections}
    roots = _load_roots(path, members)
    protection = classify_protected_regions(index)
    assessments = assess_fields(index)
    targets = find_t02_auto_targets(index)
    failures.extend(_check_invariants(case, index, roots, targets, assessments))
    failures.extend(_check_safe_targets(case, index, roots, targets, assessments))
    failures.extend(_check_anchors(case, index, roots, protection, assessments, targets))
    unsafe = sum(1 for item in failures if item["reason_code"] in {"UNSAFE_AUTO", "NONEMPTY_AUTO_TARGET", "FAKE_LABEL", "CHOICE_AS_QUESTION"})
    return failures, unsafe


def _auto_labels(assessments) -> list:
    return [item for item in assessments if item.decision == "AUTO" or item.auto_write_allowed]


def _check_invariants(case, index, roots, targets, assessments) -> list[dict]:
    failures = []
    for target in targets:
        label = target.field_label or ""
        section = index.sections[target.section_index]
        location = _location(section.section_member, target.section_index, target.paragraph_index, target.run_index)
        if label in _LOCKED_FAKE_LABELS or _compact(label) in _LOCKED_CHOICE_LABELS or "※" in label:
            failures.append(_failure(
                case, field=label, structure_type="T02", decision="AUTO", expected="NOT_AUTO", actual=label,
                reason_code="FAKE_LABEL" if label in _LOCKED_FAKE_LABELS else "CHOICE_AS_QUESTION",
                xml_location=location, before=label, after=label, severity="BLOCKER",
            ))
        if _SIGNATURE_RE.search(label) or (_DATE_RE.search(label) and _DATE_RE.sub("", label).strip() == ""):
            failures.append(_failure(
                case, field=label, structure_type="T02", decision="AUTO", expected="NOT_AUTO", actual=label,
                reason_code="UNSAFE_AUTO", xml_location=location, severity="BLOCKER",
            ))
        actual = _run_text(roots, section.section_member, target.paragraph_index, target.run_index)
        if actual.strip():
            failures.append(_failure(
                case, field=label, structure_type="T02", decision="AUTO", expected="", actual=actual,
                reason_code="NONEMPTY_AUTO_TARGET", xml_location=location, before="", after=actual, severity="BLOCKER",
            ))
    for item in assessments:
        label = item.field_label or ""
        if not label:
            continue
        if label in _LOCKED_FAKE_LABELS or _compact(label) in _LOCKED_CHOICE_LABELS:
            failures.append(_failure(
                case, field=label, structure_type=item.field_type, decision=item.decision,
                expected="no synthetic or choice-header label", actual=label,
                reason_code="FAKE_LABEL" if label in _LOCKED_FAKE_LABELS else "CHOICE_AS_QUESTION",
                xml_location=_location(item.section_member, item.section_index, item.paragraph_index or -1, item.run_index or -1),
                severity="BLOCKER",
            ))
        if item.auto_write_allowed and item.field_type != "T02":
            failures.append(_failure(
                case, field=label, structure_type=item.field_type, decision=item.decision,
                expected="NOT_AUTO", actual="AUTO", reason_code="UNSAFE_AUTO", severity="BLOCKER",
            ))
    return failures


def _check_safe_targets(case, index, roots, targets, assessments) -> list[dict]:
    failures = []
    for expected in case["known_safe_t02"]:
        section = index.sections[expected["section_index"]]
        location = _location(section.section_member, expected["section_index"], expected["paragraph_index"], expected["run_index"])
        joined = _joined_label(roots, section.section_member, tuple(expected["label_paragraphs"]))
        if joined != expected["label_text"]:
            failures.append(_failure(
                case, field=expected["field_label"], structure_type="T02", decision="",
                expected=expected["label_text"], actual=joined, reason_code="TEXT_MISMATCH",
                xml_location=location, before=expected["label_text"], after=joined, severity="BLOCKER",
            ))
        value = _run_text(roots, section.section_member, expected["paragraph_index"], expected["run_index"])
        if value != "":
            failures.append(_failure(
                case, field=expected["field_label"], structure_type="T02", decision="",
                expected="", actual=value, reason_code="TEXT_MISMATCH", xml_location=location,
                before="", after=value, severity="BLOCKER",
            ))
        match = next((
            item for item in targets
            if item.field_label == expected["field_label"]
            and item.section_index == expected["section_index"]
            and item.paragraph_index == expected["paragraph_index"]
            and item.run_index == expected["run_index"]
            and item.table_index == expected["table_index"]
            and item.row == expected["row"]
            and item.col == expected["col"]
        ), None)
        table = index.tables[expected["table_index"]]
        value_cell = next((
            cell for cell in table.cells
            if expected["paragraph_index"] in cell.paragraph_indexes
        ), None)
        label_cell = next((
            cell for cell in table.cells
            if any(item in cell.paragraph_indexes for item in expected["label_paragraphs"])
        ), None)
        simple = (
            value_cell is not None and label_cell is not None
            and value_cell.row_span == 1 and value_cell.col_span == 1
            and label_cell.row_span == 1 and label_cell.col_span == 1
        )
        if not simple:
            if match is not None:
                failures.append(_failure(
                    case, field=expected["field_label"], structure_type="T02", decision="AUTO",
                    expected="NOT_P1_CANDIDATE", actual="PRESENT", reason_code="MERGED_T02_CANDIDATE",
                    xml_location=location, severity="BLOCKER",
                ))
            continue
        if match is None:
            failures.append(_failure(
                case, field=expected["field_label"], structure_type="T02", decision="MISSING",
                expected="AUTO", actual="ABSENT", reason_code="MISSING_SAFE_T02",
                xml_location=location, severity="REGRESSION",
            ))
            continue
        candidate = next((
            item for item in assessments
            if item.paragraph_index == expected["paragraph_index"]
            and item.section_index == expected["section_index"]
            and item.field_label == expected["field_label"]
            and item.field_type == "T02"
            and item.eligible
        ), None)
        if candidate is None:
            failures.append(_failure(
                case, field=expected["field_label"], structure_type="T02", decision="MISSING",
                expected="T02_CANDIDATE", actual="ABSENT", reason_code="MISSING_SAFE_T02",
                xml_location=location, severity="REGRESSION",
            ))
            continue
        if candidate.decision == "AUTO" or candidate.auto_write_allowed or candidate.write_target is not None:
            failures.append(_failure(
                case, field=expected["field_label"], structure_type="T02", decision=candidate.decision,
                expected="AUTHORIZATION_PENDING", actual="AUTO", reason_code="UNSAFE_AUTO",
                xml_location=location, severity="BLOCKER",
            ))
    return failures


def _check_anchors(case, index, roots, protection, assessments, targets) -> list[dict]:
    failures = []
    for anchor in case["anchors"]:
        section = index.sections[anchor["section_index"]]
        location = _location(section.section_member, anchor["section_index"], anchor["paragraph_index"], anchor["run_index"])
        actual_text = _run_text(roots, section.section_member, anchor["paragraph_index"], anchor["run_index"])
        if actual_text != anchor["text"]:
            failures.append(_failure(
                case, field=anchor["id"], structure_type=anchor["structure_type"], decision="",
                expected=anchor["text"], actual=actual_text, reason_code="TEXT_MISMATCH",
                xml_location=location, before=anchor["text"], after=actual_text, severity="BLOCKER",
            ))
            continue
        decisions = [
            item for item in protection.decisions
            if item.section_index == anchor["section_index"]
            and item.paragraph_index == anchor["paragraph_index"]
            and item.run_index == anchor["run_index"]
        ]
        role = decisions[0].role if decisions else ""
        decision = decisions[0].decision if decisions else ""
        if anchor["expected_roles"] and role not in anchor["expected_roles"]:
            failures.append(_failure(
                case, field=anchor["id"], structure_type=anchor["structure_type"], decision=decision,
                expected=",".join(anchor["expected_roles"]), actual=role or "ABSENT",
                reason_code="ROLE_MISMATCH", xml_location=location, before=anchor["text"], after=actual_text,
                severity="REGRESSION",
            ))
        if anchor["expected_decision"] == "NOT_AUTO":
            if decision == "AUTO" or any(item.auto_write_allowed for item in decisions):
                failures.append(_failure(
                    case, field=anchor["id"], structure_type=anchor["structure_type"], decision=decision,
                    expected="NOT_AUTO", actual=decision or "ABSENT", reason_code="UNSAFE_AUTO",
                    xml_location=location, severity="BLOCKER",
                ))
        elif decisions and decision != anchor["expected_decision"]:
            failures.append(_failure(
                case, field=anchor["id"], structure_type=anchor["structure_type"], decision=decision,
                expected=anchor["expected_decision"], actual=decision or "ABSENT",
                reason_code="DECISION_MISMATCH", xml_location=location, before=anchor["text"], after=actual_text,
                severity="REGRESSION",
            ))
        if anchor["never_auto"]:
            hit = next((
                item for item in targets
                if item.section_index == anchor["section_index"] and item.paragraph_index == anchor["paragraph_index"]
            ), None)
            auto = next((
                item for item in _auto_labels(assessments)
                if item.section_index == anchor["section_index"] and item.paragraph_index == anchor["paragraph_index"]
            ), None)
            if hit is not None or auto is not None:
                failures.append(_failure(
                    case, field=anchor["id"], structure_type=anchor["structure_type"], decision="AUTO",
                    expected="NOT_AUTO", actual=getattr(hit or auto, "field_label", "") or "AUTO",
                    reason_code="UNSAFE_AUTO", xml_location=location, severity="BLOCKER",
                ))
        for item in assessments:
            if item.section_index != anchor["section_index"] or item.paragraph_index != anchor["paragraph_index"]:
                continue
            if _compact(item.field_label or "") in {_compact(label) for label in anchor["forbid_field_labels"]}:
                failures.append(_failure(
                    case, field=anchor["id"], structure_type=anchor["structure_type"], decision=item.decision,
                    expected="label not in " + ",".join(anchor["forbid_field_labels"]), actual=item.field_label or "",
                    reason_code="SECTION_TITLE_AS_LABEL", xml_location=location, severity="BLOCKER",
                ))
    for label in _LOCKED_FAKE_LABELS:
        if any((item.field_label or "") == label for item in assessments):
            failures.append(_failure(
                case, field=label, structure_type="T08", decision="AUTO", expected="absent", actual=label,
                reason_code="FAKE_LABEL", severity="BLOCKER",
            ))
    return failures
