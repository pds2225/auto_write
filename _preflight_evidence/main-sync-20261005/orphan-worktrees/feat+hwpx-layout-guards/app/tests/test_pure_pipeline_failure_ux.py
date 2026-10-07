"""test_pure_pipeline_failure_ux.py — 파이프라인 실패 UX(정직 안내) 순수 로직 안전망.

pipeline_failure_ux 는 mail→auto_write 파이프라인의 실패를 비개발자용 한국어
메시지·exit code 로 분류한다. 네트워크·문서 열기 없이 dict/dataclass 입력만 받는
분류 함수들을 직접 검증한다. 야간 안전망(2026-07-16).

여기서 고정하는 계약:
- FailureReport.merge 는 (code, form, message) 중복을 제거하고 exit_code 는 최댓값.
- 로그인벽 도메인(sbiz24 등)은 '도구 버그가 아님'을 안내하고 다른 분류를 덮는다.
- 다운로드 실패 status → 코드 매핑(NO_ATTACHMENTS/PAGE_FETCH_FAILED/…),
  SSL 계열 오류는 전용 문구.
- 마감이 지난 공고는 DEADLINE_PAST(error)로 exit 2 — 헛수고 방지.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from auto_write.services.cross_form_autofill import BatchAutofillItem
from auto_write.services.pipeline_failure_ux import (
    FailureAdvice,
    FailureReport,
    _hint_for_batch_item,
    _parse_date_from_deadline,
    check_deadline_warning,
    classify_download_failure,
    classify_login_wall,
    collect_analysis_failures,
)


# --- FailureAdvice / FailureReport ----------------------------------------------

def test_as_line_prefix_and_form():
    assert FailureAdvice("C", "메시지", "error").as_line() == "[실패] 메시지"
    assert FailureAdvice("C", "메시지", "warn").as_line() == "[주의] 메시지"
    assert FailureAdvice("C", "메시지", "info").as_line() == "[안내] 메시지"
    assert FailureAdvice("C", "메시지", "???").as_line() == "[안내] 메시지"   # 미지 심각도 안전
    assert FailureAdvice("C", "메시지", "error", form="신청서.docx").as_line() \
        == "[실패] 신청서.docx — 메시지"


def test_report_merge_dedups_and_keeps_max_exit_code():
    a = FailureReport([FailureAdvice("X", "같은 메시지")], exit_code=0)
    b = FailureReport(
        [FailureAdvice("X", "같은 메시지"), FailureAdvice("Y", "다른 메시지")],
        exit_code=2,
    )
    a.merge(b)
    assert [adv.code for adv in a.advices] == ["X", "Y"]   # 중복 1건 제거
    assert a.exit_code == 2                                 # 최댓값 유지
    a.merge(FailureReport(exit_code=0))
    assert a.exit_code == 2                                 # 낮은 코드로 안 내려감
    assert a.lines() == ["[실패] 같은 메시지", "[실패] 다른 메시지"]


# --- _parse_date_from_deadline ----------------------------------------------------

def test_parse_date_korean_and_dotted_formats():
    assert _parse_date_from_deadline("접수기간: 2026년 7월 31일까지") == date(2026, 7, 31)
    assert _parse_date_from_deadline("~ 2026. 7. 3") == date(2026, 7, 3)
    assert _parse_date_from_deadline("2026-12-01 18:00") == date(2026, 12, 1)


def test_parse_date_invalid_or_missing_returns_none():
    assert _parse_date_from_deadline("") is None
    assert _parse_date_from_deadline("마감: 추후 공지") is None
    assert _parse_date_from_deadline("2026년 13월 40일") is None   # 달력에 없는 날짜


# --- classify_login_wall -----------------------------------------------------------

def test_login_wall_sbiz24_always_flagged():
    msg = classify_login_wall("https://www.sbiz24.kr/notice/1", [])
    assert "로그인" in msg and "도구 버그가 아닙니다" in msg


def test_login_wall_smes_needs_bad_status():
    # smes 계열은 실패 status 가 있어야 로그인벽으로 확정(정상 다운로드는 침묵).
    assert classify_login_wall("https://www.smes.go.kr/x", []) == ""
    msg = classify_login_wall(
        "https://www.smes.go.kr/x", [{"status": "NO_ATTACHMENTS"}])
    assert "로그인" in msg


def test_login_wall_other_domain_silent():
    assert classify_login_wall("https://www.bizinfo.go.kr/x", [{"status": "NO_ATTACHMENTS"}]) == ""


# --- classify_download_failure -----------------------------------------------------

def test_download_login_wall_short_circuits():
    rep = classify_download_failure(
        "https://sbiz24.kr/n/1", [{"status": "NO_ATTACHMENTS"}])
    assert [a.code for a in rep.advices] == ["LOGIN_WALL"]
    assert rep.exit_code == 2


def test_download_status_code_mapping():
    rep = classify_download_failure("https://ex.com", [
        {"status": "NO_ATTACHMENTS"},
        {"status": "EXTRACT_FAILED"},
        {"status": "DOWNLOAD_FAILED", "error": "HTTP 404"},
    ])
    codes = [a.code for a in rep.advices]
    assert codes == [
        "DOWNLOAD_NO_ATTACHMENTS", "DOWNLOAD_EXTRACT_FAILED", "DOWNLOAD_HTTP_FAILED"]
    assert any("HTTP 404" in a.message for a in rep.advices)


def test_download_page_failed_ssl_vs_generic():
    ssl_rep = classify_download_failure(
        "https://ex.com", [{"status": "PAGE_FETCH_FAILED", "error": "SSL: UNEXPECTED_EOF"}])
    assert "SSL" in ssl_rep.advices[0].message
    gen_rep = classify_download_failure(
        "https://ex.com", [{"status": "PAGE_FETCH_FAILED", "error": "timeout"}])
    assert "SSL" not in gen_rep.advices[0].message


def test_download_unknown_rc_and_folder_unresolved():
    rep = classify_download_failure("https://ex.com", [], proc_rc=1)
    assert [a.code for a in rep.advices] == ["DOWNLOAD_UNKNOWN"]

    rep2 = classify_download_failure("https://ex.com", [], folder_resolved=False)
    assert [a.code for a in rep2.advices] == ["DOWNLOAD_FOLDER_UNKNOWN"]


def test_download_all_fine_exit_zero():
    rep = classify_download_failure("https://ex.com", [{"status": "OK"}])
    assert rep.advices == [] and rep.exit_code == 0


# --- collect_analysis_failures / check_deadline_warning ----------------------------

def _analysis(tmp_path, *, deadline: str = "", forms=None, ann_path="공고.hwp", notes=None):
    ann = SimpleNamespace(key_info={"deadline": deadline}) if deadline else None
    return SimpleNamespace(
        folder=str(tmp_path / "없는폴더"),      # K-Startup 잡파일 검사는 폴더 없음 → 침묵
        announcement=ann,
        announcement_path=ann_path,
        forms=forms if forms is not None else ["form"],
        notes=notes or [],
    )


def test_deadline_past_is_error_exit2(tmp_path):
    rep = collect_analysis_failures(_analysis(tmp_path, deadline="2000년 1월 1일"))
    codes = [a.code for a in rep.advices]
    assert "DEADLINE_PAST" in codes and rep.exit_code == 2
    # 채팅 상단용 경고 문구도 같은 결과에서 나온다.
    assert "마감이 지났습니다" in check_deadline_warning(_analysis(tmp_path, deadline="2000년 1월 1일"))


def test_deadline_soon_is_warning_not_error(tmp_path):
    soon = date.today() + timedelta(days=2)
    rep = collect_analysis_failures(
        _analysis(tmp_path, deadline=f"{soon.year}년 {soon.month}월 {soon.day}일"))
    codes = [a.code for a in rep.advices]
    assert "DEADLINE_SOON" in codes and "DEADLINE_PAST" not in codes
    assert rep.exit_code == 0                      # 임박은 경고 — 파이프라인 계속


def test_no_forms_and_no_announcement_reported(tmp_path):
    rep = collect_analysis_failures(
        _analysis(tmp_path, forms=[], ann_path="", notes=["양식을 찾지 못했습니다"]))
    codes = [a.code for a in rep.advices]
    assert "NOTICE_NO_FORMS" in codes              # error — exit 2
    assert "NOTICE_NO_ANNOUNCEMENT" in codes       # warn
    assert "ANALYSIS_NOTE" in codes                # '찾지 못했' 노트 승계
    assert rep.exit_code == 2


# --- _hint_for_batch_item -----------------------------------------------------------

def _item(**kw) -> BatchAutofillItem:
    base = dict(target="폴더/신청서.docx", source="완성본.docx", output="out.docx")
    base.update(kw)
    return BatchAutofillItem(**base)


def test_hint_no_source_found():
    out = _hint_for_batch_item(_item(source="", ok=False))
    assert [a.code for a in out] == ["BATCH_NO_SOURCE"]
    assert out[0].form == "신청서.docx"            # 파일명만 노출(경로 아님)


def test_hint_unsupported_extension():
    out = _hint_for_batch_item(_item(ok=False, notes=["비지원 확장자: .pdf"]))
    assert [a.code for a in out] == ["FORM_UNSUPPORTED"]


def test_hint_transcribe_zero_is_warn():
    out = _hint_for_batch_item(_item(ok=False, transcribed=0, notes=["항목 불일치"]))
    assert [a.code for a in out] == ["BATCH_TRANSCRIBE_ZERO"]
    assert out[0].severity == "warn"


def test_hint_generic_failure_carries_notes():
    out = _hint_for_batch_item(_item(ok=False, transcribed=3, notes=["저장 실패"]))
    assert [a.code for a in out] == ["BATCH_ITEM_FAILED"]
    assert "저장 실패" in out[0].message


def test_hint_hwp_com_unavailable_after_docx_ok():
    out = _hint_for_batch_item(
        _item(ok=True, hwp_ok=False, output="결과.docx", notes=["한글 COM 미가용"]))
    assert [a.code for a in out] == ["HWP_COM_UNAVAILABLE"]
    assert out[0].severity == "warn"               # DOCX 는 성공 — 차단 아님


def test_hint_merge_cell_address_info():
    out = _hint_for_batch_item(
        _item(ok=True, hwp_ok=True, unmatched_targets=[{"target_label": "사업장 소재지"}]))
    assert [a.code for a in out] == ["MERGE_CELL_ADDRESS"]
    assert out[0].severity == "info"
