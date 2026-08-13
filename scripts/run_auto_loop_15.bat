@echo off
setlocal EnableExtensions
echo [1/2] pytest...
call "%~dp0run_loop_tests.bat"
if errorlevel 1 exit /b 1
echo [2/2] git push (origin current branch)...
git -C "%~dp0." push -u origin HEAD
exit /b %ERRORLEVEL%
