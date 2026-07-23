#!/usr/bin/env python3
"""온랩 참가신청서 HWPX 채움 — 셀 좌표 지정 최소수정(hp:t 텍스트만, 구조 무변경).

예시값이 든 양식이라 라벨 매칭 대신 (표, 행, 셀) 좌표로 정확히 기입한다.
모르는 인적사항(휴대전화·이메일·주소)은 예시값 제거 후 공란.
붙임2(상금·지원금)는 공란 유지(재도전패키지 수령 여부 확인 전).
"""
import shutil
import zipfile
from lxml import etree

SRC = r"D:\auto_write\온랩\작업\신청서_원본변환.hwpx"
DST = r"D:\auto_write\온랩\온랩_전달패키지\output\참가신청서_작성본_v1.hwpx"

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}

# (표idx, 행idx, 셀idx) → 새 텍스트 ('' = 예시값 제거)
FILLS = {
    # 표1: 참가신청서
    (1, 0, 2): "마켓게이트",
    (1, 1, 1): "박다솜",
    (1, 1, 3): "1명 (대표자 포함)",
    (1, 2, 1): "",                      # 휴대전화 — 본인 기입
    (1, 2, 3): "",                      # E-mail — 본인 기입
    (1, 3, 1): "창업 준비",
    (1, 3, 3): "여",
    (1, 4, 1): "",                      # 주소 — 본인 기입
    (1, 5, 1): "개인",
    (1, 6, 2): "",                      # 팀원 성명 (1인 팀 — 공란)
    (1, 7, 1): "",                      # 팀원 휴대전화
    (1, 7, 3): "",                      # 팀원 E-mail
    (1, 8, 1): "미래기술(AX)",
    (1, 10, 1): "AI·데이터 기반 수출지원 One-Stop 플랫폼 '마켓게이트'",
    (1, 11, 1): "AI가 수출국가 추천부터 바이어 매칭·계약까지 돕는 중소기업 수출 One-Stop 플랫폼",
    (1, 13, 2): "2026년 7월 24일",
    (1, 14, 2): "박다솜",
    # 표14·15: 붙임3 동의서 명단 (서명은 자필)
    (14, 2, 1): "박다솜",
    (14, 2, 2): "1992.04.06.",
    (14, 2, 3): "여",
    (15, 1, 1): "박다솜",
    (15, 1, 2): "1992.04.06.",
    (15, 1, 3): "여",
    # 표18: 붙임4 서약서
    (18, 0, 2): "2026년 7월 24일",
    (18, 1, 2): "마켓게이트",
    (18, 2, 2): "박다솜",
}


def set_cell_text(cell, value):
    """셀의 첫 hp:t 에 값을 넣고 나머지 hp:t 는 비운다. hp:t 가 없으면 첫 run 에 생성."""
    ts = cell.findall(".//hp:t", NS)
    if ts:
        ts[0].text = value
        for t in ts[1:]:
            t.text = ""
        return True
    runs = cell.findall(".//hp:run", NS)
    if runs and value:
        t = etree.SubElement(runs[0], f"{{{NS['hp']}}}t")
        t.text = value
        return True
    return value == ""  # 빈 값 지정인데 t 도 없으면 이미 공란


def main():
    shutil.copyfile(SRC, DST)
    with zipfile.ZipFile(SRC) as z:
        names = z.namelist()
        payload = {n: z.read(n) for n in names}

    root = etree.fromstring(payload["Contents/section0.xml"])
    tables = root.findall(".//hp:tbl", NS)

    done, miss = [], []
    for (ti, ri, ci), value in FILLS.items():
        try:
            rows = tables[ti].findall(".//hp:tr", NS)
            cells = rows[ri].findall("hp:tc", NS)
            ok = set_cell_text(cells[ci], value)
            (done if ok else miss).append((ti, ri, ci, value[:20]))
        except IndexError:
            miss.append((ti, ri, ci, value[:20]))

    payload["Contents/section0.xml"] = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True)

    with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            if n == "mimetype":
                zout.writestr(n, payload[n], compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(n, payload[n])

    print(f"기입 {len(done)}건 / 실패 {len(miss)}건")
    for m in miss:
        print("  실패:", m)
    return 0 if not miss else 2


if __name__ == "__main__":
    raise SystemExit(main())
