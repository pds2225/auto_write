# -*- coding: utf-8 -*-
"""F1 직인 자동 삽입 · F2 체크박스 자동 선택 — 합성 HWPX(가짜 데이터)로 검증."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from lxml import etree
from PIL import Image

from auto_write.services.submit_finish.checkbox_select import find_checkbox_groups, select_checkboxes
from auto_write.services.submit_finish.seal_stamp import SealSpec, find_seal_slots, stamp_seals
from auto_write.services.submit_finish.status import Status, find_forbidden

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_HC = "http://www.hancom.co.kr/hwpml/2011/core"
_OPF = "http://www.idpf.org/2007/opf/"


# ── 합성 HWPX 빌더 ─────────────────────────────────────────────
def _p(*runs: str) -> str:
    body = "".join(f"<hp:run charPrIDRef=\"0\"><hp:t>{r}</hp:t></hp:run>" for r in runs)
    return f"<hp:p paraPrIDRef=\"0\">{body}</hp:p>"


def _tc(row: int, col: int, *paras: str) -> str:
    inner = "".join(paras) or _p("")
    return (f"<hp:tc><hp:subList>{inner}</hp:subList>"
            f"<hp:cellAddr colAddr=\"{col}\" rowAddr=\"{row}\"/>"
            f"<hp:cellSpan colSpan=\"1\" rowSpan=\"1\"/></hp:tc>")


def _tbl(rows: list[list[list[str]]]) -> str:
    trs = "".join(
        "<hp:tr>" + "".join(_tc(r, c, *cell) for c, cell in enumerate(row)) + "</hp:tr>"
        for r, row in enumerate(rows))
    return f"<hp:p paraPrIDRef=\"0\"><hp:run charPrIDRef=\"0\"><hp:tbl>{trs}</hp:tbl></hp:run></hp:p>"


def _write_hwpx(path: Path, body: str) -> None:
    section = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}" xmlns:hc="{_HC}">{body}</hs:sec>')
    header = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><hh:head xmlns:hh="{_HH}">'
              '<hh:refList><hh:charProperties itemCnt="1"><hh:charPr id="0" textColor="#000000"/>'
              '</hh:charProperties></hh:refList></hh:head>')
    hpf = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><opf:package xmlns:opf="{_OPF}">'
           '<opf:manifest><opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
           '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
           '</opf:manifest><opf:spine><opf:itemref idref="section0"/></opf:spine></opf:package>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header.encode("utf-8"))
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", hpf.encode("utf-8"))


def _section(path: Path):
    with zipfile.ZipFile(path) as archive:
        return etree.fromstring(archive.read("Contents/section0.xml"))


def _pics(path: Path) -> list:
    return list(_section(path).iter(f"{{{_HP}}}pic"))


def _all_text(path: Path) -> str:
    return "".join(t.text or "" for t in _section(path).iter(f"{{{_HP}}}t"))


# ── F1 ────────────────────────────────────────────────────────
@pytest.fixture()
def seal_doc(tmp_path: Path) -> tuple[Path, Path]:
    body = (
        _p("신청인 홍길동 (서명 또는 인)")                       # ① 본문 괄호표식(본인)
        + _p("신청 기업 정보")
        + _tbl([
            [[_p("대표자")], [_p("홍길동")], [_p("(인)")]],      # ② 표 칸 괄호표식(대표자)
            [[_p("성명")], [_p("홍길동")], [_p("서명")], []],    # ③ '서명' 라벨 옆 빈칸
        ])
        + _p("대표자 이영희 (직인)")                             # 다른 사람 칸
        + _p("참여인력 현황")
        + _tbl([
            [[_p("구분")], [_p("성명")], [_p("서명")]],
            [[_p("팀원")], [_p("김철수")], []],                  # 팀원 칸
            [[_p("팀원")], [_p("박영수")], []],
        ])
    )
    src = tmp_path / "seal.hwpx"
    _write_hwpx(src, body)
    img = tmp_path / "fake_seal.png"
    Image.new("RGBA", (300, 200), (200, 0, 0, 255)).save(img)   # 가짜 직인 3:2
    return src, img


def _spec(img: Path) -> SealSpec:
    return SealSpec(owner="홍길동", image=img, source="company_master", kind="seal", width_mm=15)


def test_find_and_stamp_three_owner_slots(seal_doc, tmp_path: Path) -> None:
    src, img = seal_doc
    before = src.read_bytes()
    slots = find_seal_slots(src)
    assert len(slots) == 6
    roles = sorted(s.role for s in slots)
    assert roles.count("member") == 2
    out = tmp_path / "out.hwpx"
    report = stamp_seals(src, out, [_spec(img)])
    assert report["inserted"] == 3                                # ① 3곳 삽입
    assert len(_pics(out)) == 3
    assert src.read_bytes() == before                             # 원본 미수정
    inserted = [f for f in report["findings"] if f.code == "F1_SEAL_INSERTED"]
    assert len(inserted) == 3
    for f in inserted:                                            # ⑩ 대상자·크기·출처 기록
        assert f.meta["target"] == "홍길동" and f.meta["source"] == "company_master"
        assert f.meta["size_mm"] == "15.0x10.0"
        assert not find_forbidden(f.message)


def test_wrong_owner_and_member_slots_not_stamped(seal_doc, tmp_path: Path) -> None:
    src, img = seal_doc
    out = tmp_path / "out.hwpx"
    report = stamp_seals(src, out, [_spec(img)])
    codes = [f.code for f in report["findings"]]
    assert codes.count("F1_SEAL_OWNER_UNKNOWN") == 1             # ② 이영희 칸 삽입 0
    assert codes.count("F1_SEAL_OTHER_PARTY") == 2               # ③ 팀원 칸 REVIEW
    review = [f for f in report["findings"] if f.status is Status.REVIEW]
    assert all(f.meta["inserted"] is False for f in review)
    # 삽입된 그림은 모두 홍길동 줄·행에만 있다
    root = _section(out)
    for pic in root.iter(f"{{{_HP}}}pic"):
        scope = pic.getparent().getparent()                       # 그림이 붙은 문단
        cur = scope
        while cur is not None and cur.tag != f"{{{_HP}}}tc":
            cur = cur.getparent()
        if cur is not None:
            scope = cur.getparent()                               # 표 칸이면 그 행 전체
        ctx = "".join(t.text or "" for t in scope.iter(f"{{{_HP}}}t"))
        assert "홍길동" in ctx
        assert "이영희" not in ctx and "김철수" not in ctx and "박영수" not in ctx


def test_rerun_is_idempotent(seal_doc, tmp_path: Path) -> None:
    src, img = seal_doc
    first = tmp_path / "first.hwpx"
    second = tmp_path / "second.hwpx"
    stamp_seals(src, first, [_spec(img)])
    report = stamp_seals(first, second, [_spec(img)])            # ④ 재실행
    assert report["inserted"] == 0
    assert len(_pics(second)) == 3
    assert [f.code for f in report["findings"]].count("F1_SEAL_PRESENT") == 3
    with zipfile.ZipFile(second) as archive:
        assert len([n for n in archive.namelist() if n.startswith("BinData/")]) == 1
    again = tmp_path / "again.hwpx"                               # 원본에서 다시 = 같은 결과
    assert stamp_seals(src, again, [_spec(img)])["inserted"] == 3


def test_aspect_ratio_and_floating_layout(seal_doc, tmp_path: Path) -> None:
    src, img = seal_doc
    out = tmp_path / "out.hwpx"
    stamp_seals(src, out, [_spec(img)])
    for pic in _pics(out):                                        # ⑤ 가로·세로 비율 보존
        sz = pic.find(f"{{{_HP}}}sz")
        w, h = int(sz.get("width")), int(sz.get("height"))
        assert w > 0 and h > 0
        assert abs(w / h - 300 / 200) < 0.01
        org = pic.find(f"{{{_HP}}}orgSz")
        assert abs(int(org.get("width")) / int(org.get("height")) - 1.5) < 0.01
        assert pic.get("textWrap") == "IN_FRONT_OF_TEXT"
        pos = pic.find(f"{{{_HP}}}pos")
        assert pos.get("treatAsChar") == "0"
        assert int(pos.get("vertOffset")) >= 0 and int(pos.get("horzOffset")) >= 0


def test_zip_integrity_and_manifest(seal_doc, tmp_path: Path) -> None:
    src, img = seal_doc
    out = tmp_path / "out.hwpx"
    stamp_seals(src, out, [_spec(img)])
    with zipfile.ZipFile(out) as archive:                         # ⑥ zip 무결성·manifest
        assert archive.testzip() is None
        first = archive.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        hpf = etree.fromstring(archive.read("Contents/content.hpf"))
        items = {i.get("id"): i.get("href") for i in hpf.iter(f"{{{_OPF}}}item")}
        image_items = {k: v for k, v in items.items() if v.startswith("BinData/")}
        assert len(image_items) == 1
        (image_id, href), = image_items.items()
        assert archive.read(href) == img.read_bytes()             # 원본 바이트 = 해상도 보존
    refs = {el.get("binaryItemIDRef") for el in _section(out).iter(f"{{{_HC}}}img")}
    assert refs == {image_id}
    ids = [p.get("id") for p in _pics(out)]
    assert len(set(ids)) == len(ids)


def test_same_path_and_missing_image_rejected(seal_doc, tmp_path: Path) -> None:
    src, img = seal_doc
    with pytest.raises(ValueError):
        stamp_seals(src, src, [_spec(img)])
    with pytest.raises(FileNotFoundError):
        stamp_seals(src, tmp_path / "x.hwpx", [SealSpec(owner="홍길동", image=tmp_path / "none.png")])


# ── F2 ────────────────────────────────────────────────────────
@pytest.fixture()
def box_doc(tmp_path: Path) -> Path:
    body = (
        _tbl([
            [[_p("사업자 구분")], [_p("□ 개인 □ 법인")]],
            [[_p("지원 분야")], [_p("□", "제조 ", "□", "서비스 ", "□", "기타")]],   # run 분리
            [[_p("기업 형태")], [_p("□ 중소기업 □ 중견기업")]],
            [[_p("여성기업 여부")], [_p("■ 예 □ 아니오")]],
            [[_p("벤처기업 인증 여부")], [_p("□ 예 □ 아니오")]],
        ])
        + _p("1. 개인정보 수집·이용 동의")
        + _p("□ 동의함 □ 동의하지 않음")
        + _p("2. 제3자 제공 동의")
        + _p("□ 동의함 □ 동의하지 않음")
    )
    src = tmp_path / "box.hwpx"
    _write_hwpx(src, body)
    return src


_DECISIONS = {
    "사업자 구분": {"value": "법인사업자", "source": "company_master", "single": True},
    "지원 분야": {"value": ["제조", "서비스"], "source": "plan", "single": False},
    "기업 형태": {"value": ["중소기업", "중견기업"], "source": "plan", "single": True},
    "여성기업 여부": {"value": "예", "source": "company_master", "single": True},
    "1. 개인정보 수집·이용 동의": {"value": "동의함", "source": "plan", "single": True},
}


def _group_text(path: Path) -> dict[str, str]:
    return {g.label: " ".join(("■" if o.checked else "□") + o.label for o in g.options)
            for g in find_checkbox_groups(path)}


def test_checkbox_groups_detected(box_doc: Path) -> None:
    groups = {g.label: g for g in find_checkbox_groups(box_doc)}
    assert [o.label for o in groups["지원 분야"].options] == ["제조", "서비스", "기타"]
    assert groups["1. 개인정보 수집·이용 동의"].consent is True
    assert groups["사업자 구분"].consent is False


def test_checkbox_selection_rules(box_doc: Path, tmp_path: Path) -> None:
    before = box_doc.read_bytes()
    out = tmp_path / "out.hwpx"
    report = select_checkboxes(box_doc, out, _DECISIONS, consents={"2. 제3자 제공 동의": True})
    state = _group_text(out)
    assert state["사업자 구분"] == "□개인 ■법인"                   # ⑩ 근거(동의어 정규화·정확일치)
    assert state["지원 분야"] == "■제조 ■서비스 □기타"            # ⑨ 분리 run 처리
    assert state["기업 형태"] == "□중소기업 □중견기업"            # ⑦ 단일선택 중복 → FAIL, 변경 0
    assert state["여성기업 여부"] == "■예 □아니오"                # 이미 ■ 유지
    assert state["벤처기업 인증 여부"] == "□예 □아니오"           # 근거 없음 → 그대로
    assert state["1. 개인정보 수집·이용 동의"].startswith("□동의함")   # ⑧ 미승인 동의 자동 체크 0
    assert state["2. 제3자 제공 동의"].startswith("■동의함")       # 해당 항목 승인만 인정
    assert box_doc.read_bytes() == before
    by_code: dict[str, list] = {}
    for f in report["findings"]:
        by_code.setdefault(f.code, []).append(f)
        assert not find_forbidden(f.message)
    assert by_code["F2_SINGLE_MULTI"][0].status is Status.FAIL
    assert len(by_code["F2_CONSENT_UNAPPROVED"]) == 1
    assert by_code["F2_NO_BASIS"][0].meta["label"] == "벤처기업 인증 여부"
    selected = {f.meta["label"]: f for f in by_code["F2_SELECTED"]}
    assert selected["사업자 구분"].meta["source"] == "company_master"
    assert selected["지원 분야"].meta["selected"] == ["서비스", "제조"]
    assert selected["2. 제3자 제공 동의"].meta["source"] == "user"
    # 분리 run 은 □ 글자만 바뀌고 옵션 run 은 그대로
    texts = [t.text for t in _section(out).iter(f"{{{_HP}}}t")]
    assert ["■", "제조 ", "■", "서비스 ", "□", "기타"] == texts[texts.index("제조 ") - 1: texts.index("제조 ") + 5]


def test_consent_not_inferred_from_other_item(box_doc: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.hwpx"
    select_checkboxes(box_doc, out, {}, consents={"1. 개인정보 수집·이용 동의": True})
    state = _group_text(out)
    assert state["1. 개인정보 수집·이용 동의"].startswith("■동의함")
    assert state["2. 제3자 제공 동의"].startswith("□동의함")       # 다른 항목 승인으로 추정 금지
    assert "■" not in state["사업자 구분"]


def test_partial_value_does_not_check(box_doc: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.hwpx"                                   # L025: 부분문자열 오체크 금지
    report = select_checkboxes(box_doc, out, {"사업자 구분": {"value": "개인정보보호", "source": "plan"}})
    assert _group_text(out)["사업자 구분"] == "□개인 □법인"
    assert any(f.code == "F2_OPTION_UNMATCHED" for f in report["findings"])


def test_checkbox_rerun_idempotent(box_doc: Path, tmp_path: Path) -> None:
    first, second = tmp_path / "a.hwpx", tmp_path / "b.hwpx"
    select_checkboxes(box_doc, first, _DECISIONS)
    report = select_checkboxes(first, second, _DECISIONS)
    assert report["selected"] == 0
    assert _group_text(first) == _group_text(second)
    with zipfile.ZipFile(second) as archive:
        assert archive.testzip() is None


def test_member_seal_only_when_user_approved(seal_doc, tmp_path: Path) -> None:
    """팀원 칸은 기본 REVIEW. 해당 소유자 도장을 사용자가 명시 승인한 경우에만 그 칸에 삽입."""
    src, img = seal_doc
    base = [SealSpec(owner="김철수", image=img, source="user", kind="seal", width_mm=15)]
    r0 = stamp_seals(src, tmp_path / "o0.hwpx", base)
    assert r0["inserted"] == 0                                    # 승인 없음 → 삽입 0
    assert "F1_SEAL_OTHER_PARTY" in [f.code for f in r0["findings"]]

    ok = [SealSpec(owner="김철수", image=img, source="user", kind="seal", width_mm=15, user_approved=True)]
    r1 = stamp_seals(src, tmp_path / "o1.hwpx", ok)
    assert r1["inserted"] == 1                                    # 김철수 칸만
    assert len(_pics(tmp_path / "o1.hwpx")) == 1
    f = [x for x in r1["findings"] if x.code == "F1_SEAL_INSERTED"][0]
    assert f.meta["target"] == "김철수" and f.meta["source"] == "user"
    # 박영수 칸은 여전히 REVIEW (다른 팀원 승인으로 추정 금지)
    assert "F1_SEAL_OTHER_PARTY" in [x.code for x in r1["findings"]]


# ── F1 슬롯 라벨 바인딩(동의서 하단: 한 표 칸 안에 대표+팀원1~4 서명 줄) ─────────
_GAP = " " * 19


@pytest.fixture()
def consent_doc(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    cell = [
        _p("본인은 팀원 및 신청자의 개인정보 수집·이용에 동의합니다."),
        _p("                 신청자(팀 대표) 성명  :" + _GAP + "(서명/인)"),
        *[_p(f"팀원{i}" + _GAP + "(서명/인)") for i in range(1, 5)],
    ]
    src = tmp_path / "consent.hwpx"
    _write_hwpx(src, _tbl([[cell]]))
    imgs: dict[str, Path] = {}
    for i, (who, size) in enumerate([("가대표", (300, 300)), ("나팀원", (400, 200)),
                                     ("다팀원", (200, 400)), ("라팀원", (300, 150))]):
        imgs[who] = tmp_path / f"seal_{i}.png"
        Image.new("RGBA", size, (200, 0, i * 40, 255)).save(imgs[who])
    return src, imgs


def _bind_specs(imgs: dict[str, Path], approved: bool = True) -> list[SealSpec]:
    labels = {"가대표": "신청자(팀 대표) 성명", "나팀원": "팀원1", "다팀원": "팀원2", "라팀원": "팀원3"}
    return [SealSpec(owner=who, image=imgs[who], source="user", width_mm=15,
                     user_approved=approved, slot_label=labels[who]) for who in labels]


def _para_texts(path: Path) -> list[str]:
    return ["".join(t.text or "" for t in p.iter(f"{{{_HP}}}t"))
            for p in _section(path).iter(f"{{{_HP}}}p") if "(서명/인)" in "".join(
                t.text or "" for t in p.iter(f"{{{_HP}}}t")) and p.find(f".//{{{_HP}}}tbl") is None]


def test_rep_line_role_and_labels(consent_doc) -> None:
    src, _ = consent_doc
    slots = find_seal_slots(src)
    assert [s.label for s in slots] == ["신청자(팀대표)성명", "팀원1", "팀원2", "팀원3", "팀원4"]
    assert [s.role for s in slots] == ["representative"] + ["member"] * 4   # ① 대표 줄 인식
    assert all("label" in s.to_dict() for s in slots)


def test_slot_label_binding_stamps_bound_lines_only(consent_doc, tmp_path: Path) -> None:
    src, imgs = consent_doc
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = stamp_seals(src, out, _bind_specs(imgs))
    assert report["inserted"] == 4                                         # ② 대표+팀원1~3
    assert src.read_bytes() == before
    ins = {f.meta["label"]: f for f in report["findings"] if f.code == "F1_SEAL_INSERTED"}
    assert {k: v.meta["target"] for k, v in ins.items()} == {
        "신청자(팀대표)성명": "가대표", "팀원1": "나팀원", "팀원2": "다팀원", "팀원3": "라팀원"}
    assert all(f.meta["binding"] == "slot_label" and f.meta["source"] == "user" for f in ins.values())
    review = [f for f in report["findings"] if f.status is Status.REVIEW]
    assert [f.meta["label"] for f in review] == ["팀원4"]                    # 팀원4 미삽입
    # 각 그림은 자기 줄(문단)에 붙고, 서로 다른 BinData 4개
    paras = {}
    for pic in _pics(out):
        p = pic.getparent().getparent()
        paras["".join(t.text or "" for t in p.iter(f"{{{_HP}}}t"))] = pic
    assert len(paras) == 4 and not any(k.startswith("팀원4") for k in paras)
    with zipfile.ZipFile(out) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if n.startswith("BinData/")]) == 4


def test_binding_ignored_without_approval(consent_doc, tmp_path: Path) -> None:
    src, imgs = consent_doc
    report = stamp_seals(src, tmp_path / "o.hwpx", _bind_specs(imgs, approved=False))
    assert report["inserted"] == 0                                         # ③ 승인 없음 → 무시
    assert all(f.status is Status.REVIEW for f in report["findings"])
    assert not any(f.meta.get("binding") for f in report["findings"])


def test_partial_label_does_not_bind(consent_doc, tmp_path: Path) -> None:
    src, imgs = consent_doc
    spec = SealSpec(owner="나팀원", image=imgs["나팀원"], source="user", user_approved=True, slot_label="팀원")
    report = stamp_seals(src, tmp_path / "o.hwpx", [spec])
    assert report["inserted"] == 0                                         # ④ 부분일치 금지
    assert len(_pics(tmp_path / "o.hwpx")) == 0


def test_two_specs_same_slot_review(consent_doc, tmp_path: Path) -> None:
    src, imgs = consent_doc
    specs = [SealSpec(owner="나팀원", image=imgs["나팀원"], user_approved=True, slot_label="팀원1"),
             SealSpec(owner="다팀원", image=imgs["다팀원"], user_approved=True, slot_label="팀원 1")]
    report = stamp_seals(src, tmp_path / "o.hwpx", specs)
    assert report["inserted"] == 0                                         # ⑤ 같은 줄 2개 → REVIEW
    conflict = [f for f in report["findings"] if f.code == "F1_SEAL_BINDING_CONFLICT"]
    assert len(conflict) == 1 and conflict[0].status is Status.REVIEW
    assert sorted(conflict[0].meta["candidates"]) == ["나팀원", "다팀원"]


def test_write_names_once_and_idempotent(consent_doc, tmp_path: Path) -> None:
    src, imgs = consent_doc
    first, second = tmp_path / "a.hwpx", tmp_path / "b.hwpx"
    r1 = stamp_seals(src, first, _bind_specs(imgs), write_names=True)
    texts = _para_texts(first)
    width = len("팀원1" + _GAP + "(서명/인)")
    assert texts[0].count("가대표") == 1 and texts[0].index("가대표") < texts[0].index("(서명/인)")
    assert texts[0].startswith("                 신청자(팀 대표) 성명  :")   # 라벨 보존
    for i, who in enumerate(["나팀원", "다팀원", "라팀원"], start=1):
        assert texts[i].startswith(f"팀원{i}  {who} ") and texts[i].endswith("(서명/인)")
        assert texts[i].count(who) == 1
        assert len(texts[i]) == width - 3                                  # 공백을 이름 폭만큼 줄임
    assert texts[4] == "팀원4" + _GAP + "(서명/인)"                          # 미바인딩 줄 그대로
    assert sum(1 for f in r1["findings"] if f.meta.get("name_written")) == 4
    r2 = stamp_seals(first, second, _bind_specs(imgs), write_names=True)   # ⑥ 재실행
    assert _para_texts(second) == texts                                    # 이름 중복 0
    assert r2["inserted"] == 0                                             # ⑦ 직인 중복 0
    assert [f.code for f in r2["findings"]].count("F1_SEAL_PRESENT") == 4
    assert len(_pics(second)) == 4
    assert all(f.meta.get("name_written") is False for f in r2["findings"] if f.code == "F1_SEAL_PRESENT")
    with zipfile.ZipFile(second) as archive:
        assert len([n for n in archive.namelist() if n.startswith("BinData/")]) == 4
    assert not list(_section(first).iter(f"{{{_HP}}}linesegarray"))


def test_write_names_off_by_default(consent_doc, tmp_path: Path) -> None:
    src, imgs = consent_doc
    out = tmp_path / "o.hwpx"
    stamp_seals(src, out, _bind_specs(imgs))
    assert _para_texts(out)[1] == "팀원1" + _GAP + "(서명/인)"


def test_bound_seal_aspect_ratio(consent_doc, tmp_path: Path) -> None:
    src, imgs = consent_doc
    out = tmp_path / "o.hwpx"
    stamp_seals(src, out, _bind_specs(imgs))
    ratios = sorted(round(int(p.find(f"{{{_HP}}}sz").get("width")) / int(p.find(f"{{{_HP}}}sz").get("height")), 2)
                    for p in _pics(out))
    assert ratios == [0.5, 1.0, 2.0, 2.0]                                  # ⑧ 가로·세로 비율 보존
    for pic in _pics(out):
        assert pic.get("textWrap") == "IN_FRONT_OF_TEXT"
        pos = pic.find(f"{{{_HP}}}pos")
        assert pos.get("treatAsChar") == "0"
        assert int(pos.get("vertOffset")) >= 0 and int(pos.get("horzOffset")) >= 0


# ── 실환경에서 발견: 표식이 <t> 안 <tab/> 의 tail 에 있는 실양식(마포 참가신청서) ──
def _tab_p(label: str, marker: str) -> str:
    return (f'<hp:p paraPrIDRef="0"><hp:run charPrIDRef="0">'
            f'<hp:t>{label}<hp:tab width="8000" leader="0" type="1"/>{marker}</hp:t></hp:run></hp:p>')


def test_marker_in_tab_tail_is_detected_and_stamped(tmp_path: Path) -> None:
    """'신청자(대표자)<tab/>(서명/인)' 처럼 표식이 tab 뒤 tail 글자면 이전엔 슬롯으로 잡히지 않았다."""
    src = tmp_path / "tab.hwpx"
    _write_hwpx(src, _tab_p("신청자(대표자)", "(서명/인)") + _p("끝"))
    img = tmp_path / "fake_seal.png"
    Image.new("RGBA", (300, 200), (200, 0, 0, 255)).save(img)
    slots = find_seal_slots(src)
    assert [s.role for s in slots] == ["representative"]
    out = tmp_path / "out.hwpx"
    spec = SealSpec(owner="홍길동", image=img, kind="seal", width_mm=15, aliases=("대표자", "신청자"))
    report = stamp_seals(src, out, [spec])
    assert report["inserted"] == 1 and len(_pics(out)) == 1
    # 같은 양식의 팀원 줄(라벨 사이에 tab)도 슬롯으로 잡히되 승인 없이는 자동 기입하지 않는다.
    team = tmp_path / "team.hwpx"
    _write_hwpx(team, _tab_p("팀원1", "(서명/인)"))
    only = find_seal_slots(team)
    assert [s.role for s in only] == ["member"]
    rep2 = stamp_seals(team, tmp_path / "team_out.hwpx", [spec])
    assert rep2["inserted"] == 0


def test_stacked_signature_lines_cap_seal_height_to_one_line(tmp_path: Path) -> None:
    """서명 줄이 연달아 있으면 그림 높이를 한 줄(≈7mm) 안으로 줄여 다음 줄 라벨을 덮지 않는다(실렌더 확인)."""
    src = tmp_path / "stack.hwpx"
    _write_hwpx(src, _tab_p("신청자(팀 대표) 성명 :", "(서명/인)") + _tab_p("팀원1", "(서명/인)") + _tab_p("팀원2", "(서명/인)"))
    img = tmp_path / "fake_seal.png"
    Image.new("RGBA", (300, 200), (200, 0, 0, 255)).save(img)
    spec = SealSpec(owner="홍길동", image=img, kind="seal", width_mm=18, aliases=("대표자", "팀 대표"))
    report = stamp_seals(src, tmp_path / "out.hwpx", [spec])
    inserted = [f for f in report["findings"] if f.code == "F1_SEAL_INSERTED"]
    assert len(inserted) == 1
    assert inserted[0].meta.get("cramped_cap") is True
    assert inserted[0].meta["height_mm"] <= 7.05
    # 단독 줄은 요청 크기 유지
    lone = tmp_path / "lone.hwpx"
    _write_hwpx(lone, _tab_p("신청자(대표자)", "(서명/인)") + _p("끝"))
    rep2 = stamp_seals(lone, tmp_path / "lone_out.hwpx", [spec])
    f2 = [f for f in rep2["findings"] if f.code == "F1_SEAL_INSERTED"][0]
    assert f2.meta["width_mm"] == 18.0 and not f2.meta.get("cramped_cap")
