"""NotebookLM 상태 머신과 업로드 승인 게이트."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

PROMPT_FIXTURE = (
    Path(__file__).resolve().parent / "prompts" / "notebooklm_slide_description.ko.txt"
)


class NotebookLMState(str, Enum):
    OPEN = "OPEN"
    EXTERNAL_UPLOAD_CONSENT = "EXTERNAL_UPLOAD_CONSENT"
    AUTH_CHECK = "AUTH_CHECK"
    FIND_OR_CREATE_NOTEBOOK = "FIND_OR_CREATE_NOTEBOOK"
    UNCHECK_ALL_SOURCES = "UNCHECK_ALL_SOURCES"
    SELECT_OR_UPLOAD_PDF = "SELECT_OR_UPLOAD_PDF"
    VERIFY_EXACTLY_ONE_SOURCE = "VERIFY_EXACTLY_ONE_SOURCE"
    OPEN_STUDIO_SLIDES = "OPEN_STUDIO_SLIDES"
    SELECT_PRESENTER = "SELECT_PRESENTER"
    SELECT_SHORT = "SELECT_SHORT"
    SET_DESCRIPTION = "SET_DESCRIPTION"
    GENERATE = "GENERATE"
    WAIT_READY = "WAIT_READY"
    DOWNLOAD = "DOWNLOAD"
    VERIFY_FILE = "VERIFY_FILE"
    VERIFY_CITATIONS = "VERIFY_CITATIONS"
    DONE = "DONE"
    MANUAL_ACTION = "MANUAL_ACTION"
    FAIL = "FAIL"


# 허용된 전이 (부분 — 핵심 경로 + manual/fail)
ALLOWED_TRANSITIONS: dict[NotebookLMState, set[NotebookLMState]] = {
    NotebookLMState.OPEN: {
        NotebookLMState.EXTERNAL_UPLOAD_CONSENT,
        NotebookLMState.AUTH_CHECK,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.EXTERNAL_UPLOAD_CONSENT: {
        NotebookLMState.AUTH_CHECK,
        NotebookLMState.FAIL,
        NotebookLMState.MANUAL_ACTION,
    },
    NotebookLMState.AUTH_CHECK: {
        NotebookLMState.FIND_OR_CREATE_NOTEBOOK,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.FIND_OR_CREATE_NOTEBOOK: {
        NotebookLMState.UNCHECK_ALL_SOURCES,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.UNCHECK_ALL_SOURCES: {
        NotebookLMState.SELECT_OR_UPLOAD_PDF,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.SELECT_OR_UPLOAD_PDF: {
        NotebookLMState.VERIFY_EXACTLY_ONE_SOURCE,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.VERIFY_EXACTLY_ONE_SOURCE: {
        NotebookLMState.OPEN_STUDIO_SLIDES,
        NotebookLMState.FAIL,
        NotebookLMState.MANUAL_ACTION,
    },
    NotebookLMState.OPEN_STUDIO_SLIDES: {
        NotebookLMState.SELECT_PRESENTER,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.SELECT_PRESENTER: {
        NotebookLMState.SELECT_SHORT,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.SELECT_SHORT: {
        NotebookLMState.SET_DESCRIPTION,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.SET_DESCRIPTION: {
        NotebookLMState.GENERATE,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.GENERATE: {
        NotebookLMState.WAIT_READY,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.WAIT_READY: {
        NotebookLMState.DOWNLOAD,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.DOWNLOAD: {
        NotebookLMState.VERIFY_FILE,
        NotebookLMState.MANUAL_ACTION,
        NotebookLMState.FAIL,
    },
    NotebookLMState.VERIFY_FILE: {
        NotebookLMState.VERIFY_CITATIONS,
        NotebookLMState.FAIL,
        NotebookLMState.MANUAL_ACTION,
    },
    NotebookLMState.VERIFY_CITATIONS: {
        NotebookLMState.DONE,
        NotebookLMState.FAIL,
        NotebookLMState.MANUAL_ACTION,
    },
    NotebookLMState.MANUAL_ACTION: {
        NotebookLMState.OPEN,
        NotebookLMState.AUTH_CHECK,
        NotebookLMState.FIND_OR_CREATE_NOTEBOOK,
        NotebookLMState.WAIT_READY,
        NotebookLMState.FAIL,
    },
    NotebookLMState.DONE: set(),
    NotebookLMState.FAIL: set(),
}


class ExternalUploadBlocked(RuntimeError):
    """--allow-external-upload 없이 업로드 단계 진입 시."""

    code = "external_upload_blocked"


class NotebookLMStateMachine:
    def __init__(self, *, allow_external_upload: bool = False, attempt: int = 1):
        self.state = NotebookLMState.OPEN
        self.allow_external_upload = allow_external_upload
        self.attempt = attempt
        self.generate_clicks = 0
        self.file_chooser_calls = 0
        self.history: list[NotebookLMState] = [self.state]

    def transition(self, nxt: NotebookLMState) -> NotebookLMState:
        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if nxt not in allowed:
            raise ValueError(f"invalid transition {self.state} → {nxt}")
        if nxt == NotebookLMState.SELECT_OR_UPLOAD_PDF and not self.allow_external_upload:
            # AUTH_CHECK까지는 허용, 업로드는 차단
            raise ExternalUploadBlocked(
                "--allow-external-upload 없이는 NotebookLM PDF 업로드를 진행할 수 없습니다."
            )
        self.state = nxt
        self.history.append(nxt)
        return nxt

    def record_file_chooser(self) -> None:
        if not self.allow_external_upload:
            raise ExternalUploadBlocked(
                "--allow-external-upload 없이는 file chooser를 열 수 없습니다."
            )
        if self.state not in {
            NotebookLMState.SELECT_OR_UPLOAD_PDF,
            NotebookLMState.UNCHECK_ALL_SOURCES,
        }:
            raise ExternalUploadBlocked("현재 상태에서 file chooser 호출이 허용되지 않습니다.")
        self.file_chooser_calls += 1

    def record_generate_click(self) -> None:
        if self.state != NotebookLMState.GENERATE:
            raise ValueError("GENERATE 상태가 아닐 때 생성 클릭 금지")
        if self.generate_clicks >= 1:
            raise ValueError("생성 버튼은 attempt당 1회만 허용됩니다.")
        self.generate_clicks += 1

    def bump_attempt_for_resume(self) -> int:
        """MANUAL_ACTION 후 재개 시 attempt +1."""
        if self.state != NotebookLMState.MANUAL_ACTION:
            raise ValueError("MANUAL_ACTION 상태가 아니면 attempt를 올리지 않습니다.")
        self.attempt += 1
        self.generate_clicks = 0
        return self.attempt


def load_slide_description_bytes() -> bytes:
    """고정 설명 fixture를 UTF-8 byte-for-byte로 로드.

    파일 끝 단일 개행은 허용하고, 체크아웃 CRLF 는 LF 로 정규화한다.
    """
    raw = PROMPT_FIXTURE.read_bytes()
    raw = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    return raw


EXPECTED_SLIDE_DESCRIPTION = (
    "흰배경에 블루계열 혹은 무채색 텍스트사용. 단정하고 깔끔한 디자인. \n"
    "의미전달 최우선. 가독성, 가시성 중요\n"
    "여러항목을 나열할때는 가로로 나열했으면함\n"
    "하나의 텍스트상자에 행이 3줄초과되지않았으면함\n"
    "상세설명이아닌 키워드위주였으면함 최대 문장 1~2개까지허용\n"
    "출처와 자료를  기재(각주로 본문하단에 출처이름, 기관명, 년도 명기)\n"
    " 출처리스트는 별도로 제공해라. 자료명,기관명, URL필수"
)


def verify_slide_description_fixture() -> bytes:
    actual = load_slide_description_bytes()
    expected = EXPECTED_SLIDE_DESCRIPTION.encode("utf-8")
    if actual != expected:
        raise ValueError("notebooklm_slide_description.ko.txt 가 계획 고정문구와 byte 불일치")
    return actual


def can_click_generate(*, checked_source_count: int, settings_ok: bool) -> bool:
    return checked_source_count == 1 and settings_ok
