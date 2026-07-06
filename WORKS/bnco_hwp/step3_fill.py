# -*- coding: utf-8 -*-
"""Step 3: 서식.hwpx 의 서식 1-1호(T2)·1-2호(T4) 셀을 시그니처 검증 후 교체 → 최종 hwpx.

서울AI허브 검증 방식: (표,행,열) 좌표 + 현재 텍스트 시그니처가 일치할 때만 교체.
불일치 셀은 건너뛰고 보고(오기입<빈칸). 1-3호~1-6호(주관기관·동의서)는 불가침.
"""
import copy
import os
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\auto_write\app")
from lxml import etree
from auto_write.services.hwpx_fill import _q, _direct, _cell_text, _inherit_charpr

IN_HWPX = Path(r"D:\auto_write\WORKS\bnco_hwp\서식.hwpx")
OUT_HWPX = Path(r"D:\auto_write\WORKS\비앤코_디자인개발_서식채움_초안.hwpx")
SECTION = "Contents/section0.xml"

# ---------------------------------------------------------------- 채울 내용
TASK_NAME = "한국인 족형 맞춤 발레 토슈즈 토컵·밑창 일체형(PP) 제품디자인 개발"

COMPANY_PROFILE = """[기업연혁]
- 2014.06 비앤코 인터내셔날 설립(인천 남동구, 화장품 제조·도소매·정보통신)
- 2015 여성기업 확인(중소벤처기업부)
- (설립연도 [확인필요]) 베트남 현지법인 BNCO VINA 설립(수입·통관·유통·판촉)
- 2019 「100만불 수출의 탑」 수상, 수출실적 약 151만 달러
- 2020 품목별 원산지 인증 수출자 지정(관세청), 수출실적 약 198만 달러
- 2021 수출실적 약 200만 달러
- 2024 화장품책임판매업 등록, 미국 FDA 등록
- 2025 공장등록 완료(인천 남동구 호구포로 194, 3층 322호)
[생산품목]
- 자사브랜드 ITER: PDRN 기반 기초 스킨케어 4종 세트(토너·에멀전·세럼·크림, HS 3304.99)
- OEM: YHL 기초·색조 화장품(슬리핑팩·크림·립틴트 등, HS 3304.99)
[주요거래처]
- 베트남 현지법인 BNCO VINA(수입·통관·유통), ㈜엔프라니(HOLIKA HOLIKA 베트남 총판 계약), YHL(OEM 공급)"""

# --- 사용자 최종 확정본(소제목 포함 존댓말 버전) 3종 — 그대로 사용 ---
PRODUCT_USE = """■ 제품 개요
발레 무용수용 포인트슈즈(토슈즈)의 핵심 구조부인 '토컵+밑창 일체형' 부품으로, 자사 브랜드 RUSALKA(상표등록 2025.08)의 핵심 부품입니다.
■ 기존 제품의 문제
기존 토슈즈는 100년 전 방식의 수작업(종이·천·접착제 적층)으로 수명이 2~3일에 불과하고, 서구형 발틀 기반이라 한국인 족형에 맞지 않아 족부 부상(82.6%)과 '길들이기' 관습을 유발해 왔습니다.
■ 핵심 특성
토컵(발가락 지지부)과 밑창(아웃솔)을 PP(폴리프로필렌)로 일체 성형하여 △내구성 향상 △균일한 품질 △구매 즉시 착용(Ready-to-Wear) △한국인 족형 데이터(3D 발 스캐닝 기반 디지털 라스트) 반영을 구현하며, 사출 성형 양산으로 가격 경쟁력과 품질 일관성을 확보합니다."""

NEED_SUPPORT = """■ 시장 현황과 문제
국내 토슈즈 시장은 연 약 151억 원 규모이나 수입 의존도가 58%이며, 수작업 제조로 인한 품질 편차와 짧은 수명(2~3일) 탓에 무용수는 월 50~60만 원의 교체 부담과 족부 부상 위험(82.6%)을 안고 있습니다.
■ 당사 준비 현황
5년간 자체 개발로 3차 시제품 340켤레 제작, 발레 전공생 10명 필드테스트를 완료했습니다.
■ 디자인 개발의 필요성
양산 전환의 관건인 '토컵+밑창 일체형(PP)' 제품디자인(구조 최적화·사출 대응 형상·시방서)은 전문 역량이 필요한 영역입니다. 30년 제품개발·제화 경험, 베트남 생산기반, 수출 실적(100만불 수출의 탑)을 보유한 당사가 인천대학교 산학협력단의 디자인 전문성과 결합하면 양산 가능한 완성 디자인 확보가 가능하여, 본 지원사업 지원이 절실합니다."""

UTIL_PLAN = """■ 활용계획
개발 산출물(최종 3D렌더링·시방서·디자인목업·디자인출원)은 즉시 양산 준비에 투입합니다.
① 국내: 수입 의존 58% 시장에 국산 대체재로 진입, 무용계 필드테스트 네트워크로 초기 판로 확보
② 해외: 베트남 현지법인 BNCO VINA·미국 FDA 등록 경험·연 200만 달러 수출실적 등 기존 인프라로 아시아·북미 확장
③ IP: 디자인출원으로 일체형 구조의 권리 확보
■ 기대효과
△무용수 족부 부상·교체 비용 부담 경감 △품질 균일화·수명 연장 △수입 대체 및 K-발레 용품 수출 산업화 △인천 지역 제조기업의 신규 사업 창출이 기대됩니다."""

TECH_STATUS = """- RUSALKA 상표: 출원 2024.02, 등록완료 2025.08
- 특허: 출원예정 [확인필요: 특허 출원 진행상황·출원번호]
- 개발 프로세스: 3D 발 스캐닝 → 디지털 라스트(K-Last, Size Korea 데이터 기반) 역설계(CAD) → 금형/3D프린팅 시제품 제작(대상: 맞춤 라스트·밑창·토컵)
- 시제품 이력: 3차 시제품 340켤레 제작, 발레 전공생 10명 필드테스트 완료
- (참고) 비앤코 기존 상표권 4건: 「비앤코」·「BNCO」·「비앤코 스킨」·「BNCO SKIN」(화장품, 등록) — 본 과제 대상과 별개"""

BRAND_OWN = """자체 Brand 판매 ( [확인필요]% )
Brand Name: ITER(기초화장품, 기존 라인) / RUSALKA(발레 토슈즈, 신규 개발 라인)
상표등록: RUSALKA 등록완료(출원 2024.02·등록 2025.08), 「비앤코」·「BNCO」·「비앤코 스킨」·「BNCO SKIN」 등록
[확인필요: 'ITER' 상표 자체의 출원·등록 여부]"""

BRAND_OEM = """OEM Brand 판매 ( [확인필요]% )
Brand Name: YHL 등"""

EXPORT_REGION = ("베트남(주력 — 현지법인 BNCO VINA 통한 수입·통관·유통·판촉), "
                 "미국(2024 FDA 등록, 진출 추진 중), 호주, EU, 일본")

HOST_ORG = """인천대학교 산학협력단
[확인필요: search.idsc.kr 주관기관(제품 분야) 등록 완료 여부·디자인 관련학과 개설 요건 충족 여부 — 사전 협의 필수]"""

# ---------------------------------------------------------------- 셀 스펙
# (표 idx, 행 idx, 열 idx, 현재 텍스트 시그니처(prefix, ""=빈칸이어야 함), 새 값)
SPEC = [
    # ===== 서식 제1-1호 (T2) 참여기업 영역 =====
    (2, 1, 1, "예) 하반기 일반기업", "하반기 일반기업"),
    (2, 1, 3, "예) 수출용 피부관리", TASK_NAME),
    (2, 5, 2, "", "비앤코 인터내셔날"),
    (2, 5, 4, "", "임수미"),
    (2, 6, 1, "2001. 01", "2014. 06"),
    (2, 6, 3, "000-00-00000", "121-25-28496"),
    (2, 6, 5, "000000-0000000", "해당없음(개인사업자)"),
    (2, 7, 1, "", "[확인필요]"),                      # 대표자 성별
    (2, 7, 3, "19600101", "[확인필요]"),              # 생년월일
    (2, 7, 5, "대표자 핸드폰", "[확인필요]"),          # 핸드폰
    (2, 8, 1, "※ 선정이후", "인천광역시 남동구 호구포로 189, 904호(고잔동, 남동테크노타워 지식산업센터)"),
    (2, 8, 3, "", "bnco-oem.com [확인필요: 대표 홈페이지 URL 확정]"),
    (2, 9, 2, "", "[확인필요]"),                      # 담당자 부서
    (2, 9, 4, "", "이사"),                            # 직위
    (2, 9, 6, "", "함승아"),                          # 성명
    (2, 10, 1, "", "[확인필요]"),                     # 전화
    (2, 10, 3, "", "[확인필요]"),                     # 핸드폰
    (2, 10, 5, "", "dvd1970@naver.com"),              # E-mail
    (2, 11, 2, "", "인천대학교 산학협력단"),           # 주관기관 기업명(확정값만)
    (2, 18, 0, "예) 24,750,000", "24,750,000\n[확인필요: 주관기관 협의 후 확정]"),
    (2, 18, 1, "예) 18,000,000", "18,000,000"),
    (2, 18, 2, "예) 4,500,000", "4,500,000"),
    (2, 18, 3, "예) 2,250,000", "2,250,000"),
    (2, 19, 8, "(총 00일)", "(총 90일 이내) [확인필요: 착수·종료일 협의]"),
    # ===== 서식 제1-2호 (T4) =====
    (4, 1, 1, "", TASK_NAME),
    (4, 1, 3, "예) 제품", "제품"),
    (4, 1, 4, "예) 신규제품", "신규제품"),
    (4, 2, 1, "", "비앤코 인터내셔날 (대표 임수미)"),
    (4, 2, 3, "", HOST_ORG),
    (4, 3, 1, "※ 간략히 기재", COMPANY_PROFILE),
    # 매출현황(총액/수출/내수 × 2023~2026) — [확인필요] 간결 표기
    (4, 5, 1, "원", "[확인필요]"),
    (4, 5, 2, "원", "약 16억 원 [확인필요]"),
    (4, 5, 3, "원", "[확인필요]"),
    (4, 5, 4, "원", "[확인필요]"),
    (4, 6, 1, "원", "[확인필요]"),
    (4, 6, 2, "원", "[확인필요]"),
    (4, 6, 3, "원", "[확인필요]"),
    (4, 6, 4, "원", "[확인필요]"),
    (4, 7, 1, "원", "[확인필요]"),
    (4, 7, 2, "원", "[확인필요]"),
    (4, 7, 3, "원", "[확인필요]"),
    (4, 7, 4, "원", "[확인필요]"),
    # 고용현황 2023~2026
    (4, 8, 2, "명", "[확인필요]"),
    (4, 8, 3, "명", "[확인필요]"),
    (4, 8, 4, "명", "[확인필요]"),
    (4, 8, 5, "명", "약 2명 [확인필요]"),
    (4, 9, 2, "디자이너 총 00명", "[확인필요: 사내 디자이너 보유 여부(예/아니오)·보유 시 인원]"),
    (4, 10, 1, "※ 간략히 기재", EXPORT_REGION),
    (4, 11, 1, "자체 Brand 판매", BRAND_OWN),
    (4, 11, 2, "OEM Brand 판매", BRAND_OEM),
    (4, 12, 1, "※ 용도 및 특성", PRODUCT_USE),        # 확정본 500자
    (4, 13, 1, "예) 특허기술명", TECH_STATUS),
    (4, 14, 1, "※ 간략히 기재", NEED_SUPPORT),        # 확정본 500자
    (4, 15, 1, "※ 간략히 기재", UTIL_PLAN),           # 확정본 500자
]

_id_counter = 1900000000


def _next_id() -> str:
    global _id_counter
    _id_counter += 1
    return str(_id_counter)


def _set_para_text(p, value: str, tc) -> None:
    """단락 p 의 텍스트를 value 로(첫 hp:t 기입, 나머지 hp:t 비움·잉여 run 무해)."""
    ts = [el for el in p.iter(_q("t"))]
    if ts:
        ts[0].text = value
        for extra in ts[1:]:
            extra.text = ""
        return
    runs = list(p.iter(_q("run")))
    if runs:
        run = runs[0]
    else:
        run = etree.SubElement(p, _q("run"))
        run.set("charPrIDRef", _inherit_charpr(tc))
    t = etree.SubElement(run, _q("t"))
    t.text = value


def set_cell_multiline(tc, text: str) -> bool:
    """셀 내용을 text 로 통째 교체. 줄바꿈은 단락 복제(첫 단락 서식 승계)로 유지."""
    lines = text.split("\n")
    paras = list(tc.iter(_q("p")))
    if not paras:
        return False
    first = paras[0]
    for p in paras[1:]:
        parent = p.getparent()
        if parent is not None:
            parent.remove(p)
    _set_para_text(first, lines[0], tc)
    prev = first
    for line in lines[1:]:
        clone = copy.deepcopy(first)
        if clone.get("id") is not None:
            clone.set("id", _next_id())
        _set_para_text(clone, line, tc)
        prev.addnext(clone)
        prev = clone
    return True


def main() -> int:
    with zipfile.ZipFile(IN_HWPX) as zin:
        infos = zin.infolist()
        data = {i.filename: zin.read(i.filename) for i in infos}

    root = etree.fromstring(data[SECTION])
    tables = list(root.iter(_q("tbl")))
    print(f"tables={len(tables)}")

    filled, skipped = [], []
    for (ti, ri, ci, sig, value) in SPEC:
        tag = f"T{ti} R{ri} C{ci}"
        try:
            rows = _direct(tables[ti], "tr")
            cells = _direct(rows[ri], "tc")
            tc = cells[ci]
        except IndexError:
            skipped.append((tag, "좌표 없음"))
            continue
        cur = _cell_text(tc)
        ok = (cur == "") if sig == "" else cur.startswith(sig)
        if not ok:
            skipped.append((tag, f"시그니처 불일치: 현재={cur[:40]!r} 기대prefix={sig!r}"))
            continue
        if set_cell_multiline(tc, value):
            filled.append((tag, value.split("\n")[0][:50]))
        else:
            skipped.append((tag, "단락 없음(기입 불가)"))

    print(f"\nfilled={len(filled)}")
    for tag, head in filled:
        print(f"  OK {tag}: {head}")
    print(f"skipped={len(skipped)}")
    for tag, why in skipped:
        print(f"  SKIP {tag}: {why}")

    if skipped:
        print("\n!! 시그니처 불일치 존재 — 저장은 진행하되 위 SKIP 목록 보고 필수")

    # 원 XML 선언(standalone 등) 보존해 재직렬화
    new_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    orig = data[SECTION]
    m = re.match(rb"^<\?xml[^>]*\?>", orig)
    if m:
        decl = m.group(0)
        body = etree.tostring(root)
        new_xml = decl + body
    data[SECTION] = new_xml

    # 원자적 재압축: mimetype 선두 STORED, 나머지 엔트리 속성·순서 보존
    OUT_HWPX.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_HWPX.with_name(f"{OUT_HWPX.stem}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            if "mimetype" in data:
                zi = zipfile.ZipInfo("mimetype")
                zi.compress_type = zipfile.ZIP_STORED
                zout.writestr(zi, data["mimetype"])
            for info in infos:
                name = info.filename
                if name == "mimetype":
                    continue
                zi = zipfile.ZipInfo(name, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zout.writestr(zi, data[name])
        os.replace(tmp, OUT_HWPX)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    print(f"\nsaved -> {OUT_HWPX} ({OUT_HWPX.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
