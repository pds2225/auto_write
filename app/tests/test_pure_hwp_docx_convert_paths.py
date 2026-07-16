"""hwp_docx_convert 경로 해석·안전 가드 단위 안전망(순수 로직).

변환 자체는 한글(Hancom) COM 이 필요해 이 세션에서 실제로 돌리지 않는다. 대신
COM 을 타기 전에 실행되는 순수 로직만 검증한다:

- ``_resolve_paths`` : 출력 경로 결정 + **원본 덮어쓰기 금지**(out==in → ValueError)
  + 없는 입력(FileNotFoundError) — 평생목표(무손실 변환)의 안전 전제.
- ``_nonempty_file`` : 변환 산출물이 실제로 생겼는지(빈 파일이면 실패로 취급).
- ``convert``       : 확장자로 방향을 고르되, 지원 밖 확장자는 COM 접근 전에
  ValueError 로 즉시 거른다(파일 존재 여부와 무관한 순수 분기).
"""

from __future__ import annotations

import pytest

from auto_write.services.hwp_docx_convert import (
    _nonempty_file,
    _resolve_paths,
    convert,
)


def _touch(path, data: bytes = b"x") -> None:
    path.write_bytes(data)


# --- _resolve_paths: 기본 출력 경로 --------------------------------------------

def test_resolve_paths_default_suffix(tmp_path) -> None:
    src = tmp_path / "양식.hwp"
    _touch(src)
    got_src, dst, prev_bak = _resolve_paths(src, None, ".docx")
    assert got_src == src
    assert dst.name == "양식.docx"          # 같은 이름 + 기본 확장자
    assert dst.parent == tmp_path
    assert prev_bak == ""                   # 기존 출력이 없으면 백업 없음


def test_resolve_paths_explicit_output(tmp_path) -> None:
    src = tmp_path / "a.docx"
    _touch(src)
    out = tmp_path / "sub" / "결과.hwp"
    _, dst, prev_bak = _resolve_paths(src, out, ".hwp")
    assert dst == out
    assert dst.parent.exists()              # 출력 폴더를 만들어 둔다
    assert prev_bak == ""


def test_resolve_paths_backs_up_existing_output(tmp_path) -> None:
    # 기존 출력 파일(사용자가 수정했을 수 있음)은 무경고 덮어쓰기 대신
    # 타임스탬프 백업(_prev...)으로 옮겨 보존한다(2026-07 원본 사양).
    from pathlib import Path

    src = tmp_path / "양식.hwp"
    _touch(src)
    out = tmp_path / "양식.docx"
    _touch(out, b"old-output")
    _, dst, prev_bak = _resolve_paths(src, out, ".docx")
    assert dst == out
    assert prev_bak != ""
    bak = Path(prev_bak)
    assert bak.exists() and bak.read_bytes() == b"old-output"   # 내용 보존
    assert "_prev" in bak.name and bak.suffix == ".docx"
    assert not out.exists()                 # 원래 자리는 새 산출물을 위해 비워 둠


# --- _resolve_paths: 안전 가드 -------------------------------------------------

def test_resolve_paths_refuses_overwrite_source(tmp_path) -> None:
    src = tmp_path / "원본.hwp"
    _touch(src)
    with pytest.raises(ValueError):
        _resolve_paths(src, src, ".docx")   # out==in → 원본 덮어쓰기 금지


def test_resolve_paths_refuses_overwrite_via_relative_alias(tmp_path) -> None:
    # 문자열은 달라도 resolve 하면 같은 파일이면 거부(경로 별칭 우회 차단)
    src = tmp_path / "원본.hwp"
    _touch(src)
    alias = tmp_path / "sub" / ".." / "원본.hwp"
    with pytest.raises(ValueError):
        _resolve_paths(src, alias, ".docx")


def test_resolve_paths_missing_input_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        _resolve_paths(tmp_path / "없는파일.hwp", None, ".docx")


# --- _nonempty_file ------------------------------------------------------------

def test_nonempty_file(tmp_path) -> None:
    missing = tmp_path / "nope.docx"
    assert _nonempty_file(missing) is False

    empty = tmp_path / "empty.docx"
    empty.write_bytes(b"")
    assert _nonempty_file(empty) is False

    filled = tmp_path / "filled.docx"
    filled.write_bytes(b"data")
    assert _nonempty_file(filled) is True


# --- convert: 지원 밖 확장자는 COM 접근 전에 거른다(순수 분기) ------------------

def test_convert_rejects_unsupported_extension(tmp_path) -> None:
    # 파일이 없어도(존재 확인 전에) 확장자로 즉시 ValueError — COM 을 타지 않는다
    with pytest.raises(ValueError):
        convert(tmp_path / "문서.txt")
    with pytest.raises(ValueError):
        convert("아무거나.pdf")
