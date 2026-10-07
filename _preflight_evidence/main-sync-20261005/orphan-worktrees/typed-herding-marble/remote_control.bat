@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo ========================================
echo Auto Write 로컬 PC 리모트 컨트롤
echo ========================================
echo.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "DEST=%~1"
if "%DEST%"=="" set "DEST=%ROOT%"

if not exist "%DEST%\.git" (
  echo [ERROR] 먼저 GitHub에서 저장소를 받으세요.
  echo         git clone https://github.com/pds2225/auto_write.git D:\auto_write
  echo         또는 clone.bat
  pause
  exit /b 2
)

set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.11 "%ROOT%\app\local_pc_remote.py" --dest "%DEST%" --start
  if not errorlevel 1 goto :started
  py -3 "%ROOT%\app\local_pc_remote.py" --dest "%DEST%" --start
  if not errorlevel 1 goto :started
)

where python >nul 2>&1
if not errorlevel 1 (
  python "%ROOT%\app\local_pc_remote.py" --dest "%DEST%" --start
  if not errorlevel 1 goto :started
)

where agent >nul 2>&1
if not errorlevel 1 (
  echo [INFO] Cursor My Machines 워커를 시작합니다. 이 창을 닫지 마세요.
  cd /d "%DEST%"
  agent worker start --name auto-write-pc --worker-dir "%DEST%"
  goto :eof
)

where claude >nul 2>&1
if not errorlevel 1 (
  echo [INFO] Claude Code Remote Control을 시작합니다. 이 창을 닫지 마세요.
  cd /d "%DEST%"
  claude remote-control --name auto_write
  goto :eof
)

echo [ERROR] Cursor CLI(agent) 또는 Claude Code(claude)가 없습니다.
echo [Cursor] PowerShell에서:
echo          irm 'https://cursor.com/install?win32=true' ^| iex
echo          agent login
echo          그다음 이 파일을 다시 더블클릭하세요.
echo [Claude] Claude Code 설치 후 D:\auto_write 에서 claude remote-control
pause
exit /b 1

:started
echo.
echo [안내] 워커가 떠 있는 동안 PC를 끄지 마세요.
pause
exit /b 0
