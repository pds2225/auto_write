@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo ========================================
echo Auto Write 설치 도구
echo ========================================
echo.

set "ROOT_DIR=%~dp0"
set "APP_DIR=%ROOT_DIR%app"
set "REQ_FILE=%APP_DIR%\requirements.txt"

if not exist "%APP_DIR%" (
  echo [ERROR] app 폴더를 찾지 못했습니다: %APP_DIR%
  pause
  exit /b 1
)

if not exist "%REQ_FILE%" (
  echo [ERROR] requirements.txt를 찾지 못했습니다: %REQ_FILE%
  pause
  exit /b 1
)

set "PYTHON_EXE="
for %%P in (
  "%LocalAppData%\Programs\Python\Python313\python.exe"
  "%LocalAppData%\Programs\Python\Python312\python.exe"
  "%LocalAppData%\Programs\Python\Python311\python.exe"
  "%ProgramFiles%\Python313\python.exe"
  "%ProgramFiles%\Python312\python.exe"
  "%ProgramFiles%\Python311\python.exe"
) do (
  if exist "%%~fP" (
    set "PYTHON_EXE=%%~fP"
    goto :python_found
  )
)

for /f "delims=" %%P in ('where python 2^>nul') do (
  echo %%P | find /I "WindowsApps" >nul
  if errorlevel 1 (
    set "PYTHON_EXE=%%P"
    goto :python_found
  )
)

if not defined PYTHON_EXE (
  echo [ERROR] Python 3.11 이상을 찾지 못했습니다.
  echo [안내] https://www.python.org/downloads/windows/ 에서 Python을 설치하고,
  echo        설치 시 "Add python.exe to PATH"를 체크하세요.
  pause
  exit /b 1
)

:python_found
echo [INFO] Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version
if errorlevel 1 (
  echo [ERROR] Python 실행에 실패했습니다.
  pause
  exit /b 1
)

echo.
echo [1/3] pip 업그레이드
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
  echo [WARN] pip 업그레이드에 실패했습니다. 설치는 계속 진행합니다.
)

echo.
echo [2/3] Auto Write 필수 패키지 설치
"%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
  echo [ERROR] 필수 패키지 설치에 실패했습니다.
  echo [조치] 인터넷 연결, Python 권한, 백신 차단 여부를 확인하세요.
  pause
  exit /b 1
)

echo.
echo [3/3] 테스트 도구 설치
"%PYTHON_EXE%" -m pip install pytest
if errorlevel 1 (
  echo [WARN] pytest 설치에 실패했습니다. 앱 실행은 가능할 수 있습니다.
)

echo.
echo ========================================
echo 설치 완료
echo ========================================
echo 다음 순서로 실행하세요.
echo 1. check_env.bat 실행
echo 2. launch.bat 실행
echo 3. 브라우저에서 http://127.0.0.1:8765 접속
echo.
pause
