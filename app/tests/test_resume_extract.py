# -*- coding: utf-8 -*-
"""resume_extract 순수 파서/병합 회귀 테스트 (COM 불필요).

fixture 는 실제 소스 이력서(박다솜_금융관련_이력서 20250805.hwp)를
doc_text_extract 로 평문화한 결과를 축약한 것(2026-07-13 실측).
"""
from __future__ import annotations

from auto_write.services.resume_extract import (
    IDENTITY_KEYS,
    ProfileBuildResult,
    ResumeProfile,
    build_profile,
    merge_profiles,
    parse_profile_text,
    profile_to_json,
)

# 실측 평문(축약) — identity 2쌍 행·값 반복·5섹션·저서 포함.
REAL_TEXT = """\
이 력 서
박다솜, 『AHP를 활용한 벤처캐피탈리스트의 ICT기업 투자결정요인』, 한양대학교 석사학위논문(2025)
박다솜, 이정일, 『2023년 창업지원사업 안내』, e퍼플(2023)
성명(국문) | 박다솜 | 소 속 | 밸류업파트너스 | 이미지
성 별 | 여 | 직 위 | 대표 | 이미지
핸 드 폰 | 010-2930-6666 | 생년월일 | 1992.04.06 | 이미지
이 메 일 | pds2225@naver.com | pds2225@naver.com | pds2225@naver.com | 이미지
주소(사업장) | 서울 마포구 와우산로 105 | 서울 마포구 와우산로 105 | 서울 마포구 와우산로 105 | 이미지
주소(거주지) | 서울 마포구 어울마당로3길 11 | 서울 마포구 어울마당로3길 11 | 서울 마포구 어울마당로3길 11 | 이미지
컨설팅 분야 | 중소기업/창업기업 정책자금, 투자유치 | 중소기업/창업기업 정책자금, 투자유치 | 중소기업/창업기업 정책자금, 투자유치 | 이미지
학력 | 기간 | 학교명 | 전공학과 | 학위
학력 | 2022.03~2025.08 | 한양대학교 | 경영컨설팅학과 | 석사
경력 | 기간 | 직장명 | 직위 | 담당업무
경력 | 2022.11~현재 | 밸류업파트너스 | 대표 | 자문, 멘토링, 컨설팅
경력 | 2022.02~2022.11 | IPO브릿지 | 선임컨설턴트 | 사업계획서, IR자료 컨설팅
경력 | 2016.11~2020.02 | 웰컴저축은행 (본점, 부평지점) | 계장 | 기업금융(부동산/PF대출)
자격 | 발급일자 | 자격증명 | 발급번호 | 발급기관
자격 | 2020.01.01. | 경영지도사 | 12040 | 중소벤처기업부
자격 | 2016.08.05 | 사회조사분석사 | 16202053963O | 한국산업인력관리공단
수행기간 | 주최기관명 | 강의 주제 | 회차/시간 | 구분
2024.12.15 | 초이비즈니스그룹 | 정부지원사업 기초 | 1회 2시간 | 민간
2023.03.20 | 일리(ILLI) | 소상공인 정책자금 활용법 | 1회 1시간 | 민간
수행기간 | 프로젝트명 | 수행내용(주요 과제) | 발주처
2023.11~2023.12 | ESG 지속가능경영보고서 작성 | 중대 이슈, 사회(S) | 구리도시공사
2022.02~2022.10 | 그린바이오 벤처캠퍼스 제안서 작성 | 정량/정성 기대효과 | 강원도, 평창군
"""


def _profile():
    return parse_profile_text(REAL_TEXT, source="fixture.hwp")


def test_identity_two_pairs_and_repeat_dedup():
    """한 행에 라벨-값 2쌍 + 값 반복 칸을 정확히 파싱(반복은 무시)."""
    p = _profile()
    ident = p.identity
    assert ident["name"] == "박다솜"
    assert ident["org"] == "밸류업파트너스"      # 2쌍 행의 둘째 라벨-값
    assert ident["gender"] == "여"
    assert ident["position"] == "대표"
    assert ident["phone"] == "010-2930-6666"
    assert ident["birth"] == "1992.04.06"
    assert ident["email"] == "pds2225@naver.com"  # 반복 3칸 → 하나만
    assert ident["address_work"].startswith("서울 마포구 와우산로")
    assert ident["address_home"].startswith("서울 마포구 어울마당로")
    assert "정책자금" in ident["field"]


def test_education_and_career_columns():
    """학력/경력 데이터행 컬럼 매핑 정확(태그 셀 제거)."""
    p = _profile()
    assert len(p.education) == 1
    edu = p.education[0]
    assert edu.period == "2022.03~2025.08"
    assert edu.school == "한양대학교"
    assert edu.major == "경영컨설팅학과"
    assert edu.degree == "석사"

    assert len(p.career) == 3
    c0 = p.career[0]
    assert c0.period == "2022.11~현재"
    assert c0.company == "밸류업파트너스"
    assert c0.position == "대표"
    assert "멘토링" in c0.duty
    # 헤더행("경력|기간|직장명...")은 데이터로 잡히지 않음
    assert all(c.company != "직장명" for c in p.career)


def test_certs_and_lectures_and_projects():
    """자격/강의(날짜선두)/수행 리스트 파싱."""
    p = _profile()
    assert len(p.certs) == 2
    assert p.certs[0].name == "경영지도사"
    assert p.certs[0].number == "12040"
    assert p.certs[0].issuer == "중소벤처기업부"

    assert len(p.lectures) == 2
    assert p.lectures[0].date == "2024.12.15"
    assert p.lectures[0].org == "초이비즈니스그룹"
    assert p.lectures[0].kind == "민간"

    assert len(p.projects) == 2
    assert p.projects[0].period == "2023.11~2023.12"
    assert p.projects[0].client == "구리도시공사"


def test_publications_captured():
    """『...』 저서/논문 라인 추출(표 밖)."""
    p = _profile()
    assert len(p.publications) == 2
    assert any("석사학위논문" in x for x in p.publications)
    # 저서 라인이 identity/섹션으로 오분류되지 않음
    assert "name" in p.identity and p.identity["name"] == "박다솜"


def test_merge_latest_wins_and_needs_confirm():
    """상위 우선 채택 + 충돌 병기 + 리스트 dedup + 누락 needs_confirm."""
    top = parse_profile_text(
        "성명(국문) | 박다솜 | 소 속 | 밸류업파트너스 | 이미지\n"
        "경력 | 기간 | 직장명 | 직위 | 담당업무\n"
        "경력 | 2022.11~현재 | 밸류업파트너스 | 대표 | 자문\n",
        source="top.hwp")
    older = parse_profile_text(
        "성명(국문) | 박다솜 | 소 속 | 오토라이트 | 이미지\n"   # org 충돌
        "경력 | 기간 | 직장명 | 직위 | 담당업무\n"
        "경력 | 2022.11~현재 | 밸류업파트너스 | 대표 | 자문\n"   # 중복 → dedup
        "경력 | 2016.11~2020.02 | 웰컴저축은행 | 계장 | 기업금융\n",  # 신규
        source="older.hwp")
    merged, needs = merge_profiles([top, older])

    assert merged.identity["org"] == "밸류업파트너스"          # 상위 우선
    assert any("충돌" in n and "org" in n for n in needs)      # 충돌 병기
    assert len(merged.career) == 2                            # dedup + union
    # 누락 필드(email 등)는 None + needs_confirm
    assert merged.identity.get("email") is None
    assert any("[미확인]" in n and "email" in n for n in needs)


def test_json_schema_all_identity_keys_and_no_fabrication():
    """profile.json 에 IDENTITY_KEYS 전부 존재(없으면 null=날조0)."""
    p = parse_profile_text("성명(국문) | 박다솜 | 이미지\n", source="min.hwp")
    merged, needs = merge_profiles([p])
    result = ProfileBuildResult(profile=merged, needs_confirm=needs,
                                merged_sources=["min.hwp"])
    d = result.as_dict()
    for k in IDENTITY_KEYS:
        assert k in d["identity"]           # 키는 항상 존재
    assert d["identity"]["name"] == "박다솜"
    assert d["identity"]["email"] is None   # 없는 값은 null(지어내지 않음)
    # JSON 직렬화 가능(한글 보존)
    js = profile_to_json(result)
    assert "박다솜" in js and "needs_confirm" in js


# --- 적대 리뷰(2026-07-13) 확정 결함 회귀 --------------------------------------
def test_no_fabrication_from_footer_after_section():
    """[HIGH] 섹션 활성 중 서명/푸터·identity 행을 가짜 섹션 데이터로 날조하지 않고,
    identity 는 정상 파싱된다(섹션 뒤 데이터 유실·날조 0)."""
    text = (
        "자격 | 발급일자 | 자격증명 | 발급번호 | 발급기관\n"
        "자격 | 2020.01.01. | 경영지도사 | 12040 | 중소벤처기업부\n"
        "작성일자 | 2025.08.05\n"                          # 푸터 → 가짜 자격 금지
        "성명(국문) | 박다솜 | 소 속 | 밸류업파트너스 | 이미지\n"  # identity 유실 금지
    )
    p = parse_profile_text(text, source="x.hwp")
    assert len(p.certs) == 1                    # '작성일자' 행이 자격으로 날조 안 됨
    assert all(c.name != "2025.08.05" for c in p.certs)
    assert p.identity.get("name") == "박다솜"    # 섹션 뒤 identity 파싱됨
    assert p.identity.get("org") == "밸류업파트너스"


def test_education_dedup_keeps_distinct_periods():
    """[MED] 학과/학위 공란인 서로 다른 학력(기간 상이)이 dedup 로 유실되지 않음."""
    text = (
        "학력 | 기간 | 학교명 | 전공학과 | 학위\n"
        "학력 | 2010.03~2014.02 | 한양대학교 |  | \n"
        "학력 | 2016.03~2018.02 | 한양대학교 |  | \n"
    )
    p = parse_profile_text(text)
    assert len(p.education) == 2
    merged, _ = merge_profiles([p])
    assert len(merged.education) == 2           # period 포함 키 → 유실 0


def test_cert_dedup_keeps_distinct_when_no_number():
    """[LOW] 발급번호 공란인 동일 명칭 자격(발급일/기관 상이)이 유실되지 않음."""
    text = (
        "자격 | 발급일자 | 자격증명 | 발급번호 | 발급기관\n"
        "자격 | 2020.01.01 | 경영지도사 |  | 한국산업인력공단\n"
        "자격 | 2023.05.05 | 경영지도사 |  | 한국생산성본부\n"
    )
    p = parse_profile_text(text)
    merged, _ = merge_profiles([p])
    assert len(merged.certs) == 2               # date/issuer 로 구분 → 유실 0


def test_data_row_with_header_words_not_misclassified():
    """[LOW] 데이터행 내용에 '학교명·학위' 등 헤더 단어가 섞여도 헤더로 오인 안 함."""
    text = (
        "수행기간 | 프로젝트명 | 수행내용(주요 과제) | 발주처\n"
        "2023.01 | 학교명 관리 시스템 구축 | 학위 검증 모듈 | 발주처X\n"
        "2024.05 | 일반 프로젝트 | 내용 | 발주처Y\n"
    )
    p = parse_profile_text(text)
    assert len(p.projects) == 2                 # 날짜선두 → 헤더 오인/유실 없음
    assert len(p.education) == 0


def test_folder_scan_includes_txt(tmp_path):
    """[MED] 폴더 스캔이 pdf/txt(extract_text 지원)도 포함(양식 화이트리스트 상속 갭 해소)."""
    f = tmp_path / "이력서_test.txt"
    f.write_text("성명(국문) | 박다솜 | 이미지\n", encoding="utf-8")
    result = build_profile([tmp_path])
    assert result.merged_sources                # txt 가 폴더 스캔에 포함됨
    assert result.profile.identity.get("name") == "박다솜"


def test_education_consolidates_graduated_over_completed():
    """같은 석사 과정의 '석사'(졸업)와 '석사 수료'는 최종(졸업)만 남고, 학사(다른 레벨)는 보존."""
    top = parse_profile_text(
        "학력 | 기간 | 학교명 | 전공학과 | 학위\n"
        "학력 | 2022.03~2025.08 | 한양대학교 | 경영컨설팅학과 | 석사\n"
        "학력 | 2010.03~2014.02 | 강남대학교 | 세무학과 | 학사\n",
        source="top.hwp")
    older = parse_profile_text(
        "학력 | 기간 | 학교명 | 전공학과 | 학위\n"
        "학력 | 2022.03~2024.02 | 한양대학교 | 경영컨설팅학과 | 석사 수료\n",
        source="older.hwp")
    merged, needs = merge_profiles([top, older])
    pairs = [(e.school, e.degree) for e in merged.education]
    assert ("한양대학교", "석사") in pairs          # 졸업(최종)만 채택
    assert all("수료" not in (e.degree or "") for e in merged.education)
    assert ("강남대학교", "학사") in pairs          # 다른 레벨은 보존(과잉병합 금지)
    assert len(merged.education) == 2
    assert any("[대체]" in n and "수료" in n for n in needs)   # 대체 내역 병기
