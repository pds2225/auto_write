"""test_pure_plan_builder.py — plan_builder 순수 로직 회귀.

파일 I/O·COM·네트워크 없이(외부 plan JSON 은 tmp_path 로만 로컬 검증)
`build_fill_plan` / `_load_external_plan` 의 결정론 동작을 고정한다.

고정하는 계약:
- organization_profile / project_meta['overview'] 의 라벨->값을 identity/overview 로 반영.
- 값이 빈 문자열/공백뿐인 항목은 버린다(허위 충전 금지 원칙).
- 외부 plan(fill_plan.json 우선, 없으면 <template_id>.json)이 있으면 병합/치환.
- identity/overview 는 프로젝트값 위에 외부값을 덮어쓰기 병합, 그 외 키는 그대로 치환.
- 외부값이 falsy([]/{}/"") 면 스킵(빈 항목으로 기존 값 지우지 않음).
- 손상 JSON·비-dict JSON·없는 파일은 조용히 {} 로 폴백.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from auto_write.services.plan_builder import _load_external_plan, build_fill_plan


def _proj(*, org=None, meta=None):
    return SimpleNamespace(organization_profile=org, project_meta=meta)


def _profile(template_id="tmpl-1"):
    return SimpleNamespace(template_id=template_id)


# --------------------------------------------------------------------------
# build_fill_plan — 프로젝트 데이터 → identity/overview
# --------------------------------------------------------------------------

def test_identity_built_from_organization_profile():
    plan = build_fill_plan(_profile(), _proj(org={"기업명": "밸류업", "대표자": "박다솜"}))
    assert plan["identity"] == {"기업명": "밸류업", "대표자": "박다솜"}
    assert "overview" not in plan


def test_overview_built_from_project_meta_overview():
    plan = build_fill_plan(_profile(), _proj(meta={"overview": {"아이템명": "오토라이트"}}))
    assert plan["overview"] == {"아이템명": "오토라이트"}
    assert "identity" not in plan


def test_blank_and_whitespace_values_are_dropped():
    org = {"기업명": "밸류업", "빈칸": "", "공백": "   ", "대표자": "박다솜"}
    plan = build_fill_plan(_profile(), _proj(org=org))
    # 빈 문자열/공백뿐인 값은 허위 충전 금지 원칙으로 제외.
    assert plan["identity"] == {"기업명": "밸류업", "대표자": "박다솜"}


def test_values_are_coerced_to_str():
    plan = build_fill_plan(_profile(), _proj(org={"인원": 5, "설립연도": 2020}))
    assert plan["identity"] == {"인원": "5", "설립연도": "2020"}


def test_empty_project_returns_empty_plan_without_external():
    assert build_fill_plan(_profile(), _proj()) == {}


def test_non_dict_org_is_ignored_gracefully():
    # organization_profile 가 dict 가 아니면(리스트 등) 조용히 무시.
    plan = build_fill_plan(_profile(), _proj(org=["not", "a", "dict"]))
    assert "identity" not in plan


def test_meta_without_overview_key_is_ignored():
    plan = build_fill_plan(_profile(), _proj(meta={"other": {"x": "y"}}))
    assert "overview" not in plan


def test_all_blank_identity_not_added():
    # 값이 전부 공백이면 identity 자체가 만들어지지 않는다.
    plan = build_fill_plan(_profile(), _proj(org={"a": "", "b": "  "}))
    assert "identity" not in plan


# --------------------------------------------------------------------------
# build_fill_plan — 외부 plan 병합/치환
# --------------------------------------------------------------------------

def _write_plan(dirpath, data, name="fill_plan.json"):
    p = dirpath / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_external_identity_overrides_and_extends(tmp_path):
    _write_plan(tmp_path, {"identity": {"기업명": "외부", "대표자": "외부대표"}})
    plan = build_fill_plan(
        _profile(), _proj(org={"기업명": "프로젝트"}), external_plan_dir=tmp_path
    )
    # 충돌 키는 외부값이 덮어쓰고, 새 키는 추가된다.
    assert plan["identity"] == {"기업명": "외부", "대표자": "외부대표"}


def test_external_only_identity_set_when_no_project_identity(tmp_path):
    _write_plan(tmp_path, {"identity": {"기업명": "외부만"}})
    plan = build_fill_plan(_profile(), _proj(), external_plan_dir=tmp_path)
    assert plan["identity"] == {"기업명": "외부만"}


def test_external_passthrough_keys_replace_directly(tmp_path):
    ext = {
        "row_rewrites": [{"anchor": "표1", "value": "채움"}],
        "replacements": {"__NAME__": "밸류업"},
        "replacements_prefix": {"prefix": "P"},
        "paragraph_fills": [{"label": "요약", "text": "내용"}],
    }
    _write_plan(tmp_path, ext)
    plan = build_fill_plan(_profile(), _proj(), external_plan_dir=tmp_path)
    for key, val in ext.items():
        assert plan[key] == val


def test_external_falsy_values_are_skipped(tmp_path):
    # 빈 리스트/딕트/문자열은 스킵 — 기존/부재 값을 빈 값으로 덮어쓰지 않는다.
    _write_plan(tmp_path, {"row_rewrites": [], "replacements": {}, "identity": {}})
    plan = build_fill_plan(
        _profile(), _proj(org={"기업명": "유지"}), external_plan_dir=tmp_path
    )
    assert "row_rewrites" not in plan
    assert "replacements" not in plan
    # 외부 identity 가 {} 라도 프로젝트 identity 는 보존.
    assert plan["identity"] == {"기업명": "유지"}


# --------------------------------------------------------------------------
# _load_external_plan — 파일 폴백/우선순위/방어
# --------------------------------------------------------------------------

def test_load_returns_empty_when_dir_is_none():
    assert _load_external_plan("tmpl-1", None) == {}


def test_load_returns_empty_when_no_files(tmp_path):
    assert _load_external_plan("tmpl-1", tmp_path) == {}


def test_load_prefers_fill_plan_over_template_named(tmp_path):
    _write_plan(tmp_path, {"src": "fill_plan"}, name="fill_plan.json")
    _write_plan(tmp_path, {"src": "template"}, name="tmpl-1.json")
    assert _load_external_plan("tmpl-1", tmp_path) == {"src": "fill_plan"}


def test_load_falls_back_to_template_named(tmp_path):
    _write_plan(tmp_path, {"src": "template"}, name="tmpl-1.json")
    assert _load_external_plan("tmpl-1", tmp_path) == {"src": "template"}


def test_load_corrupt_json_falls_through_to_empty(tmp_path):
    (tmp_path / "fill_plan.json").write_text("{ not valid json", encoding="utf-8")
    assert _load_external_plan("tmpl-1", tmp_path) == {}


def test_load_corrupt_first_then_valid_second(tmp_path):
    (tmp_path / "fill_plan.json").write_text("{bad", encoding="utf-8")
    _write_plan(tmp_path, {"src": "template"}, name="tmpl-1.json")
    # 손상된 fill_plan.json 은 건너뛰고 유효한 <template_id>.json 을 쓴다.
    assert _load_external_plan("tmpl-1", tmp_path) == {"src": "template"}


def test_load_non_dict_json_is_rejected(tmp_path):
    _write_plan(tmp_path, ["a", "list", "not", "dict"], name="fill_plan.json")
    assert _load_external_plan("tmpl-1", tmp_path) == {}


def test_load_accepts_string_dir_path(tmp_path):
    _write_plan(tmp_path, {"src": "fill_plan"})
    # external_plan_dir 이 str 이어도 Path 로 처리되어야 한다.
    assert _load_external_plan("tmpl-1", str(tmp_path)) == {"src": "fill_plan"}


def test_missing_template_id_defaults_to_empty_string(tmp_path):
    # profile.template_id 부재 시 "" 로 폴백해도 크래시 없이 외부 plan 을 로드한다.
    # (build_fill_plan 은 _EXTERNAL_KEYS 에 든 키만 반영하므로 실제 키로 검증.)
    _write_plan(tmp_path, {"replacements": {"__X__": "Y"}})
    prof = SimpleNamespace()  # template_id 없음
    plan = build_fill_plan(prof, _proj(), external_plan_dir=tmp_path)
    assert plan == {"replacements": {"__X__": "Y"}}


def test_build_ignores_external_keys_outside_whitelist(tmp_path):
    # _EXTERNAL_KEYS 화이트리스트 밖의 키(예: "src")는 반영하지 않는다(계약 고정).
    _write_plan(tmp_path, {"src": "무시됨", "replacements": {"a": "b"}})
    plan = build_fill_plan(_profile(), _proj(), external_plan_dir=tmp_path)
    assert "src" not in plan
    assert plan["replacements"] == {"a": "b"}
