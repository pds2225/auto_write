"""NotebookLM 상태머신·업로드 게이트·selector·고정 설명."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from auto_write.image_automation.notebooklm_browser import (
    BrowserSessionStub,
    NotebookLMBrowser,
    SourceItem,
)
from auto_write.image_automation.notebooklm_selectors import (
    SelectorAmbiguityError,
    candidates_for,
    resolve_unique_selector,
)
from auto_write.image_automation.notebooklm_state import (
    EXPECTED_SLIDE_DESCRIPTION,
    ExternalUploadBlocked,
    NotebookLMState,
    NotebookLMStateMachine,
    can_click_generate,
    verify_slide_description_fixture,
)
from auto_write.image_automation.download_verify import pick_download_event_file, sniff_kind, verify_download

# 이 저장소 루트(= git origin 을 읽을 수 있는 경로). 개발자 PC 의 임시 워크트리
# 절대경로를 테스트에 박아 두면 그 폴더가 정리된 뒤 영구 실패한다(WinError 267).
REPO_ROOT = Path(__file__).resolve().parents[2]


def _pdf(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello")
    doc.save(path)
    doc.close()
    return path


def test_slide_description_fixture_bytes():
    actual = verify_slide_description_fixture()
    assert actual == EXPECTED_SLIDE_DESCRIPTION.encode("utf-8")
    assert actual.decode("utf-8").count("\n") == 6  # 7 lines


def test_external_upload_blocked_file_chooser_zero():
    sm = NotebookLMStateMachine(allow_external_upload=False)
    sm.transition(NotebookLMState.EXTERNAL_UPLOAD_CONSENT)
    sm.transition(NotebookLMState.AUTH_CHECK)
    sm.transition(NotebookLMState.FIND_OR_CREATE_NOTEBOOK)
    sm.transition(NotebookLMState.UNCHECK_ALL_SOURCES)
    with pytest.raises(ExternalUploadBlocked):
        sm.transition(NotebookLMState.SELECT_OR_UPLOAD_PDF)
    with pytest.raises(ExternalUploadBlocked):
        sm.record_file_chooser()
    assert sm.file_chooser_calls == 0


def test_browser_gate_without_allow(tmp_path: Path, monkeypatch):
    # repo 이름은 origin URL 에서 나온다. 개발자 PC 의 임시 워크트리 경로를 박아 두면
    # 그 폴더가 정리된 뒤 영구 실패하므로(WinError 267) 항상 이 저장소 루트를 쓴다.
    browser = NotebookLMBrowser(allow_external_upload=False, cwd=REPO_ROOT)
    result = browser.run_pre_upload_gate()
    assert result.code == "external_upload_blocked"
    assert result.file_chooser_calls == 0
    assert result.repo_name == "auto_write"


def test_selector_ko_en_registry():
    ko = candidates_for("generate", "ko")
    en = candidates_for("generate", "en")
    assert any(c.name == "생성" for c in ko)
    assert any(c.name == "Generate" for c in en)


def test_ambiguous_selector_no_click():
    with pytest.raises(SelectorAmbiguityError):
        resolve_unique_selector("generate", "ko", match_fn=lambda c: True)  # all match


def test_unregistered_locale_no_click():
    with pytest.raises(SelectorAmbiguityError):
        candidates_for("generate", "ja")  # type: ignore[arg-type]


def test_source_uncheck_then_one_checked(tmp_path: Path):
    pdf = _pdf(tmp_path / "a.pdf")
    session = BrowserSessionStub(
        locale="ko",
        notebooks=["auto_write"],
        sources=[
            SourceItem("other.pdf", checked=True),
            SourceItem("noise.pdf", checked=True),
        ],
        visible_labels={
            "슬라이드 자료",
            "발표자 슬라이드",
            "짧게",
            "생성",
        },
        notebook_url_id="nb-1",
        downloaded=_pdf(tmp_path / "dl.pdf"),
    )
    browser = NotebookLMBrowser(
        allow_external_upload=True,
        cwd=REPO_ROOT,
        session=session,
    )
    result = browser.run_stub_happy_path(pdf, download_to=session.downloaded)
    assert result.code == "done"
    assert result.checked_source_count == 1
    assert result.generate_clicks == 1
    assert result.file_chooser_calls == 1
    assert sum(1 for s in session.sources if s.checked) == 1
    assert session.description == EXPECTED_SLIDE_DESCRIPTION


def test_generate_only_once():
    sm = NotebookLMStateMachine(allow_external_upload=True)
    for st in [
        NotebookLMState.EXTERNAL_UPLOAD_CONSENT,
        NotebookLMState.AUTH_CHECK,
        NotebookLMState.FIND_OR_CREATE_NOTEBOOK,
        NotebookLMState.UNCHECK_ALL_SOURCES,
        NotebookLMState.SELECT_OR_UPLOAD_PDF,
        NotebookLMState.VERIFY_EXACTLY_ONE_SOURCE,
        NotebookLMState.OPEN_STUDIO_SLIDES,
        NotebookLMState.SELECT_PRESENTER,
        NotebookLMState.SELECT_SHORT,
        NotebookLMState.SET_DESCRIPTION,
        NotebookLMState.GENERATE,
    ]:
        sm.transition(st)
    sm.record_generate_click()
    with pytest.raises(ValueError):
        sm.record_generate_click()


def test_manual_action_attempt_bump():
    sm = NotebookLMStateMachine(allow_external_upload=True)
    sm.transition(NotebookLMState.EXTERNAL_UPLOAD_CONSENT)
    sm.transition(NotebookLMState.AUTH_CHECK)
    sm.transition(NotebookLMState.MANUAL_ACTION)
    assert sm.bump_attempt_for_resume() == 2
    assert sm.generate_clicks == 0


def test_can_click_generate_requires_one_source():
    assert can_click_generate(checked_source_count=1, settings_ok=True)
    assert not can_click_generate(checked_source_count=2, settings_ok=True)
    assert not can_click_generate(checked_source_count=1, settings_ok=False)


def test_download_rejects_stale_and_bad_magic(tmp_path: Path):
    stale = tmp_path / "old.pdf"
    _pdf(stale)
    with pytest.raises(ValueError, match="stale"):
        verify_download(stale, allowed_preexisting={stale})
    bad = tmp_path / "x.bin"
    bad.write_bytes(b"not-a-pdf")
    with pytest.raises(ValueError):
        sniff_kind(bad)
    good = _pdf(tmp_path / "new.pdf")
    picked = pick_download_event_file(good, tmp_path)
    verified = verify_download(picked, allowed_preexisting={stale})
    assert verified.kind == "pdf"
    assert verified.page_or_slide_count == 1


def test_captcha_manual_action(tmp_path: Path):
    session = BrowserSessionStub(captcha=True, notebooks=["auto_write"])
    browser = NotebookLMBrowser(
        allow_external_upload=True,
        cwd=REPO_ROOT,
        session=session,
    )
    result = browser.run_pre_upload_gate()
    assert result.code == "auth_or_captcha"
    assert result.state == NotebookLMState.MANUAL_ACTION
