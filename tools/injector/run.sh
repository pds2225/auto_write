#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo "[BizPlan Injector — tools/injector]"
pip install -r requirements.txt -q
mkdir -p output
python inject.py --template templates/사업계획서_원본양식.docx --content examples/content_marketgate.json --output output/사업계획서_완성.docx
echo "완료! tools/injector/output 폴더를 확인하세요."
