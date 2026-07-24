"""NotebookLM 브라우저 자동화 (Playwright). 업로드는 --allow-external-upload 필수."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from auto_write.image_automation.notebooklm_selectors import (
    Locale,
    SelectorAmbiguityError,
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
from auto_write.image_automation.paths import anonymous_upload_name, sha256_file
from auto_write.image_automation.repo_name import RepoNameError, canonical_repo_name


@dataclass
class SourceItem:
    name: str
    checked: bool = False


@dataclass
class BrowserSessionStub:
    """단위테스트용 가상 NotebookLM UI."""

    locale: Locale = "ko"
    logged_in: bool = True
    captcha: bool = False
    notebooks: list[str] = field(default_factory=list)
    sources: list[SourceItem] = field(default_factory=list)
    visible_labels: set[str] = field(default_factory=set)
    description: str = ""
    generate_clicks: int = 0
    file_chooser_calls: int = 0
    downloaded: Path | None = None
    header_title: str = ""
    notebook_url_id: str = ""

    def match_label(self, name: str) -> bool:
        return name in self.visible_labels


@dataclass
class NotebookLMRunResult:
    state: NotebookLMState
    attempt: int
    file_chooser_calls: int
    generate_clicks: int
    repo_name: str = ""
    origin_url_hash: str = ""
    upload_name: str = ""
    checked_source_count: int | None = None
    download_path: Path | None = None
    code: str = ""
    draft: bool = False
    prompt_hash: str = ""


def _origin_hash(origin_url: str) -> str:
    return hashlib.sha256(origin_url.encode("utf-8")).hexdigest()


class NotebookLMBrowser:
    """
    실제 Playwright 세션 또는 stub 세션을 구동.
    외부 업로드는 allow_external_upload=True 일 때만 file chooser 호출.
    """

    def __init__(
        self,
        *,
        allow_external_upload: bool = False,
        locale: Locale = "ko",
        cwd: Path | None = None,
        session: BrowserSessionStub | None = None,
        attempt: int = 1,
    ):
        self.allow_external_upload = allow_external_upload
        self.locale = locale
        self.cwd = Path(cwd) if cwd else Path.cwd()
        self.session = session
        self.sm = NotebookLMStateMachine(
            allow_external_upload=allow_external_upload,
            attempt=attempt,
        )
        self._click_log: list[str] = []

    def click_semantic(self, step: str, match_fn: Callable[..., bool] | None = None) -> None:
        def _match(cand):
            if match_fn is not None:
                return match_fn(cand)
            if self.session is None:
                return False
            return self.session.match_label(cand.name)

        cand = resolve_unique_selector(step, self.locale, _match)
        self._click_log.append(f"{cand.role}:{cand.name}")
        if self.session is not None:
            # keep stub in sync for generate
            if step == "generate":
                self.session.generate_clicks += 1

    def ensure_external_consent(self) -> None:
        self.sm.transition(NotebookLMState.EXTERNAL_UPLOAD_CONSENT)
        if not self.allow_external_upload:
            raise ExternalUploadBlocked(
                "실행별 --allow-external-upload 없이는 외부 업로드를 진행하지 않습니다."
            )
        self.sm.transition(NotebookLMState.AUTH_CHECK)

    def open_file_chooser(self) -> None:
        self.sm.record_file_chooser()
        if self.session is not None:
            self.session.file_chooser_calls += 1

    def uncheck_all_sources(self) -> None:
        if self.session is None:
            return
        for s in self.session.sources:
            s.checked = False

    def select_only_source(self, upload_name: str) -> int:
        if self.session is None:
            return 0
        count = 0
        for s in self.session.sources:
            s.checked = s.name == upload_name
            if s.checked:
                count += 1
        return count

    def set_description_exact(self) -> bytes:
        prompt = verify_slide_description_fixture()
        text = prompt.decode("utf-8")
        assert text == EXPECTED_SLIDE_DESCRIPTION
        if self.session is not None:
            self.session.description = text
        return prompt

    def generate_once(self, *, checked_source_count: int, settings_ok: bool) -> None:
        if not can_click_generate(checked_source_count=checked_source_count, settings_ok=settings_ok):
            raise ValueError("생성 사전조건 미충족 (checked_source_count==1 && settings_ok)")
        self.sm.transition(NotebookLMState.GENERATE)
        self.sm.record_generate_click()
        self.click_semantic("generate")
        self.sm.transition(NotebookLMState.WAIT_READY)

    def mark_manual(self, code: str) -> NotebookLMRunResult:
        self.sm.transition(NotebookLMState.MANUAL_ACTION)
        return NotebookLMRunResult(
            state=self.sm.state,
            attempt=self.sm.attempt,
            file_chooser_calls=self.sm.file_chooser_calls,
            generate_clicks=self.sm.generate_clicks,
            code=code,
            draft=True,
        )

    def prepare_upload_name(self, pdf_path: Path, repo_name: str) -> str:
        digest = sha256_file(pdf_path)
        return anonymous_upload_name(repo_name, digest)

    def run_pre_upload_gate(self) -> NotebookLMRunResult:
        """업로드 없이 AUTH_CHECK까지. allow 없으면 여기서 중단."""
        try:
            repo_name, origin = canonical_repo_name(self.cwd)
        except RepoNameError as exc:
            self.sm.transition(NotebookLMState.FAIL)
            return NotebookLMRunResult(
                state=self.sm.state,
                attempt=self.sm.attempt,
                file_chooser_calls=0,
                generate_clicks=0,
                code=str(exc),
                draft=True,
            )

        self.sm.transition(NotebookLMState.EXTERNAL_UPLOAD_CONSENT)
        if not self.allow_external_upload:
            return NotebookLMRunResult(
                state=self.sm.state,
                attempt=self.sm.attempt,
                file_chooser_calls=0,
                generate_clicks=0,
                repo_name=repo_name,
                origin_url_hash=_origin_hash(origin),
                code="external_upload_blocked",
                draft=True,
            )
        self.sm.transition(NotebookLMState.AUTH_CHECK)
        if self.session is not None and (self.session.captcha or not self.session.logged_in):
            return self.mark_manual("auth_or_captcha")
        return NotebookLMRunResult(
            state=self.sm.state,
            attempt=self.sm.attempt,
            file_chooser_calls=0,
            generate_clicks=0,
            repo_name=repo_name,
            origin_url_hash=_origin_hash(origin),
            code="ok",
        )

    def run_stub_happy_path(
        self,
        pdf_path: Path,
        *,
        download_to: Path | None = None,
    ) -> NotebookLMRunResult:
        """테스트용 stub 전체 경로 (실제 네트워크 없음)."""
        if self.session is None:
            raise RuntimeError("stub session 필요")
        gate = self.run_pre_upload_gate()
        if gate.code != "ok":
            return gate

        repo_name = gate.repo_name
        upload_name = self.prepare_upload_name(pdf_path, repo_name)

        # notebook uniqueness
        matches = [n for n in self.session.notebooks if n == repo_name]
        if len(matches) > 1:
            return self.mark_manual("ambiguous_notebook")
        if len(matches) == 0:
            self.session.notebooks.append(repo_name)
            self.session.header_title = repo_name
            self.session.notebook_url_id = "new-nb-1"
        else:
            self.session.header_title = repo_name
            self.session.notebook_url_id = self.session.notebook_url_id or "existing-nb-1"

        self.sm.transition(NotebookLMState.FIND_OR_CREATE_NOTEBOOK)
        self.sm.transition(NotebookLMState.UNCHECK_ALL_SOURCES)
        self.uncheck_all_sources()

        self.sm.transition(NotebookLMState.SELECT_OR_UPLOAD_PDF)
        self.open_file_chooser()
        # attach source
        if not any(s.name == upload_name for s in self.session.sources):
            self.session.sources.append(SourceItem(name=upload_name, checked=False))
        checked = self.select_only_source(upload_name)
        self.sm.transition(NotebookLMState.VERIFY_EXACTLY_ONE_SOURCE)
        if checked != 1:
            self.sm.transition(NotebookLMState.FAIL)
            return NotebookLMRunResult(
                state=self.sm.state,
                attempt=self.sm.attempt,
                file_chooser_calls=self.sm.file_chooser_calls,
                generate_clicks=0,
                repo_name=repo_name,
                origin_url_hash=gate.origin_url_hash,
                upload_name=upload_name,
                checked_source_count=checked,
                code="checked_source_count_mismatch",
                draft=True,
            )

        for step, state in [
            ("studio_slides", NotebookLMState.OPEN_STUDIO_SLIDES),
            ("presenter_slides", NotebookLMState.SELECT_PRESENTER),
            ("length_short", NotebookLMState.SELECT_SHORT),
        ]:
            self.sm.transition(state)
            try:
                self.click_semantic(step)
            except SelectorAmbiguityError:
                return self.mark_manual("ui_contract_changed")

        self.sm.transition(NotebookLMState.SET_DESCRIPTION)
        prompt = self.set_description_exact()
        prompt_hash = hashlib.sha256(prompt).hexdigest()

        self.generate_once(checked_source_count=1, settings_ok=True)
        self.sm.transition(NotebookLMState.DOWNLOAD)
        dl = download_to
        if dl is None and self.session.downloaded is not None:
            dl = self.session.downloaded
        self.sm.transition(NotebookLMState.VERIFY_FILE)
        self.sm.transition(NotebookLMState.VERIFY_CITATIONS)
        self.sm.transition(NotebookLMState.DONE)
        return NotebookLMRunResult(
            state=self.sm.state,
            attempt=self.sm.attempt,
            file_chooser_calls=self.sm.file_chooser_calls,
            generate_clicks=self.sm.generate_clicks,
            repo_name=repo_name,
            origin_url_hash=gate.origin_url_hash,
            upload_name=upload_name,
            checked_source_count=1,
            download_path=dl,
            code="done",
            prompt_hash=prompt_hash,
        )


def summarize_upload_consent(
    *,
    provider: str,
    anon_name: str,
    sha256: str,
    page_count: int,
) -> dict[str, Any]:
    """콘솔/리포트용 비식별 업로드 요약 (원문·Secret 미포함)."""
    return {
        "provider": provider,
        "anonymous_filename": anon_name,
        "sha256_prefix": sha256[:8],
        "page_count": page_count,
    }
