"""plan_builder.py

SubmittableFiller 용 plan(dict) 을 프로젝트 데이터에서 자동 도출한다.

범위(검토 반영, 의도적 축소):
- identity/overview: organization_profile / project_meta['overview'] 의 라벨->값을 그대로 사용
  (라벨 매칭 기반이라 표 좌표 불필요).
- row_rewrites/replacements/paragraph_fills: 표 좌표 의존이라 자동 추론하지 않고,
  양식별 외부 JSON(지정 디렉터리의 fill_plan.json 또는 <template_id>.json) 에서 로드.
- 자동 도출 불가 항목은 비워둔다(허위 충전 금지). 근거 부족 보고는 평가 루프(needs_input) 담당.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_EXTERNAL_KEYS = ("row_rewrites", "replacements", "replacements_prefix", "paragraph_fills", "identity", "overview")


def _load_external_plan(template_id: str, external_plan_dir: str | Path | None) -> dict[str, Any]:
    if not external_plan_dir:
        return {}
    d = Path(external_plan_dir)
    for path in (d / "fill_plan.json", d / f"{template_id}.json"):
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}


def build_fill_plan(profile: Any, project_input: Any, *, external_plan_dir: str | Path | None = None) -> dict[str, Any]:
    plan: dict[str, Any] = {}

    org = getattr(project_input, "organization_profile", None) or {}
    if isinstance(org, dict):
        identity = {str(k): str(v) for k, v in org.items() if str(v).strip()}
        if identity:
            plan["identity"] = identity

    meta = getattr(project_input, "project_meta", None) or {}
    overview = meta.get("overview") if isinstance(meta, dict) else None
    if isinstance(overview, dict):
        ov = {str(k): str(v) for k, v in overview.items() if str(v).strip()}
        if ov:
            plan["overview"] = ov

    template_id = str(getattr(profile, "template_id", "") or "")
    ext = _load_external_plan(template_id, external_plan_dir)
    for key in _EXTERNAL_KEYS:
        val = ext.get(key)
        if not val:
            continue
        if key in ("identity", "overview") and isinstance(val, dict) and isinstance(plan.get(key), dict):
            merged = dict(plan[key])
            merged.update({str(k): str(v) for k, v in val.items()})
            plan[key] = merged
        else:
            plan[key] = val
    return plan
