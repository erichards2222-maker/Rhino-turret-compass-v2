@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1
py -3.12 -B tools\verify_package.py
if errorlevel 1 (echo Verification failed. Check the error above. & pause & exit /b 1)
pause
exit /b 0
