"""user_pipeline_config.py — mail→auto_write 파이프라인 사용자 기본값.

완성본 폴더(source-pool) 등을 저장해 매 실행마다 다시 묻지 않게 한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_APP_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _APP_ROOT / "config" / "user_pipeline.json"
_MAIL_CONFIG_PATH = Path(r"D:\mail\scripts\notice_download_config.json")

_DEFAULTS: dict[str, Any] = {
    "default_source_pool": "",
    "default_out_subdir": "filled",
    "mail_out_dir": "",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_config() -> dict[str, Any]:
    """사용자 파이프라인 설정을 읽는다(없으면 기본값)."""
    cfg = dict(_DEFAULTS)
    cfg.update(_read_json(_CONFIG_PATH))
    if not cfg.get("mail_out_dir") and _MAIL_CONFIG_PATH.is_file():
        mail_cfg = _read_json(_MAIL_CONFIG_PATH)
        if mail_cfg.get("out_dir"):
            cfg["mail_out_dir"] = str(mail_cfg["out_dir"])
    return cfg


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    """설정을 병합 저장하고 최종 dict 를 반환한다."""
    cfg = load_config()
    for key, val in updates.items():
        if key in _DEFAULTS:
            cfg[key] = val
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cfg


def resolve_source_pool(explicit: str | None) -> str:
    """CLI --source-pool 또는 저장된 기본값."""
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    pool = load_config().get("default_source_pool") or ""
    if not pool:
        raise ValueError(
            "완성본 폴더(--source-pool)가 필요합니다. "
            "한 번 지정할 때 --save-defaults 를 붙이면 다음부터 자동으로 씁니다.")
    return pool


def resolve_mail_out_dir(explicit: str | None) -> Path:
    if explicit and str(explicit).strip():
        return Path(explicit)
    cfg = load_config()
    raw = cfg.get("mail_out_dir") or ""
    if not raw:
        raise ValueError("다운로드 저장 폴더가 설정되지 않았습니다.")
    return Path(raw)
