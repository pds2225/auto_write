import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import win32com.client as w

paths = [
    Path(r"D:\auto_write\results\backup_profile_v4\프로필 양식_박다솜_v4.hwpx"),
    Path(r"D:\auto_write\results\프로필 양식_박다솜_v5.hwpx"),
]

hwp = w.Dispatch("HWPFrame.HwpObject")
try:
    hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
except Exception as e:
    print("reg", e)

# Discover Open signature via signatures/help if available
for name in ("Open", "OpenDocument"):
    try:
        attr = getattr(hwp, name)
        print(name, attr)
    except Exception as e:
        print(name, "missing", e)

for p in paths:
    ok = None
    err = None
    for call in (
        lambda: hwp.Open(str(p), "HWPX", "forceopen:true", "lock:false"),
        lambda: hwp.Open(str(p), "", "", ""),
        lambda: hwp.Open(str(p), "HWPX", "", ""),
        lambda: hwp.XHwpDocuments.Open(str(p)),
    ):
        try:
            ok = call()
            err = None
            print(p.name, "OPEN", ok)
            break
        except Exception as e:
            err = e
    if err is not None and ok is None:
        print(p.name, "FAIL", type(err).__name__, err)

try:
    hwp.Quit()
except Exception as e:
    print("quit", e)
