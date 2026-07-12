"""test_cross_form_synonyms.py — 동의어 클러스터 확장/신설 회귀 (2026-07-01).

실측(박다솜 참가신청서 → 서울AI허브 신청서)에서 놓쳤던 매칭을 고정하고,
신설 5클러스터(담당자명·지원분야·제품서비스명·매출액·사업비)와 분리 규칙,
그리고 클러스터 간 _key 충돌 부재(조용한 덮어쓰기 방지)를 검증한다.
"""

from __future__ import annotations

from auto_write.services.cross_form_autofill import SYNONYMS, _cluster_rep, _key


def _same(a: str, b: str) -> bool:
    ra, rb = _cluster_rep(_key(a)), _cluster_rep(_key(b))
    return ra is not None and ra == rb


def test_name_cluster_recall():
    # 실측 회귀: 신청자명↔성명↔신청인 = 같은(대표자) 클러스터
    assert _same("신청자명", "성명")
    assert _same("신청인", "성명")
    assert _same("대표자이름", "대표자")


def test_address_cluster_recall():
    # 실측 회귀: 자택주소↔주소지
    assert _same("자택주소", "주소지")
    assert _same("본점소재지", "주소")
    assert _same("사업장소재지", "주소")


def test_new_clusters():
    assert _same("실무담당자", "담당자")
    assert _same("신청분야", "지원분야")
    assert _same("서비스명", "제품명")
    assert _same("연매출", "매출액")
    assert _same("총사업비", "사업비")


def test_cluster_separation():
    # 대표자 ≠ 담당자(사용자 강조: 실무자 칸에 대표명 오기입 방지)
    assert not _same("대표자", "담당자")
    # 사업명 ≠ 제품명(사업명과 실제 제품명이 다른 경우)
    assert not _same("사업명", "제품명")
    # 지원분야 ≠ 업종
    assert not _same("지원분야", "업종")


def test_empty_paren_placeholder():
    from auto_write.services.cross_form_autofill import _is_obvious_placeholder
    # 빈 괄호 예시는 채울 빈칸으로 인정
    assert _is_obvious_placeholder("( - )")
    assert _is_obvious_placeholder("( )")
    assert _is_obvious_placeholder("()")
    # 글자·숫자가 든 괄호는 실값 → 보존
    assert not _is_obvious_placeholder("(주)")
    assert not _is_obvious_placeholder("(041-123-4567)")
    assert not _is_obvious_placeholder("서울 마포구")


def test_no_key_collision():
    """같은 _key 가 서로 다른 클러스터에 있으면 _CLUSTER_OF 에서 조용히 덮인다 — 금지."""
    seen: dict[str, str] = {}
    for cl in SYNONYMS:
        rep = _key(cl[0])
        for alias in cl:
            k = _key(alias)
            assert k not in seen or seen[k] == rep, (
                f"클러스터 충돌: '{alias}'(_key={k}) 가 [{seen.get(k)}]와 [{rep}] 양쪽에")
            seen[k] = rep
