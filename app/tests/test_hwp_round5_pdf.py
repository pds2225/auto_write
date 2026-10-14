"""PDF 호출·시간제한·소유권 회귀. 실제 한글 저장 성공은 별도 검증한다."""
from pathlib import Path
import threading

import pytest

from core.docx.services import hwp_docx_convert as mod
from test_hwp_docx_convert import _FakeHwpCom


@pytest.mark.parametrize('result', ['success', 'refused', 'timeout'])
def test_pdf_export_confirms_before_save_and_preserves_other_processes(tmp_path, monkeypatch, result):
    source, output = tmp_path / 'source.hwpx', tmp_path / 'output.pdf'
    source.write_bytes(b'original source')
    pids, killed, events = {900}, [], []
    released = threading.Event()

    class Fake(_FakeHwpCom):
        def SetMessageBoxMode(self, mode):
            events.append(('message', mode))
            return 0

        def Open(self, *args):
            events.append(('open', args))
            return True

        def SaveAs(self, path, fmt, opts):
            events.append(('save', fmt, opts))
            pids.add(333)  # 저장 중 사용자가 별도로 연 창도 보호한다.
            assert ('message', 0x00000010) in events
            assert fmt == 'PDF' and opts == ''
            if result == 'timeout':
                assert released.wait(2)
                raise RuntimeError('owned COM server terminated')
            if result == 'refused':
                return False
            Path(path).write_bytes(b'%PDF-mock')
            return True

    def dispatch():
        pids.add(101)
        return Fake()

    def kill(owned):
        killed.append(set(owned))
        pids.difference_update(owned)
        released.set()

    monkeypatch.setattr(mod, '_hangul_image_pids', lambda: set(pids))
    monkeypatch.setattr(mod, '_hwp_object_pid', lambda hwp: 101)
    monkeypatch.setattr(mod, '_dispatch_hwp', dispatch)
    monkeypatch.setattr(mod, '_kill_owned_pids', kill)
    assert mod._com_stage_timeout('SaveAs[PDF]') == 120.0
    if result == 'timeout':
        original_timeout = mod._com_stage_timeout
        monkeypatch.setattr(mod, '_com_stage_timeout',
                            lambda stage: 0.05 if stage == 'SaveAs[PDF]' else original_timeout(stage))
        with pytest.raises(mod.HangulComTimeout, match=r'SaveAs\[PDF\]'):
            mod.export_pdf_via_com(source, output)
    elif result == 'refused':
        with pytest.raises(RuntimeError, match='저장 실패'):
            mod.export_pdf_via_com(source, output)
        assert not output.exists()
    else:
        mod.export_pdf_via_com(source, output)
        assert output.read_bytes() == b'%PDF-mock'
    assert events[0] == ('message', 0x00000010)
    assert set().union(*killed) == {101}
    assert pids == {900, 333}
    assert source.read_bytes() == b'original source'
