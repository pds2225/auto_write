"""test_pure_evidence_service.py — 근거검색 URL 순수 헬퍼 안전망.

EvidenceService 의 네트워크 무관 URL 헬퍼(_is_preferred_domain / _decode_base64_url /
_normalize_bing_link)를 직접 검증한다. httpx·AI 호출은 타지 않는다.
인스턴스는 __new__ 로 만들어 __init__(OpenAIService) 의존을 피한다(대상 헬퍼는
openai_service 를 사용하지 않는다). 야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

import base64

from auto_write.services.evidence_service import EvidenceService


def _svc() -> EvidenceService:
    return EvidenceService.__new__(EvidenceService)


class TestIsPreferredDomain:
    def test_go_kr(self):
        assert _svc()._is_preferred_domain("https://www.example.go.kr/page") is True

    def test_ac_kr(self):
        assert _svc()._is_preferred_domain("http://univ.ac.kr") is True

    def test_re_kr(self):
        assert _svc()._is_preferred_domain("https://kisti.re.kr/board") is True

    def test_or_kr(self):
        assert _svc()._is_preferred_domain("https://foo.or.kr") is True

    def test_commercial_is_not_preferred(self):
        assert _svc()._is_preferred_domain("https://naver.com") is False

    def test_empty_url(self):
        assert _svc()._is_preferred_domain("") is False

    def test_case_insensitive(self):
        assert _svc()._is_preferred_domain("https://WWW.EXAMPLE.GO.KR") is True


class TestDecodeBase64Url:
    def test_decodes_http_url(self):
        raw = "https://example.com"
        enc = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        assert _svc()._decode_base64_url(enc) == raw

    def test_non_http_payload_rejected(self):
        enc = base64.urlsafe_b64encode(b"hello").decode().rstrip("=")
        assert _svc()._decode_base64_url(enc) == ""

    def test_empty(self):
        assert _svc()._decode_base64_url("") == ""

    def test_invalid_base64_returns_empty(self):
        # 한 글자는 base64 데이터 문자 수 규칙 위반 → 예외 → "" 로 안전 폴백.
        assert _svc()._decode_base64_url("x") == ""


class TestNormalizeBingLink:
    def test_empty(self):
        assert _svc()._normalize_bing_link("") == ""

    def test_non_bing_passthrough(self):
        url = "https://naver.com/path?x=1"
        assert _svc()._normalize_bing_link(url) == url

    def test_bing_redirect_is_decoded(self):
        target = "https://real.go.kr/page"
        enc = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
        url = f"https://www.bing.com/ck/a?u=a1{enc}&more=1"
        assert _svc()._normalize_bing_link(url) == target

    def test_bing_without_u_param_returns_original(self):
        url = "https://www.bing.com/search?q=test"
        assert _svc()._normalize_bing_link(url) == url
