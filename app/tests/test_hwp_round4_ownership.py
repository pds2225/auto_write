"""Windows COM 소유권/실패 정리를 Linux CI에서도 mock으로 실행한다."""
from pathlib import Path
import threading

import pytest

from auto_write.services import hwp_docx_convert as mod
from test_hwp_docx_convert import _FakeHwpCom


@pytest.mark.parametrize("error", [OSError, RuntimeError, AssertionError])
def test_round4_pid_query_returns_empty_for_any_subprocess_exception(monkeypatch, error):
    monkeypatch.setattr(mod.sys, "platform", "win32")
    def fail(*args, **kwargs):
        raise error("tasklist failed")
    monkeypatch.setattr(mod.subprocess, "Popen", fail)
    assert mod._query_hangul_tasklist() == ""
    assert mod._hangul_image_pids() == set()
    assert mod._hword_image_pids() == set()


def test_round4_pid_query_does_not_call_subprocess_run(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "win32")
    def forbid(*args, **kwargs):
        raise AssertionError("rhwp run seam was called")
    class Process:
        returncode = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def communicate(self, **kwargs): return '"Hwp.exe","123","Console","1","1 K"', ""
    monkeypatch.setattr(mod.subprocess, "run", forbid)
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: Process())
    assert mod._hangul_image_pids() == {123}


@pytest.mark.parametrize("mode", ["success", "open_error", "open_timeout", "save_timeout"])
@pytest.mark.parametrize("handle_available", [True, False])
def test_round4_docx_conversion_closes_only_owned_hwp_and_hword(tmp_path, monkeypatch, mode, handle_available):
    monkeypatch.setattr(mod.sys, "platform", "win32")
    hwp_pids, hword_pids = ({900} if handle_available else set()), {800}
    killed = []
    released = threading.Event()
    class Fake(_FakeHwpCom):
        def Open(self, *args):
            hword_pids.add(202)
            hword_pids.add(333)  # 변환 중 사용자가 별도로 연 Hword
            if mode == "open_error":
                raise RuntimeError("DOCX open failed")
            if mode == "open_timeout":
                assert released.wait(2)
                raise RuntimeError("COM server terminated")
            return True
        def SaveAs(self, *args):
            if mode == "save_timeout":
                assert released.wait(2)
                raise RuntimeError("COM server terminated")
            return super().SaveAs(*args)
    fake = Fake()
    def dispatch():
        hwp_pids.add(101)
        return fake
    def kill(pids):
        killed.append(set(pids))
        hwp_pids.difference_update(pids)
        hword_pids.difference_update(pids)
        released.set()
    monkeypatch.setattr(mod, "_hangul_image_pids", lambda: set(hwp_pids))
    monkeypatch.setattr(mod, "_hword_image_pids", lambda: set(hword_pids))
    monkeypatch.setattr(mod, "_hwp_object_pid", lambda hwp: 101 if handle_available else None)
    monkeypatch.setattr(mod, "_is_automation_hwp", lambda pid: pid == 101)
    monkeypatch.setattr(mod, "_process_parent_pid", lambda pid: {101: mod.os.getpid(), 202: 101, 333: 999}.get(pid))
    monkeypatch.setattr(mod, "_dispatch_hwp", dispatch)
    monkeypatch.setattr(mod, "_kill_owned_pids", kill)
    monkeypatch.setattr(mod, "_com_stage_timeout", lambda stage: 0.03)
    src = tmp_path / "source.docx"
    src.write_bytes(b"original")
    out = tmp_path / "out.hwp"
    if mode == "success":
        mod._convert_via_com(src, out, ("HWP",))
        assert out.read_bytes() == b"FAKE-HWP-BINARY"
    elif "timeout" in mode:
        with pytest.raises(mod.HangulComTimeout):
            mod._convert_via_com(src, out, ("HWP",))
    else:
        with pytest.raises(RuntimeError, match="DOCX open failed"):
            mod._convert_via_com(src, out, ("HWP",))
    assert set().union(*killed) == {101, 202}
    assert hwp_pids == ({900} if handle_available else set()) and hword_pids == {800, 333}
    assert src.read_bytes() == b"original"


def test_round4_dispatch_timeout_tracks_hwp_without_window_handle(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "win32")
    pids = {900}
    killed = []
    released = threading.Event()
    def dispatch():
        pids.add(101)
        assert released.wait(2)
        raise RuntimeError("COM terminated")
    def kill(owned):
        killed.append(set(owned))
        released.set()
    monkeypatch.setattr(mod, "_hangul_image_pids", lambda: set(pids))
    monkeypatch.setattr(mod, "_kill_owned_pids", kill)
    monkeypatch.setattr(mod, "_dispatch_hwp", dispatch)
    monkeypatch.setattr(mod, "_com_stage_timeout", lambda stage: 0.03)
    monkeypatch.setattr(mod, "_is_automation_hwp", lambda pid: pid == 101)
    monkeypatch.setattr(mod, "_process_parent_pid", lambda pid: mod.os.getpid() if pid == 101 else None)
    with pytest.raises(mod.HangulComTimeout, match="Dispatch"):
        mod._convert_via_com(tmp_path / "in.hwp", tmp_path / "out.hwpx", ("HWPX",))
    assert killed == [{101}]


@pytest.mark.parametrize("after", [{900, 333}, {900, 101, 333}])
def test_round4_fallback_does_not_claim_user_hwp_or_ambiguous_new_pids(monkeypatch, after):
    monkeypatch.setattr(mod, "_hangul_image_pids", lambda: after)
    monkeypatch.setattr(mod, "_is_automation_hwp", lambda pid: pid == 101)
    assert mod._fallback_owned_hwp_pids({900}) == set()


def test_round4_reused_hwp_is_not_cleared_or_quit(tmp_path, monkeypatch):
    hword = {800}
    killed = []
    class Existing(_FakeHwpCom):
        @property
        def XHwpWindows(self):
            raise AssertionError("user Hwp visibility must not be changed")
        def Open(self, *args):
            raise AssertionError("user Hwp must not open the input")
        def Clear(self, *args): raise AssertionError("user Hwp must stay open")
        def Quit(self): raise AssertionError("user Hwp must stay open")
    monkeypatch.setattr(mod, "_hangul_image_pids", lambda: {900})
    monkeypatch.setattr(mod, "_hword_image_pids", lambda: set(hword))
    monkeypatch.setattr(mod, "_hwp_object_pid", lambda hwp: 900)
    monkeypatch.setattr(mod, "_process_parent_pid", lambda pid: 900 if pid == 202 else None)
    monkeypatch.setattr(mod, "_dispatch_hwp", Existing)
    monkeypatch.setattr(mod, "_kill_owned_pids", lambda pids: killed.append(set(pids)))
    with pytest.raises(RuntimeError, match="기존 사용자"):
        mod._convert_via_com(tmp_path / "in.docx", tmp_path / "out.hwp", ("HWP",))
    assert killed == []
    assert hword == {800}


def test_round4_fallback_preserves_another_sessions_automation_hwp(monkeypatch):
    monkeypatch.setattr(mod, "_hangul_image_pids", lambda: {900, 333})
    monkeypatch.setattr(mod, "_is_automation_hwp", lambda pid: True)
    monkeypatch.setattr(mod, "_process_parent_pid", lambda pid: 999 if pid == 333 else None)
    assert mod._fallback_owned_hwp_pids({900}) == set()


@pytest.mark.parametrize("image", ["Hwp.exe", "Hword.exe"])
def test_round4_pid_query_failure_stops_before_dispatch(tmp_path, monkeypatch, image):
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(
        mod, "_query_hangul_tasklist",
        lambda name="Hwp.exe": "" if name == image else "INFO: No tasks match.",
    )
    def forbidden_dispatch():
        raise AssertionError("unknown baseline must not dispatch or change a user window")
    monkeypatch.setattr(mod, "_dispatch_hwp", forbidden_dispatch)
    with pytest.raises(RuntimeError, match="프로세스 조회"):
        mod._convert_via_com(tmp_path / "in.docx", tmp_path / "out.hwp", ("HWP",))


def test_round4_unknown_handle_does_not_open_another_sessions_hwp(tmp_path, monkeypatch):
    snapshots = iter(({900}, {900, 333}, {900, 333}))
    monkeypatch.setattr(mod, "_hangul_image_pids", lambda: next(snapshots))
    monkeypatch.setattr(mod, "_hwp_object_pid", lambda hwp: None)
    monkeypatch.setattr(mod, "_is_automation_hwp", lambda pid: True)
    monkeypatch.setattr(mod, "_process_parent_pid", lambda pid: None)
    class Other(_FakeHwpCom):
        def Open(self, *args):
            raise AssertionError("unowned Hwp must not open the input")
        def Clear(self, *args):
            raise AssertionError("unowned Hwp must not clear")
        def Quit(self):
            raise AssertionError("unowned Hwp must not quit")
    monkeypatch.setattr(mod, "_dispatch_hwp", Other)
    with pytest.raises(RuntimeError, match="소유권"):
        mod._convert_via_com(tmp_path / "in.hwp", tmp_path / "out.hwpx", ("HWPX",))


def test_round4_fallback_pid_does_not_prove_object_ownership_with_existing_hwp(tmp_path, monkeypatch):
    pids = {900}
    killed = []
    class Existing(_FakeHwpCom):
        def Open(self, *args):
            raise AssertionError("existing user object must not be used")
        def Clear(self, *args):
            raise AssertionError("existing user object must not be cleared")
        def Quit(self):
            raise AssertionError("existing user object must not be quit")
    def dispatch():
        pids.add(101)
        return Existing()
    monkeypatch.setattr(mod, "_hangul_image_pids", lambda: set(pids))
    monkeypatch.setattr(mod, "_hwp_object_pid", lambda hwp: None)
    monkeypatch.setattr(mod, "_dispatch_hwp", dispatch)
    monkeypatch.setattr(mod, "_is_automation_hwp", lambda pid: pid == 101)
    monkeypatch.setattr(mod, "_process_parent_pid", lambda pid: mod.os.getpid() if pid == 101 else None)
    monkeypatch.setattr(mod, "_kill_owned_pids", lambda owned: killed.append(set(owned)))
    with pytest.raises(RuntimeError, match="소유권"):
        mod._convert_via_com(tmp_path / "in.hwp", tmp_path / "out.hwpx", ("HWPX",))
    assert killed == [{101}] and pids == {900, 101}
