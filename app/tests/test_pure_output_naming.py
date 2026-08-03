"""test_pure_output_naming.py — 제출 파일명 규칙 안전망 (순수 함수).

``output_naming`` 은 제출본 파일 이름을 "어디서 실행하든 똑같이" 만드는 규칙이다
(``{양식접두}_{성명}.hwpx``). 파일을 만들지도, 폴더를 만들지도 않는 순수 문자열/
경로 계산이라 디스크 없이 그대로 검증한다. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- 파일명에 쓸 수 없는 글자(``< > : " / \\ | ? *``·제어문자)와 공백은 제거된다.
- 지우고 나서 남는 게 없으면 빈 이름 대신 fallback(기본 '미상')을 쓴다
  — 이름이 ``_.hwpx`` 처럼 깨지는 것을 막는다.
- ``resolve_submit_path`` 는 경로만 계산하고 폴더를 만들지 않는다(생성은 호출측 책임).
"""

from __future__ import annotations

from pathlib import Path

from auto_write.services.output_naming import (
    resolve_submit_path,
    sanitize_filename_part,
    submit_filename,
)


# --- sanitize_filename_part -------------------------------------------------

def test_sanitize_keeps_korean_and_drops_spaces():
    # 사람 이름 사이 공백은 붙여 쓴다(『박 다 솜』→『박다솜』).
    assert sanitize_filename_part("박 다 솜") == "박다솜"
    assert sanitize_filename_part("  전문상담위원  ") == "전문상담위원"


def test_sanitize_removes_windows_forbidden_characters():
    # 윈도우가 파일명에 금지하는 9종을 모두 제거한다.
    assert sanitize_filename_part('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"


def test_sanitize_removes_control_characters():
    # 탭·개행·NUL 같은 제어문자가 섞여도 파일명이 깨지지 않는다.
    assert sanitize_filename_part("박\t다\n솜\x00") == "박다솜"


def test_sanitize_falls_back_when_nothing_remains():
    # 전부 지워지면 빈 문자열이 아니라 fallback 을 쓴다(이름 깨짐 방지).
    assert sanitize_filename_part("") == "미상"
    assert sanitize_filename_part("   ") == "미상"
    assert sanitize_filename_part("///") == "미상"
    assert sanitize_filename_part("", fallback="신청서") == "신청서"


def test_sanitize_handles_none_like_input():
    # 호출측이 값을 못 채워 None 을 넘겨도 예외 없이 fallback.
    assert sanitize_filename_part(None) == "미상"  # type: ignore[arg-type]


# --- submit_filename --------------------------------------------------------

def test_submit_filename_default_shape():
    assert submit_filename(name="박다솜") == "전문상담위원_참여신청서_박다솜.hwpx"


def test_submit_filename_without_name_uses_fallback():
    # 성명 미상이어도 파일명은 항상 만들어진다(제출 직전에 사람이 알아볼 수 있게).
    assert submit_filename() == "전문상담위원_참여신청서_미상.hwpx"


def test_submit_filename_with_version_suffix():
    assert (
        submit_filename(name="박다솜", version="v2")
        == "전문상담위원_참여신청서_박다솜_v2.hwpx"
    )


def test_submit_filename_normalizes_extension_without_dot():
    # 'hwpx' 처럼 점 없이 넘겨도 '.hwpx' 로 정규화된다.
    assert submit_filename(name="박다솜", ext="hwpx").endswith(".hwpx")
    assert submit_filename(name="박다솜", ext=".pdf").endswith(".pdf")


def test_submit_filename_sanitizes_every_part():
    got = submit_filename(form_prefix="양식/1", name="박 다 솜", version="v 1")
    assert got == "양식1_박다솜_v1.hwpx"


def test_submit_filename_empty_prefix_uses_form_fallback():
    assert submit_filename(form_prefix="", name="박다솜") == "신청서_박다솜.hwpx"


# --- resolve_submit_path ----------------------------------------------------

def test_resolve_submit_path_joins_directory_and_name():
    p = resolve_submit_path("results", name="박다솜")
    assert isinstance(p, Path)
    assert p.name == "전문상담위원_참여신청서_박다솜.hwpx"
    assert p.parent == Path("results")


def test_resolve_submit_path_does_not_create_directory(tmp_path):
    # 경로만 계산한다 — 없는 폴더를 몰래 만들지 않는다(부수효과 0).
    target_dir = tmp_path / "not_created_yet"
    p = resolve_submit_path(target_dir, name="박다솜", version="v1")
    assert p.name == "전문상담위원_참여신청서_박다솜_v1.hwpx"
    assert not target_dir.exists()
