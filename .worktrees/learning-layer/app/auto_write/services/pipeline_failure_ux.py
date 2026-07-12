"""pipeline_failure_ux.py — mail→auto_write 파이프라인 실패·환경 UX (정직 안내).

지금까지 실측·운영에서 나온 실패 케이스를 한곳에서 분류하고,
비개발자용 한국어 메시지·exit code 힌트를 제공한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from .cross_form_autofill import BatchAutofillItem, BatchAutofillReport, list_source_pool
from .folder_analyzer import FolderAnalysisReport

_LOGIN_WALL_DOMAINS = ("sbiz24.kr", "smes.go.kr", "isso.smes.go.kr")
_KSTARTUP_JUNK_NAME_RE = re.compile(
    r"downloadPath|location\.href|function\s+fn_|첨부파일|\.html$",
    re.IGNORECASE,
)
_DATE_IN_TEXT_RE = re.compile(
    r"(\d{4})\s*[년.\-/]\s*(\d{1,2})\s*[월.\-/]\s*(\d{1,2})"
)
_ADDRESS_LABEL_RE = re.compile(r"주소|주소지|소재지|자택")
_MERGE_CELL_HINT_RE = re.compile(r"병합|\( - \)|placeholder|예시", re.IGNORECASE)


@dataclass
class FailureAdvice:
    code: str
    message: str
    severity: str = "error"  # error | warn | info
    form: str = ""

    def as_line(self) -> str:
        prefix = {"error": "[실패]", "warn": "[주의]", "info": "[안내]"}.get(
            self.severity, "[안내]")
        if self.form:
            return f"{prefix} {self.form} — {self.message}"
        return f"{prefix} {self.message}"


@dataclass
class FailureReport:
    advices: list[FailureAdvice] = field(default_factory=list)
    exit_code: int = 0

    def lines(self) -> list[str]:
        return [a.as_line() for a in self.advices]

    def merge(self, other: FailureReport) -> None:
        seen = {(a.code, a.form, a.message) for a in self.advices}
        for a in other.advices:
            key = (a.code, a.form, a.message)
            if key not in seen:
                self.advices.append(a)
                seen.add(key)
        if other.exit_code > self.exit_code:
            self.exit_code = other.exit_code


def _parse_date_from_deadline(text: str) -> date | None:
    if not text:
        return None
    m = _DATE_IN_TEXT_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def check_deadline_warning(analysis: FolderAnalysisReport) -> str:
    """마감 지남/임박 경고 문구(채팅·todo 상단용)."""
    for adv in collect_analysis_failures(analysis).advices:
        if adv.code in ("DEADLINE_PAST", "DEADLINE_SOON"):
            return adv.message.replace("[주의] ", "⚠ ").replace("[실패] ", "⚠ ")
    return ""


def classify_login_wall(url: str, log_results: list[dict[str, Any]]) -> str:
    """로그인벽 — sbiz24·중소벤처24 등."""
    u = (url or "").lower()
    if not any(dom in u for dom in _LOGIN_WALL_DOMAINS):
        # 로그 결과 URL 도 검사
        if not any(
            any(dom in str(r.get("detail_url", "")).lower() for dom in _LOGIN_WALL_DOMAINS)
            for r in log_results
        ):
            return ""
    bad = [r for r in log_results if r.get("status") in (
        "PAGE_FETCH_FAILED", "NO_ATTACHMENTS", "EXTRACT_FAILED")]
    if not bad and "sbiz24" not in u:
        return ""
    return (
        "이 사이트(소상공인24·중소벤처24 등)는 로그인 후에만 첨부를 받을 수 있습니다. "
        "브라우저에서 파일을 받아 공고 폴더에 넣고 "
        "`--notice-folder` 만 지정해 주세요. (도구 버그가 아닙니다)"
    )


def classify_download_failure(
    url: str,
    log_results: list[dict[str, Any]],
    *,
    stderr: str = "",
    proc_rc: int = 0,
    folder_resolved: bool = True,
) -> FailureReport:
    """다운로드 단계 실패 분류."""
    rep = FailureReport(exit_code=2)
    login = classify_login_wall(url, log_results)
    if login:
        rep.advices.append(FailureAdvice("LOGIN_WALL", login, "error"))
        return rep

    err_blob = (stderr or "").lower()
    for r in log_results:
        status = r.get("status", "")
        err = str(r.get("error", ""))
        if status == "NO_ATTACHMENTS":
            rep.advices.append(FailureAdvice(
                "DOWNLOAD_NO_ATTACHMENTS",
                "첨부파일을 찾지 못했습니다. 공고 페이지에서 직접 받거나 "
                "다른 링크(기업마당·K-Startup 상세 URL)를 확인해 주세요.",
                "error",
            ))
        elif status == "PAGE_FETCH_FAILED":
            if any(k in err_blob or k in err.lower() for k in (
                "ssl", "certificate", "unexpected_eof", "tls")):
                msg = (
                    "사이트 연결(SSL) 문제로 페이지를 열지 못했습니다. "
                    "잠시 후 다시 시도하거나 브라우저에서 첨부를 받아 주세요.")
            else:
                msg = (
                    "공고 페이지를 열지 못했습니다. URL·로그인 필요 여부를 확인해 주세요.")
            rep.advices.append(FailureAdvice("DOWNLOAD_PAGE_FAILED", msg, "error"))
        elif status == "EXTRACT_FAILED":
            rep.advices.append(FailureAdvice(
                "DOWNLOAD_EXTRACT_FAILED",
                "페이지는 열렸지만 첨부 링크를 읽지 못했습니다. "
                "K-Startup 등은 브라우저에서 직접 받는 것이 안전합니다.",
                "error",
            ))
        elif status == "DOWNLOAD_FAILED":
            rep.advices.append(FailureAdvice(
                "DOWNLOAD_HTTP_FAILED",
                f"파일 다운로드에 실패했습니다({err or 'HTTP 오류'}). "
                "브라우저에서 다시 받아 주세요.",
                "error",
            ))

    if proc_rc != 0 and not rep.advices:
        rep.advices.append(FailureAdvice(
            "DOWNLOAD_UNKNOWN",
            f"다운로드가 끝나지 않았습니다(exit {proc_rc}). "
            "URL과 네트워크를 확인해 주세요.",
            "error",
        ))

    if not folder_resolved and not rep.advices:
        rep.advices.append(FailureAdvice(
            "DOWNLOAD_FOLDER_UNKNOWN",
            "다운로드는 됐지만 저장 폴더를 찾지 못했습니다. "
            f"`_download_log.json` 또는 OneDrive 공고 폴더를 확인해 주세요.",
            "error",
        ))

    if not rep.advices and proc_rc != 0:
        rep.exit_code = 2
    elif not rep.advices:
        rep.exit_code = 0
    return rep


def pdf_only_pool_warning(pool: Path) -> str:
    """완성본 폴더에 PDF만 있을 때."""
    if list_source_pool(pool, recursive=True):
        return ""
    pdfs = list(pool.rglob("*.pdf")) if pool.is_dir() else []
    if pdfs:
        return (
            "완성본 폴더에 PDF만 있습니다. cross-form 소스는 DOCX/HWP/HWPX 만 "
            "지원합니다 — 한글/워드로 변환한 파일을 source-pool에 넣어 주세요.")
    return ""


def detect_kstartup_junk_attachments(notice_folder: Path) -> Optional[str]:
    """K-Startup 첨부가 HTML/JS 조각으로 받아진 경우(실측)."""
    if not notice_folder.is_dir():
        return None
    junk: list[str] = []
    for p in notice_folder.iterdir():
        if p.is_dir():
            continue
        name = p.name
        if _KSTARTUP_JUNK_NAME_RE.search(name):
            junk.append(name[:60])
        if p.suffix.lower() == ".html" and p.stat().st_size < 500_000:
            junk.append(name[:60])
    if len(junk) >= 2 or (junk and any("첨부파일" in j for j in junk)):
        return (
            "K-Startup 첨부가 HTML/스크립트 조각으로 받아진 것 같습니다. "
            "공고 상세 페이지에서 HWP/PDF를 직접 받아 이 폴더에 넣어 주세요.")
    return None


def collect_analysis_failures(analysis: FolderAnalysisReport) -> FailureReport:
    """B 단계(분석) 경고·실패."""
    rep = FailureReport()
    ann = analysis.announcement
    if ann and ann.key_info:
        raw = ann.key_info.get("deadline")
        text = raw if isinstance(raw, str) else " / ".join(str(x) for x in raw or [])
        d = _parse_date_from_deadline(text)
        if d:
            today = date.today()
            if d < today:
                rep.advices.append(FailureAdvice(
                    "DEADLINE_PAST",
                    f"마감이 지났습니다({d.isoformat()}). 제출이 불가할 수 있습니다.",
                    "error",
                ))
                rep.exit_code = max(rep.exit_code, 2)
            elif (d - today).days <= 3:
                rep.advices.append(FailureAdvice(
                    "DEADLINE_SOON",
                    f"마감이 임박했습니다({d.isoformat()}, D-{(d - today).days}).",
                    "warn",
                ))

    if not analysis.forms:
        rep.advices.append(FailureAdvice(
            "NOTICE_NO_FORMS",
            "신청서·참가서류 양식(.docx/.hwp/.hwpx)을 찾지 못했습니다. "
            "첨부를 다시 받았는지 확인해 주세요.",
            "error",
        ))
        rep.exit_code = max(rep.exit_code, 2)

    if not analysis.announcement_path:
        rep.advices.append(FailureAdvice(
            "NOTICE_NO_ANNOUNCEMENT",
            "공고문 파일을 찾지 못했습니다(파일명에 '공고'·'모집' 포함 여부). "
            "마감·자격은 수동으로 확인해 주세요.",
            "warn",
        ))

    for note in analysis.notes:
        if "찾지 못했" in note:
            rep.advices.append(FailureAdvice("ANALYSIS_NOTE", note, "warn"))

    junk = detect_kstartup_junk_attachments(Path(analysis.folder))
    if junk:
        rep.advices.append(FailureAdvice("KSTARTUP_JUNK_ATTACHMENTS", junk, "error"))
        rep.exit_code = max(rep.exit_code, 2)

    return rep


def _hint_for_batch_item(item: BatchAutofillItem) -> list[FailureAdvice]:
    """양식 1개 실패·부분실패 힌트."""
    out: list[FailureAdvice] = []
    form = Path(item.target).name
    notes_text = " ".join(item.notes)

    if not item.source and not item.ok:
        if "소스 파일이 없습니다" in notes_text or not item.source:
            out.append(FailureAdvice(
                "BATCH_NO_SOURCE",
                "완성본 폴더에서 이 양식에 맞는 파일을 찾지 못했습니다. "
                "같은 종류 신청서·사업계획서가 source-pool에 있는지 확인해 주세요.",
                "error",
                form,
            ))
        return out

    if not item.ok:
        if "비지원 확장자" in notes_text or "pdf" in notes_text.lower():
            out.append(FailureAdvice(
                "FORM_UNSUPPORTED",
                "이 파일 형식은 자동 채움을 지원하지 않습니다(.docx/.hwp/.hwpx 만). "
                "PDF는 DOCX/HWP로 변환 후 다시 시도해 주세요.",
                "error",
                form,
            ))
        elif item.transcribed == 0:
            out.append(FailureAdvice(
                "BATCH_TRANSCRIBE_ZERO",
                "완성본과 양식 항목이 맞지 않아 자동으로 채운 칸이 없습니다. "
                "다른 완성본 파일을 source-pool에 넣거나 수동으로 채워 주세요.",
                "warn",
                form,
            ))
        else:
            out.append(FailureAdvice(
                "BATCH_ITEM_FAILED",
                notes_text or "채우기에 실패했습니다.",
                "error",
                form,
            ))

    if item.ok and not item.hwp_ok and item.output.endswith(".docx"):
        if any(k in notes_text for k in ("HWP", "한글", "COM")):
            out.append(FailureAdvice(
                "HWP_COM_UNAVAILABLE",
                "DOCX는 채워졌습니다. HWP는 한글(COM)이 없어 변환하지 못했습니다 — "
                "한글에서 열어 '다른 이름으로 저장' 하거나 "
                "`python hwp_docx.py 문서.docx` 를 사용하세요.",
                "warn",
                form,
            ))

    for um in item.unmatched_targets:
        tgt = str(um.get("target_label") or um.get("normalized") or "")
        if _ADDRESS_LABEL_RE.search(tgt):
            out.append(FailureAdvice(
                "MERGE_CELL_ADDRESS",
                f"「{tgt}」칸은 표 병합/예시값 '( - )' 때문에 자동 채움이 어렵습니다. "
                "한글에서 직접 입력해 주세요. (서울AI허브 등에서 실측된 한계)",
                "info",
                form,
            ))

    return out


def collect_batch_failures(
    batch: BatchAutofillReport,
    pool: Path,
) -> FailureReport:
    """C 단계(일괄 채움) 실패·부분실패."""
    rep = FailureReport()

    pdf_msg = pdf_only_pool_warning(pool)
    if pdf_msg:
        rep.advices.append(FailureAdvice("SOURCE_POOL_PDF_ONLY", pdf_msg, "error"))
        rep.exit_code = max(rep.exit_code, 2)

    if pool.is_dir() and not list_source_pool(pool, recursive=True):
        if not pdf_msg:
            rep.advices.append(FailureAdvice(
                "SOURCE_POOL_EMPTY",
                "완성본 폴더에 DOCX/HWP/HWPX 파일이 없습니다. "
                "제출했던 신청서·사업계획서를 넣어 주세요.",
                "error",
            ))
            rep.exit_code = max(rep.exit_code, 2)

    if not batch.items:
        rep.advices.append(FailureAdvice(
            "BATCH_NO_TARGETS",
            "채울 양식이 없습니다.",
            "error",
        ))
        rep.exit_code = max(rep.exit_code, 2)
        return rep

    for item in batch.items:
        rep.advices.extend(_hint_for_batch_item(item))

    n_ok = batch.ok_count
    n_total = len(batch.items)
    n_hwp = batch.hwp_count
    if n_ok and n_ok < n_total:
        rep.advices.append(FailureAdvice(
            "BATCH_PARTIAL",
            f"양식 {n_total}개 중 {n_ok}개만 채웠습니다. 실패한 양식은 아래를 확인해 주세요.",
            "warn",
        ))
        rep.exit_code = max(rep.exit_code, 2)
    elif n_ok == 0:
        rep.exit_code = max(rep.exit_code, 2)

    if n_ok and n_hwp < n_ok:
        rep.advices.append(FailureAdvice(
            "HWP_PARTIAL",
            f"채운 {n_ok}개 중 HWP는 {n_hwp}개만 만들어졌습니다. "
            "나머지는 DOCX만 저장됐습니다.",
            "warn",
        ))

    return rep


def collect_bizplan_failures(d_attempts: list[dict[str, Any]]) -> FailureReport:
    """D 단계(서술 보강) 실패."""
    rep = FailureReport()
    for d in d_attempts:
        form = str(d.get("form", ""))
        if d.get("ok"):
            continue
        note = str(d.get("note", ""))
        if "서술 잔여 없음" in note:
            continue
        if "실패" in note:
            rep.advices.append(FailureAdvice(
                "BIZPLAN_FAILED",
                note + " — 서술 칸은 직접 작성해 주세요.",
                "warn",
                form,
            ))
    return rep


def collect_input_failures(
    *,
    missing_source_pool: str = "",
    missing_notice: str = "",
) -> FailureReport:
    rep = FailureReport(exit_code=1)
    if missing_source_pool:
        rep.advices.append(FailureAdvice(
            "SOURCE_POOL_MISSING", missing_source_pool, "error"))
    if missing_notice:
        rep.advices.append(FailureAdvice(
            "NOTICE_FOLDER_MISSING", missing_notice, "error"))
    return rep


def collect_all_failures(
    *,
    analysis: FolderAnalysisReport | None = None,
    batch: BatchAutofillReport | None = None,
    pool: Path | None = None,
    download_report: FailureReport | None = None,
    d_attempts: list[dict[str, Any]] | None = None,
    extra_notes: list[str] | None = None,
) -> FailureReport:
    """전 단계 실패를 합친다."""
    merged = FailureReport()
    if download_report:
        merged.merge(download_report)
    if analysis:
        merged.merge(collect_analysis_failures(analysis))
    if batch and pool:
        merged.merge(collect_batch_failures(batch, pool))
    if d_attempts:
        merged.merge(collect_bizplan_failures(d_attempts))
    for note in extra_notes or []:
        merged.advices.append(FailureAdvice("EXTRA", note, "info"))
    return merged


def build_failure_section(report: FailureReport) -> str:
    """다음할일.txt / 채팅용 실패 블록."""
    lines = report.lines()
    return "\n".join(lines)


def compute_pipeline_exit_code(
    failure_report: FailureReport,
    *,
    batch_ok_count: int = 0,
    has_download_error: bool = False,
) -> int:
    """exit code: 0=성공, 1=입력오류, 2=실패/부분실패/마감경과."""
    if failure_report.exit_code == 1:
        return 1
    if has_download_error:
        return 2
    if any(a.code == "DEADLINE_PAST" for a in failure_report.advices):
        return 2
    if failure_report.exit_code >= 2 and batch_ok_count == 0:
        return 2
    if failure_report.exit_code >= 2 and batch_ok_count > 0:
        return 2  # 부분 성공도 2 (정직)
    if batch_ok_count > 0:
        return 0
    return failure_report.exit_code or 2
