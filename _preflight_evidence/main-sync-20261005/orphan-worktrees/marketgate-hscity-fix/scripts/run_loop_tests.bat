@echo off
setlocal EnableExtensions
set "APP_DIR=%~dp0app"
cd /d "%APP_DIR%"
set "PYTHONPATH=%APP_DIR%"
set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not exist "%PY%" set "PY=python"
echo [INFO] Running loop tests...
"%PY%" -m pytest tests\test_psst_mapping.py tests\test_loop4_sample_generate.py -q --tb=short
set "EC=%ERRORLEVEL%"
echo [INFO] EXIT_CODE=%EC%
exit /b %EC%
