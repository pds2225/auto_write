@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo ========================================
echo Auto Write GitHub clone
echo ========================================
echo.

set "DEST=%~1"
if "%DEST%"=="" set "DEST=D:\auto_write"
set "URL=https://github.com/pds2225/auto_write.git"

where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git이 설치되어 있지 않습니다.
  echo [안내] https://git-scm.com/download/win 에서 Git을 설치한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

if exist "%DEST%\.git" (
  echo [INFO] 이미 받은 저장소입니다: %DEST%
  echo [안내] 기존 폴더를 덮어쓰지 않았습니다.
  git -C "%DEST%" remote get-url origin
  git -C "%DEST%" rev-parse --abbrev-ref HEAD
  git -C "%DEST%" rev-parse --short HEAD
  git -C "%DEST%" status -sb
  echo.
  echo [다음] setup.bat 를 더블클릭하세요.
  pause
  exit /b 0
)

if exist "%DEST%" (
  echo [ERROR] 폴더가 이미 있습니다: %DEST%
  echo [안내] 기존 파일을 지우거나 덮어쓰지 않습니다.
  echo         다른 경로 예: clone.bat D:\auto_write_copy
  pause
  exit /b 2
)

echo [INFO] git clone %URL% "%DEST%"
git clone "%URL%" "%DEST%"
if errorlevel 1 (
  echo [ERROR] clone에 실패했습니다. 인터넷 연결과 GitHub 주소를 확인하세요.
  pause
  exit /b 1
)

echo.
echo [완료] %DEST%
echo [다음] setup.bat 를 더블클릭하세요.
pause
exit /b 0
