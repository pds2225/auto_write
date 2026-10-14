"""F6 pdf_package 단위 테스트. 실제 한글 COM 은 호출하지 않는다(가짜 변환기)."""
import fitz
import pytest

from auto_write.services.submit_finish import pdf_package as pp
from auto_write.services.submit_finish.status import Status


def _pdf(path, pages):
    d = fitz.open()
    for i in range(pages):
        d.new_page().insert_text((72, 72), f"{path.stem}-{i + 1}")
    d.save(str(path))
    d.close()
    return path


def _hwpx(tmp_path):
    p = tmp_path / "s.hwpx"
    p.write_bytes(b"x")
    return p


def test_merge_order_pages_manifest(tmp_path):
    a, b, c = _pdf(tmp_path / "a.pdf", 2), _pdf(tmp_path / "b.pdf", 1), _pdf(tmp_path / "c.pdf", 3)
    r = pp.merge_pdfs([b, a, c], tmp_path / "m.pdf")
    assert r.ok and r.total_pages == 6
    assert [(m["name"], m["start_page"], m["end_page"]) for m in r.manifest] == [
        ("b.pdf", 1, 1), ("a.pdf", 2, 3), ("c.pdf", 4, 6)]
    doc = fitz.open(str(r.out))
    assert "b-1" in doc[0].get_text() and "a-1" in doc[1].get_text() and "c-3" in doc[5].get_text()
    doc.close()


def test_merge_missing_attachment_detected(tmp_path):
    a = _pdf(tmp_path / "a.pdf", 1)
    r = pp.merge_pdfs([a, tmp_path / "none.pdf"], tmp_path / "m.pdf")
    assert not r.ok and r.out is None and not (tmp_path / "m.pdf").exists()
    assert any(f.code == "F6-MISSING" and f.status == Status.FAIL for f in r.findings)


def test_merge_refuses_overwrite_and_versions(tmp_path):
    a = _pdf(tmp_path / "a.pdf", 1)
    out = tmp_path / "m.pdf"
    assert pp.merge_pdfs([a], out).ok
    with pytest.raises(ValueError):
        pp.merge_pdfs([a], out)
    r = pp.merge_pdfs([a], out, versioned=True)
    assert r.out.name == "m_v2.pdf"
    assert pp.merge_pdfs([a], out, overwrite=True).out == out


def test_submission_name():
    assert pp.build_submission_name("신청서", "(주)가나", "홍길동") == "(제출) 신청서_(주)가나_홍길동_합본.pdf"
    assert pp.build_submission_name("신:청/서?", "A*B", "홍<길>동") == "(제출) 신청서_AB_홍길동_합본.pdf"
    with pytest.raises(ValueError):
        pp.build_submission_name("신청서", "", "홍")


def test_convert_retry_then_success_keeps_first_reason(tmp_path):
    calls = []

    def conv(src, dst):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("Hangul COM timeout at open (30s)")
        _pdf(dst, 1)

    r = pp.convert_hwpx_to_pdf(_hwpx(tmp_path), tmp_path / "o.pdf", converter=conv,
                               retries=2, retry_wait=0)
    assert r.ok and r.attempts == 2 and r.real_com is False
    assert "timeout" in r.reasons[0]
    assert any(f.code == "F6-REAL-COM" and f.status == Status.UNVERIFIED for f in r.findings)


def test_convert_all_fail_preserves_timeout_reason(tmp_path):
    seq = iter([TimeoutError("Hangul COM timeout at open (30s)"), RuntimeError("refused SaveAs")])

    def conv(src, dst):
        raise next(seq)

    r = pp.convert_hwpx_to_pdf(_hwpx(tmp_path), tmp_path / "o.pdf", converter=conv,
                               retries=2, retry_wait=0)
    assert not r.ok and r.pdf is None and r.attempts == 2
    msg = next(f.message for f in r.findings if f.code == "F6-CONVERT")
    assert "timeout" in msg and "refused SaveAs" in msg


def test_convert_refuses_existing_output(tmp_path):
    out = _pdf(tmp_path / "o.pdf", 1)
    with pytest.raises(ValueError):
        pp.convert_hwpx_to_pdf(_hwpx(tmp_path), out, converter=lambda s, d: None)


def test_user_pid_preservation_flag(tmp_path, monkeypatch):
    snaps = iter([{100, 200}, {100}])  # 변환 후 사용자 PID 200 이 사라진 경우
    monkeypatch.setattr(pp, "_hwp_pids", lambda: next(snaps))

    def conv(src, dst):
        _pdf(dst, 1)

    conv.real_com = True
    r = pp.convert_hwpx_to_pdf(_hwpx(tmp_path), tmp_path / "o.pdf", converter=conv, retry_wait=0)
    assert r.real_com is True and r.user_pids_preserved is False
    assert any(f.code == "F6-USER-PID" and f.status == Status.FAIL for f in r.findings)


def test_package_end_to_end_mock(tmp_path):
    att = _pdf(tmp_path / "att.pdf", 2)
    conv, merged = pp.package(_hwpx(tmp_path), [att], tmp_path / "out", doc_name="신청서",
                              company="가나", rep="홍길동",
                              converter=lambda s, d: _pdf(d, 1), retry_wait=0)
    assert conv.ok and merged.ok and merged.total_pages == 3
    assert merged.out.name == "(제출) 신청서_가나_홍길동_합본.pdf"


def test_hwp_pid_snapshot_drops_processes_that_exit_while_settling(monkeypatch):
    """직전 실행이 남긴 한글이 막 종료되는 중이면 '사용자 프로세스가 사라짐'으로 오탐하지 않는다."""
    import core.docx.services.hwp_docx_convert as hc

    seq = iter([{100, 200}, {100}])
    monkeypatch.setattr(hc, "_hangul_image_pids", lambda: next(seq))
    monkeypatch.setattr(pp, "_PID_SETTLE_SECONDS", 0)
    assert pp._hwp_pids() == {100}
