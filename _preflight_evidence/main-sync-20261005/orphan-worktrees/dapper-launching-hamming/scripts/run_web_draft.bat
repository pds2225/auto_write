@echo off
:: web_draft 실행 — 공고문+양식 → 사업계획서 초안(MD) 웹 UI
cd /d "%~dp0app"
echo Starting web_draft on http://localhost:8501 ...
streamlit run web_draft.py --server.port 8501
