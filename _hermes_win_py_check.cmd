
@echo off
cd /d D:\auto_write\app
python -c "import sys; print(sys.executable); print(sys.version)"
python -c "import fastapi, uvicorn, jinja2, docx, openai, httpx, pydantic, PIL, pypdf, olefile; print('imports ok')"
python -c "from auto_write.main import app; print('app import ok', len(app.routes))"
