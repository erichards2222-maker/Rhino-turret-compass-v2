@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup_Beta.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B environment_check.py
if errorlevel 1 (pause & exit /b 1)
".venv\Scripts\python.exe" -B tools\gui_smoke.py
if errorlevel 1 (echo UI CHECK FAILED - preserve the error. & pause & exit /b 1)
pause
exit /b 0
