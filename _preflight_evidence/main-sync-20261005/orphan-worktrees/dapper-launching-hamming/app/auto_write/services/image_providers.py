"""image_providers.py

요약 인포그래픽 이미지 생성 provider. 사용자 승인된 유료 경로만 사용한다:
- Gemini "Nano Banana" (gemini-2.5-flash-image) via google-genai  [1순위]
- OpenAI 이미지 (gpt-image-1) via openai                          [2순위]

GENERATE_MISSING(P5/M4) 전용 경로는 ``generate_missing_gpt_image`` 만 사용한다.
이 경로는 Gemini를 호출하지 않고 gpt-image-1 만 허용한다.

원칙:
- 키가 없으면 외부 호출하지 않는다(무료 폴백은 호출측 image_service가 담당).
- API 키(Secret)는 settings에서만 읽고 절대 출력/로그하지 않는다.
- 사진(photorealism) 금지, 핵심 내용을 요약하는 인포그래픽 스타일 강제.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..utils import log_line

GPT_IMAGE_MODEL = "gpt-image-1"

INFOGRAPHIC_STYLE = (
    "Clean Korean business infographic that SUMMARIZES the key points as a diagram. "
    "Flat vector style with boxes, arrows and simple icons, large readable Korean labels, "
    "high contrast, white background. Absolutely no photorealism, no photograph, no human faces."
)


def _gemini_generate(api_key: str, model: str, prompt: str, out_path: Path) -> bool:
    try:
        from google import genai
    except Exception:
        return False
    try:
        client = genai.Client(api_key=api_key)
        full = f"{INFOGRAPHIC_STYLE}\n\n[요약 대상]\n{prompt}"
        resp = client.models.generate_content(model=model, contents=full)
        for cand in getattr(resp, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                data = getattr(inline, "data", None) if inline else None
                if data:
                    out_path.write_bytes(data)
                    return out_path.exists() and out_path.stat().st_size > 0
        return False
    except Exception as exc:
        log_line(f"[WARN] Gemini 이미지 생성 실패: {type(exc).__name__}")
        return False


def _openai_generate(openai_service: Any, prompt: str, out_path: Path) -> bool:
    try:
        styled = f"{INFOGRAPHIC_STYLE}\n\n[요약 대상]\n{prompt}"
        return bool(openai_service.generate_image_file(styled, out_path))
    except Exception as exc:
        log_line(f"[WARN] OpenAI 이미지 생성 실패: {type(exc).__name__}")
        return False


def generate_missing_gpt_image(
    settings: Any,
    openai_service: Any,
    prompt: str,
    out_path: Path,
    *,
    model: str = GPT_IMAGE_MODEL,
) -> bool:
    """GENERATE_MISSING 전용: gpt-image-1만 호출. Gemini 경로 사용 금지."""
    if settings is None or not getattr(settings, "has_openai", False):
        return False
    if model != GPT_IMAGE_MODEL:
        log_line(f"[WARN] GENERATE_MISSING model must be {GPT_IMAGE_MODEL}, got {model}")
        return False
    configured = str(getattr(settings, "openai_image_model", GPT_IMAGE_MODEL) or GPT_IMAGE_MODEL)
    if configured != GPT_IMAGE_MODEL:
        log_line(
            f"[WARN] settings.openai_image_model={configured!r} "
            f"but GENERATE_MISSING requires {GPT_IMAGE_MODEL}"
        )
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        styled = f"{INFOGRAPHIC_STYLE}\n\n[요약 대상]\n{prompt}"
        return bool(openai_service.generate_image_file(styled, out_path))
    except Exception as exc:
        log_line(f"[WARN] GENERATE_MISSING gpt-image-1 실패: {type(exc).__name__}")
        return False


def build_missing_gpt_writer(
    settings: Any,
    openai_service: Any,
) -> Callable[[str, Path], None] | None:
    """OpenAI 키가 있을 때만 gpt-image-1 writer를 반환한다."""
    if settings is None or not getattr(settings, "has_openai", False):
        return None

    def _writer(prompt: str, out_path: Path, *, model: str = GPT_IMAGE_MODEL) -> None:
        if not generate_missing_gpt_image(settings, openai_service, prompt, out_path, model=model):
            raise OSError("gpt-image-1 generation failed")

    return _writer


def generate_infographic(settings: Any, openai_service: Any, prompt: str, out_path: Path) -> str:
    """승인된 유료 provider로 인포그래픽 생성 시도. 성공 시 provider명('gemini'/'openai'), 실패/무키 시 ''."""
    if settings is None:
        return ""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if getattr(settings, "has_gemini", False):
        model = getattr(settings, "gemini_image_model", "gemini-2.5-flash-image")
        if _gemini_generate(settings.gemini_api_key, model, prompt, out_path):
            log_line(f"[IMG] Gemini Nano Banana 인포그래픽 생성: {out_path.name}")
            return "gemini"
    if getattr(settings, "has_openai", False):
        if _openai_generate(openai_service, prompt, out_path):
            return "openai"
    return ""
