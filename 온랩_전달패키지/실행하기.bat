@echo off
chcp 65001 >nul
echo ============================================
echo  2026 한난 온랩 사업계획서 생성기 (마켓게이트)
echo ============================================
pip install -r requirements_onlab.txt -q
python inject.py --template "templates\온랩_사업계획서_양식.docx" --content content_onlab.json --output "output\온랩_사업계획서_마켓게이트.docx"
echo.
echo 완료! output 폴더의 DOCX 파일을 열어 확인하세요.
echo 내용 수정 = content_onlab.json 문구 수정 후 이 파일을 다시 더블클릭.
pause
