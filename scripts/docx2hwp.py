"""docx2hwp.py — DOCX 결과물을 한글(.hwp) 파일로 변환한다.

auto_write 파이프라인의 산출물은 python-docx 로 만든 .docx 다. 정부 사업계획서는
.hwp 로 제출하는 경우가 많아, 이 스크립트로 .docx -> .hwp 변환한다.

전제(이 PC 에 이미 충족):
  - 한글(HWP) 설치 (HWPFrame.HwpObject COM 등록)
  - 패키지 설치된 Python311 + pywin32(win32com)

주의:
  - **반드시 대화형(사용자가 직접 여는) PowerShell 에서 실행**한다.
    백그라운드/서비스 세션에서는 한글 GUI COM 서버가 안 떠서 실패한다
    (com_error: 작업을 수행할 수 없습니다).
  - 처음 실행 시 한글 '보안 승인' 대화상자가 뜰 수 있다 → '허용'을 누르면 된다
    (FilePathCheckerModule 보안 모듈이 등록돼 있으면 안 뜬다).

사용 (PowerShell):
  $py = "C:\\Users\\ekth3\\AppData\\Local\\Programs\\Python\\Python311\\python.exe"
  & $py D:\\auto_write\\scripts\\docx2hwp.py "<입력.docx>" ["<출력.hwp>"]
  # 출력 경로 생략 시 입력과 같은 폴더에 같은 이름 .hwp 로 저장.
"""
from __future__ import annotations

import os
import sys


def convert(docx_path: str, hwp_path: str | None = None) -> str:
    docx_path = os.path.abspath(docx_path)
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"입력 DOCX 가 없습니다: {docx_path}")
    if hwp_path is None:
        hwp_path = os.path.splitext(docx_path)[0] + ".hwp"
    hwp_path = os.path.abspath(hwp_path)
    if os.path.abspath(docx_path) == hwp_path:
        raise ValueError("입력과 출력 경로가 같습니다.")

    import win32com.client as win32

    hwp = win32.Dispatch("HWPFrame.HwpObject")
    try:
        # 보안 대화상자 억제(모듈 등록돼 있으면 성공, 없으면 무시하고 진행)
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        # 자동화 중 메시지박스 자동 처리(버전에 따라 무시될 수 있음)
        try:
            hwp.SetMessageBoxMode(0x00000020)
        except Exception:
            pass

        # 형식 자동 인식으로 열기(빈 문자열). 실패 시 DOCX 필터 명시 재시도.
        if not hwp.Open(docx_path, "", ""):
            if not hwp.Open(docx_path, "DOCX", ""):
                raise RuntimeError(f"한글에서 DOCX 열기 실패: {docx_path}")
        if not hwp.SaveAs(hwp_path, "HWP", ""):
            raise RuntimeError(f"HWP 저장 실패: {hwp_path}")
    finally:
        try:
            hwp.Clear(1)
        except Exception:
            pass
        try:
            hwp.Quit()
        except Exception:
            pass

    if not os.path.exists(hwp_path):
        raise RuntimeError("변환은 끝났으나 결과 파일이 없습니다(권한/경로 확인).")
    return hwp_path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("사용법: python docx2hwp.py <입력.docx> [<출력.hwp>]")
        return 2
    src = argv[0]
    dst = argv[1] if len(argv) > 1 else None
    try:
        out = convert(src, dst)
    except Exception as exc:  # noqa: BLE001 - CLI 최상위에서 사용자 메시지로 출력
        print(f"[실패] {type(exc).__name__}: {exc}")
        print("→ 대화형 PowerShell 에서 실행했는지, 한글 보안 승인을 눌렀는지 확인하세요.")
        return 1
    print(f"[완료] HWP 생성: {out} ({os.path.getsize(out):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
