"""usage_acceptance 제출 게이트 명명 정책·마스킹 판정 단위 안전망.

- ``force_draft_name`` : 제출불가 파일에 ``_DRAFT`` 를 강제하는 **정책 단일 출처**.
  기존 테스트가 다루지 않던 분기(멱등·원본 충돌 시 _DRAFT2 폴백·기본 rename)를
  보강한다. 이 명명이 어긋나면 제출불가 문서가 깨끗한 이름으로 유출된다(게이트 우회).
- ``_is_masked_value`` : 블라인드 심사용 마스킹(○○○/OOO) 판정. 영문 실단어(O2O 등)를
  마스킹으로 오인하지 않아야 한다(오탐 시 실명 검출·마스킹 로직이 흔들린다).

파일 rename 은 tmp_path 안에서만 일어나며 COM/네트워크를 전혀 타지 않는다.
"""

from __future__ import annotations

from auto_write.services.usage_acceptance import _is_masked_value, force_draft_name


# --- force_draft_name: 멱등(이미 DRAFT 이면 그대로) ----------------------------

def test_force_draft_name_idempotent_for_draft_stem(tmp_path) -> None:
    p = tmp_path / "제출본_DRAFT.docx"
    p.write_bytes(b"x")
    new, err = force_draft_name(p)
    assert new == p and err == ""            # rename 하지 않음
    assert p.exists()                        # 파일 그대로


def test_force_draft_name_idempotent_for_draft2_stem(tmp_path) -> None:
    p = tmp_path / "제출본_DRAFT2.docx"
    p.write_bytes(b"x")
    new, err = force_draft_name(p)
    assert new == p and err == ""


# --- force_draft_name: 기본 rename(비-DRAFT → _DRAFT) --------------------------

def test_force_draft_name_renames_plain_file(tmp_path) -> None:
    src = tmp_path / "제출본.docx"
    src.write_text("산출물", encoding="utf-8")
    new, err = force_draft_name(src)
    assert err == ""
    assert new.name == "제출본_DRAFT.docx"
    assert new.read_text(encoding="utf-8") == "산출물"
    assert not src.exists()                  # 원래 이름은 사라진다(제출 이름 차단)


# --- force_draft_name: 목표 이름이 원본(avoid)과 겹치면 _DRAFT2 로 보존 ---------

def test_force_draft_name_avoids_clobbering_source(tmp_path) -> None:
    src = tmp_path / "X.docx"
    src.write_text("새 산출물", encoding="utf-8")
    avoid = tmp_path / "X_DRAFT.docx"        # 보존해야 할 입력 원본
    avoid.write_text("건드리면 안 되는 원본", encoding="utf-8")

    new, err = force_draft_name(src, avoid=avoid)
    assert err == ""
    assert new.name == "X_DRAFT2.docx"       # 충돌을 피해 _DRAFT2 로 마킹
    assert avoid.read_text(encoding="utf-8") == "건드리면 안 되는 원본"  # 원본 보존
    assert new.read_text(encoding="utf-8") == "새 산출물"


# --- _is_masked_value: 마스킹(○○○/OOO)만 True, 영문 실단어는 False -----------

def test_is_masked_value_true_for_masking() -> None:
    assert _is_masked_value("○○○") is True
    assert _is_masked_value("○길동") is True     # ○ 가 하나라도 있으면 마스킹으로
    assert _is_masked_value("OOO") is True        # 라틴 O 반복도 마스킹
    assert _is_masked_value("OO") is True


def test_is_masked_value_false_for_real_text() -> None:
    assert _is_masked_value("홍길동") is False
    assert _is_masked_value("") is False
    assert _is_masked_value("O2O") is False        # 영문 실단어(숫자 포함) 오인 금지
    assert _is_masked_value("GOOGLE") is False
