"""F7-B AI 시각 검수(Visual QA): 최종 PDF 전 페이지를 이미지로 렌더해 페이지별로 시각 검사한다.

- 결과 상태는 Status(PASS/FAIL/REVIEW/N/A/UNVERIFIED)만 쓰고, 최종 제출 여부는 판단하지 않는다.
- 외부 AI(openai/anthropic) 전송은 호출자가 개인정보 가림을 확인(redaction_confirmed=True)한
  경우에만, 그리고 텍스트 레이어에 주민번호 패턴이 없는 페이지에만 허용한다.
- API 키는 환경변수 이름으로만 언급하며 로그·예외·보고서에 값이 나오지 않게 정제한다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Collection, Protocol, runtime_checkable

from .status import Finding, Status, find_forbidden

ENV_PROVIDER = "AUTO_WRITE_VISUAL_QA_PROVIDER"
ENV_MODEL = "AUTO_WRITE_VISUAL_QA_MODEL"
ENV_OPENAI_KEY = "OPENAI_API_KEY"
ENV_ANTHROPIC_KEY = "ANTHROPIC_API_KEY"
DEFAULT_OPENAI_MODEL = "gpt-6.1-sol"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_DPI = 110

_RRN_RE = re.compile(r"\d{6}-?[1-4]\d{6}")
_KEY_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+\S+)")
_REPLACED = "[금지표현 제거]"

# 모델에 보낼 검사 항목과 JSON 응답 스키마(모듈 상수).
CHECK_ITEMS: tuple[str, ...] = (
    "글자 잘림", "표 넘침", "직인 위치 이탈·중복", "이미지 누락·비율 왜곡",
    "체크박스 상태", "주민등록번호 뒷자리 가림 상태", "비정상 페이지 분할", "페이지 순서",
)
RESPONSE_SCHEMA = '[{"code": "VISUAL_...", "status": "PASS|FAIL|REVIEW", "message": "...", "bbox": [x0, y0, x1, y1]}]'
PROMPT = (
    "다음은 문서 PDF 의 한 페이지 이미지다. 아래 항목을 시각적으로 검사해라: "
    + ", ".join(CHECK_ITEMS)
    + ". 오류가 의심되면 해당 영역의 bbox(페이지 기준 0~1 정규화 [x0,y0,x1,y1])를 포함해라. "
    "신청서 본문에 적힌 신청자 성명·생년월일·연락처·주소는 제출용 정보이므로 보이는 것이 정상이며 가림 오류로 보고하지 마라"
    "(주민등록번호 뒷자리처럼 가려야 하는 값이 보일 때만 보고). "
    "최종 제출 여부는 판단하지 말고 관찰한 사실만 적어라. "
    "JSON 배열만 응답해라(설명·코드펜스 금지). 이상이 없으면 빈 배열 []. 스키마: " + RESPONSE_SCHEMA
)


def scrub(text: str) -> str:
    """오류 문자열에서 API 키로 보이는 값을 지운다."""
    out = str(text)
    for env in (ENV_OPENAI_KEY, ENV_ANTHROPIC_KEY):
        val = os.environ.get(env, "")
        if val and len(val) >= 6:
            out = out.replace(val, "[KEY]")
    return _KEY_RE.sub("[KEY]", out)


def make_finding(code: str, status: Status, message: str, *, source: str, page: int | None = None,
                 evidence: str = "", meta: dict[str, Any] | None = None) -> Finding:
    """금지 표현이 섞여도 예외 없이 치환해 Finding 을 만든다."""
    for phrase in find_forbidden(message) + find_forbidden(evidence):
        message = message.replace(phrase, _REPLACED)
        evidence = evidence.replace(phrase, _REPLACED)
    return Finding(code=code, status=status, message=message, source=source, page=page,
                   evidence=evidence, meta=dict(meta or {}))


# ───────────────────────── provider ─────────────────────────

@runtime_checkable
class VisualQAProvider(Protocol):
    name: str
    model: str
    external: bool  # True 면 이미지가 외부 서비스로 전송된다
    stats: dict[str, Any]

    def inspect_page(self, page_png: bytes, page_no: int, context: dict) -> list[Finding]: ...


def _new_stats() -> dict[str, Any]:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0}


class NoneProvider:
    """외부 호출 없이 전 페이지를 UNVERIFIED 로 보고하는 fallback."""

    name = "none"
    external = False

    def __init__(self, model: str = "") -> None:
        self.model = model
        self.stats = _new_stats()

    def inspect_page(self, page_png: bytes, page_no: int, context: dict) -> list[Finding]:
        return [make_finding("VISUAL_UNVERIFIED", Status.UNVERIFIED, "기술적 검증 미실행: 시각 검사 provider 없음",
                             source="visual-ai", page=page_no)]


def parse_model_response(text: str, page_no: int, source: str = "visual-ai") -> list[Finding]:
    """모델 응답(JSON 배열)을 Finding 으로 변환한다. 깨진 응답은 UNVERIFIED."""
    raw = (text or "").strip()
    raw = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("findings", [])
        if not isinstance(data, list):
            raise ValueError("배열 아님")
    except (ValueError, TypeError):
        return [make_finding("VISUAL_RESPONSE_UNPARSEABLE", Status.UNVERIFIED,
                             "모델 응답을 해석하지 못함: 사용자 확인 필요", source=source, page=page_no)]
    if not data:
        return [make_finding("VISUAL_NO_ISSUE", Status.PASS, "자동 검사에서 추가 이상 미발견",
                             source=source, page=page_no)]
    out: list[Finding] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            status = Status(str(item.get("status", "REVIEW")).upper())
        except ValueError:
            status = Status.UNVERIFIED
        meta: dict[str, Any] = {}
        bbox = item.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                b = [min(1.0, max(0.0, float(v))) for v in bbox]
                if b[2] > b[0] and b[3] > b[1]:
                    meta["bbox"] = b
            except (TypeError, ValueError):
                pass
        out.append(make_finding(str(item.get("code") or "VISUAL_FINDING"), status,
                                str(item.get("message", "")), source=source, page=page_no, meta=meta))
    return out or [make_finding("VISUAL_RESPONSE_UNPARSEABLE", Status.UNVERIFIED,
                                "모델 응답 항목 없음: 사용자 확인 필요", source=source, page=page_no)]


Transport = Callable[[str, dict, dict], dict]


def _http_post(url: str, headers: dict, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 - 고정 https 엔드포인트
        return json.loads(resp.read().decode("utf-8"))


class _HttpProvider:
    external = True
    name = ""
    key_env = ""
    default_model = ""

    def __init__(self, model: str | None = None, *, api_key: str | None = None,
                 transport: Transport | None = None) -> None:
        self.model = model or os.environ.get(ENV_MODEL) or self.default_model
        self._api_key = api_key
        self._transport = transport or _http_post
        self.stats = _new_stats()

    def _key(self) -> str:
        key = self._api_key or os.environ.get(self.key_env, "")
        if not key:
            raise RuntimeError(f"API 키 환경변수 {self.key_env} 가 설정되지 않음")
        return key

    def _build(self, page_png: bytes, page_no: int, context: dict) -> tuple[str, dict, dict]:
        raise NotImplementedError

    def _parse(self, resp: dict) -> tuple[str, int, int]:
        raise NotImplementedError

    def inspect_page(self, page_png: bytes, page_no: int, context: dict) -> list[Finding]:
        url, headers, payload = self._build(page_png, page_no, context or {})
        resp = self._transport(url, headers, payload)
        text, tin, tout = self._parse(resp)
        self.stats["calls"] += 1
        self.stats["input_tokens"] += tin
        self.stats["output_tokens"] += tout
        return parse_model_response(text, page_no)


class OpenAIProvider(_HttpProvider):
    name = "openai"
    key_env = ENV_OPENAI_KEY
    default_model = DEFAULT_OPENAI_MODEL

    def _build(self, page_png, page_no, context):
        b64 = base64.b64encode(page_png).decode("ascii")
        payload = {"model": self.model, "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}]}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._key()}"}
        return "https://api.openai.com/v1/chat/completions", headers, payload

    def _parse(self, resp):
        text = resp["choices"][0]["message"]["content"]
        u = resp.get("usage") or {}
        return text, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))


class AnthropicProvider(_HttpProvider):
    name = "anthropic"
    key_env = ENV_ANTHROPIC_KEY
    default_model = DEFAULT_ANTHROPIC_MODEL

    def _build(self, page_png, page_no, context):
        b64 = base64.b64encode(page_png).decode("ascii")
        payload = {"model": self.model, "max_tokens": 2048, "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
            {"type": "text", "text": PROMPT},
        ]}]}
        headers = {"Content-Type": "application/json", "x-api-key": self._key(),
                   "anthropic-version": "2023-06-01"}
        return "https://api.anthropic.com/v1/messages", headers, payload

    def _parse(self, resp):
        text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        u = resp.get("usage") or {}
        return text, int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0))


def get_provider(name: str | None = None, model: str | None = None, config_path: str | Path | None = None):
    """설정 json({"provider","model"}) > 인자 > 환경변수 순으로 provider 를 만든다(기본 none)."""
    cfg: dict[str, Any] = {}
    if config_path and Path(config_path).is_file():
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    pname = (cfg.get("provider") or name or os.environ.get(ENV_PROVIDER) or "none").lower()
    pmodel = cfg.get("model") or model or os.environ.get(ENV_MODEL) or None
    if pname == "openai":
        return OpenAIProvider(pmodel)
    if pname == "anthropic":
        return AnthropicProvider(pmodel)
    return NoneProvider()


def load_manual_findings(json_path: str | Path) -> list[Finding]:
    """Claude Code 가 PNG 를 직접 보고 낸 판정 JSON([{page,code,status,message,bbox?}])을 source=manual-agent 로 적재."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("findings", [])
    out: list[Finding] = []
    for item in data:
        try:
            status = Status(str(item.get("status", "REVIEW")).upper())
        except ValueError:
            status = Status.UNVERIFIED
        meta: dict[str, Any] = {}
        if isinstance(item.get("bbox"), list) and len(item["bbox"]) == 4:
            meta["bbox"] = [float(v) for v in item["bbox"]]
        out.append(make_finding(str(item.get("code") or "VISUAL_MANUAL"), status, str(item.get("message", "")),
                                source="manual-agent", page=item.get("page"), meta=meta))
    return out


# ───────────────────────── 실행 ─────────────────────────

@dataclass
class VisualQAReport:
    findings: list[Finding] = field(default_factory=list)
    pages: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    provider_name: str = ""
    model: str = ""
    cache_hits: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"findings": [f.to_dict() for f in self.findings], "pages": self.pages, "usage": self.usage,
                "provider_name": self.provider_name, "model": self.model, "cache_hits": self.cache_hits}


def _cache_path(cache_dir: Path, png: bytes, provider: Any) -> Path:
    key = hashlib.sha256(png).hexdigest()
    tag = hashlib.sha256(f"{provider.name}|{provider.model}".encode()).hexdigest()[:12]
    return cache_dir / f"{key}_{tag}.json"


def _from_dict(d: dict, page_no: int) -> Finding:
    return Finding(code=d["code"], status=Status(d["status"]), message=d["message"], source=d.get("source", "visual-ai"),
                   page=page_no, evidence=d.get("evidence", ""), image="", meta=d.get("meta") or {})


def _crop(page: Any, bbox: list[float], dpi: int, out: Path) -> None:
    import fitz
    r = page.rect
    clip = fitz.Rect(r.x0 + bbox[0] * r.width, r.y0 + bbox[1] * r.height,
                     r.x0 + bbox[2] * r.width, r.y0 + bbox[3] * r.height)
    page.get_pixmap(dpi=dpi, clip=clip).save(str(out))


def run_visual_qa(pdf_path: str | Path, out_dir: str | Path, provider: Any, *, dpi: int = DEFAULT_DPI,
                  redaction_confirmed: bool = False, cache_dir: str | Path | None = None,
                  context: dict | None = None, manual_findings: list[Finding] | None = None,
                  confirmed_pages: Collection[int] | None = None) -> VisualQAReport:
    """confirmed_pages: 쪽 단위 확인 목록(1부터). 있으면 이 쪽만 외부 전송 대상이다(redaction_confirmed 는 전체 확인).

    합본 안에 가림 확인이 안 된 첨부가 섞여 있어도, 우리가 만든 신청서 쪽까지 막지 않게 하려는 것이다."""
    import fitz

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cdir = Path(cache_dir) if cache_dir else None
    if cdir:
        cdir.mkdir(parents=True, exist_ok=True)
    ctx = dict(context or {})
    report = VisualQAReport(provider_name=provider.name, model=provider.model)
    before = dict(provider.stats)
    with fitz.open(str(pdf_path)) as doc:
        report.pages = doc.page_count
        for idx, page in enumerate(doc):
            no = idx + 1
            png = page.get_pixmap(dpi=dpi).tobytes("png")
            confirmed = redaction_confirmed or (confirmed_pages is not None and no in confirmed_pages)
            findings = _inspect_one(page, png, no, provider, confirmed, cdir, ctx, report)
            for f in findings:
                bbox = f.meta.get("bbox")
                if bbox:
                    try:
                        safe = re.sub(r"[^A-Za-z0-9_]+", "_", f.code)
                        crop = out / f"p{no:03d}_{safe}_{len(report.findings)}.png"
                        _crop(page, bbox, dpi, crop)
                        f.image = str(crop)
                    except Exception as exc:  # 크롭 실패는 검수 전체를 막지 않는다
                        f.meta["crop_error"] = scrub(str(exc))
                report.findings.append(f)
    report.findings.extend(manual_findings or [])
    delta = {k: provider.stats.get(k, 0) - before.get(k, 0) for k in ("calls", "input_tokens", "output_tokens")}
    pin, pout = os.environ.get("AUTO_WRITE_VISUAL_QA_PRICE_IN"), os.environ.get("AUTO_WRITE_VISUAL_QA_PRICE_OUT")
    cost = None
    if pin and pout:  # 100만 토큰당 USD
        cost = round(delta["input_tokens"] * float(pin) / 1e6 + delta["output_tokens"] * float(pout) / 1e6, 6)
    report.usage = {**delta, "estimated_cost_usd": cost}
    return report


def _inspect_one(page, png, no, provider, redaction_confirmed, cdir, ctx, report) -> list[Finding]:
    if provider.external:
        if not redaction_confirmed:
            return [make_finding("VISUAL_EXTERNAL_BLOCKED", Status.REVIEW,
                                 "사용자 확인 필요: 개인정보 가림 확인 전 외부 전송 차단(이 쪽만)", source="visual-ai", page=no)]
        if _RRN_RE.search(page.get_text() or ""):
            return [make_finding("VISUAL_PII_BLOCKED", Status.REVIEW,
                                 "사용자 확인 필요: 주민번호 패턴이 보여 외부 전송 차단", source="visual-ai", page=no)]
    cpath = _cache_path(cdir, png, provider) if cdir else None
    if cpath and cpath.is_file():
        try:
            items = json.loads(cpath.read_text(encoding="utf-8"))
            hit = [_from_dict(d, no) for d in items]
            report.cache_hits += 1
            return hit
        except (ValueError, KeyError):
            pass
    try:
        findings = provider.inspect_page(png, no, ctx)
    except Exception as exc:
        return [make_finding("VISUAL_PROVIDER_ERROR", Status.UNVERIFIED,
                             "기술적 검증 미실행: provider 호출 오류", source="visual-ai", page=no,
                             evidence=scrub(f"{type(exc).__name__}: {exc}")[:300])]
    if cpath and all(f.code not in ("VISUAL_UNVERIFIED", "VISUAL_RESPONSE_UNPARSEABLE") for f in findings):
        cpath.write_text(json.dumps([f.to_dict() for f in findings], ensure_ascii=False), encoding="utf-8")
    return findings
