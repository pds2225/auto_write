"""run_document_quality_harness.py

문서 품질 개선 하네스 실행 래퍼(프로젝트 루트의 scripts/ 에서 실행 가능).
``app`` 디렉토리를 sys.path 에 추가한 뒤 본체 CLI(document_quality_orchestrator.main)를 호출한다.

사용 예 (PowerShell)
--------------------
  python D:\\auto_write\\scripts\\run_document_quality_harness.py "C:\\path\\사업계획서.docx"
  python D:\\auto_write\\scripts\\run_document_quality_harness.py in.docx --output out.docx --underline
"""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from document_quality_orchestrator import main  # app/document_quality_orchestrator.py

if __name__ == "__main__":
    sys.exit(main())
