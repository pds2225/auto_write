"""F7-B visual_qa 테스트: 합성 PDF + 모킹만 사용(실제 네트워크 호출 없음)."""
import json
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auto_write.services.submit_finish import visual_qa as vq  # noqa: E402
from auto_write.services.submit_finish.status import Status  # noqa: E402


def _pdf(tmp_path, texts=("page one", "page two")):
    p = tmp_path / "a.pdf"
    d = fitz.open()
    for t in texts:
        d.new_page().insert_text((72, 100), t)
    d.save(str(p))
    d.close()
    return p


class Fake:
    name, model = "fake", "m1"

    def __init__(self, fn=None, external=False):
        self.stats = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.external = external
        self.fn = fn

    def inspect_page(self, png, no, ctx):
        self.stats["calls"] += 1
        if self.fn:
            return self.fn(no)
        return [vq.make_finding("VISUAL_CUT", Status.REVIEW, "시각적 오류 의심", source="visual-ai",
                                page=no, meta={"bbox": [0.1, 0.1, 0.6, 0.3]})]


def _ok(n):
    return [vq.make_finding("OK", Status.PASS, "ok", source="visual-ai", page=n)]


def test_none_provider_all_unverified(tmp_path):
    r = vq.run_visual_qa(_pdf(tmp_path), tmp_path / "o", vq.NoneProvider())
    assert r.pages == 2 and len(r.findings) == 2
    assert all(f.status == Status.UNVERIFIED and f.code == "VISUAL_UNVERIFIED" for f in r.findings)


def test_crop_png_created(tmp_path):
    r = vq.run_visual_qa(_pdf(tmp_path), tmp_path / "o", Fake())
    f = r.findings[0]
    assert Path(f.image).is_file() and "p001" in f.image
    crop = fitz.Pixmap(f.image)
    full = fitz.open(str(tmp_path / "a.pdf"))[0].get_pixmap(dpi=110)
    assert crop.width < full.width and crop.height < full.height


def test_cache_hit_second_run(tmp_path):
    pdf, cache = _pdf(tmp_path), tmp_path / "c"
    p1 = Fake()
    vq.run_visual_qa(pdf, tmp_path / "o", p1, cache_dir=cache)
    assert p1.stats["calls"] == 2
    p2 = Fake()
    r = vq.run_visual_qa(pdf, tmp_path / "o", p2, cache_dir=cache)
    assert p2.stats["calls"] == 0 and r.cache_hits == 2 and r.usage["calls"] == 0
    assert r.findings[0].page == 1


def test_external_blocked_without_redaction(tmp_path):
    p = Fake(external=True)
    r = vq.run_visual_qa(_pdf(tmp_path), tmp_path / "o", p, redaction_confirmed=False)
    assert p.stats["calls"] == 0
    assert all(f.status == Status.REVIEW and "사용자 확인 필요" in f.message for f in r.findings)


def test_rrn_page_blocked(tmp_path):
    pdf = _pdf(tmp_path, ("hello", "id 900101-1234567"))
    p = Fake(fn=_ok, external=True)
    r = vq.run_visual_qa(pdf, tmp_path / "o", p, redaction_confirmed=True)
    assert p.stats["calls"] == 1
    assert r.findings[1].code == "VISUAL_PII_BLOCKED" and r.findings[1].status == Status.REVIEW
    assert "900101" not in json.dumps(r.to_dict(), ensure_ascii=False)


def test_provider_exception_preserved_and_continues(tmp_path):
    def boom(n):
        if n == 1:
            raise RuntimeError("fail sk-abcdefghijk123")
        return _ok(n)
    r = vq.run_visual_qa(_pdf(tmp_path), tmp_path / "o", Fake(fn=boom))
    assert r.findings[0].status == Status.UNVERIFIED and "RuntimeError" in r.findings[0].evidence
    assert "sk-abcdefghijk123" not in r.findings[0].evidence
    assert r.findings[1].status == Status.PASS


def test_forbidden_phrase_replaced():
    fs = vq.parse_model_response('```json\n[{"code":"X","status":"PASS","message":"제출 가능 하다"}]\n```', 1)
    assert "제출 가능" not in fs[0].message and "[금지표현 제거]" in fs[0].message
    assert vq.parse_model_response("not json", 2)[0].status == Status.UNVERIFIED


def test_report_json_serializable(tmp_path):
    r = vq.run_visual_qa(_pdf(tmp_path), tmp_path / "o", Fake())
    d = json.loads(json.dumps(r.to_dict(), ensure_ascii=False))
    assert d["pages"] == 2 and d["provider_name"] == "fake" and "usage" in d


def test_openai_anthropic_mocked_no_key_leak(tmp_path, monkeypatch):
    secret = "sk-SECRETVALUE123456"

    def tr(url, headers, payload):
        return {"choices": [{"message": {"content": '[{"code":"A","status":"FAIL","message":"잘림","bbox":[0,0,0.5,0.5]}]'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    op = vq.OpenAIProvider(api_key=secret, transport=tr)
    assert op.model == "gpt-6.1-sol"
    r = vq.run_visual_qa(_pdf(tmp_path, ("a",)), tmp_path / "o", op, redaction_confirmed=True)
    assert r.findings[0].status == Status.FAIL and r.usage["input_tokens"] == 10
    assert secret not in json.dumps(r.to_dict(), ensure_ascii=False)

    def tr2(url, headers, payload):
        assert headers["x-api-key"] == secret
        return {"content": [{"type": "text", "text": "[]"}], "usage": {"input_tokens": 3, "output_tokens": 1}}
    ap = vq.AnthropicProvider(api_key=secret, transport=tr2)
    r2 = vq.run_visual_qa(_pdf(tmp_path, ("a",)), tmp_path / "o2", ap, redaction_confirmed=True)
    assert r2.findings[0].code == "VISUAL_NO_ISSUE"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r3 = vq.run_visual_qa(_pdf(tmp_path, ("a",)), tmp_path / "o3", vq.OpenAIProvider(transport=tr),
                          redaction_confirmed=True)
    assert r3.findings[0].status == Status.UNVERIFIED and "OPENAI_API_KEY" in r3.findings[0].evidence


def test_manual_and_selection(tmp_path, monkeypatch):
    j = tmp_path / "m.json"
    j.write_text(json.dumps([{"page": 1, "code": "M", "status": "REVIEW", "message": "직인 중복 의심"}],
                            ensure_ascii=False), encoding="utf-8")
    m = vq.load_manual_findings(j)
    assert m[0].source == "manual-agent"
    r = vq.run_visual_qa(_pdf(tmp_path), tmp_path / "o", vq.NoneProvider(), manual_findings=m)
    assert {f.source for f in r.findings} == {"visual-ai", "manual-agent"}
    monkeypatch.setenv("AUTO_WRITE_VISUAL_QA_PROVIDER", "openai")
    monkeypatch.setenv("AUTO_WRITE_VISUAL_QA_MODEL", "x-model")
    p = vq.get_provider()
    assert p.name == "openai" and p.model == "x-model"
    monkeypatch.delenv("AUTO_WRITE_VISUAL_QA_PROVIDER")
    assert vq.get_provider().name == "none"
