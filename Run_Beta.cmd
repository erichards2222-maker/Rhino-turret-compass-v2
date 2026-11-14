@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup_Beta.cmd in this extracted folder first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B environment_check.py
if errorlevel 1 (
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B turret_compass_beta.py
if errorlevel 1 (
  echo The beta stopped with an error. Keep this output for troubleshooting.
  echo Redact your Windows username and paths before sharing a screenshot.
  pause
  exit /b 1
)
exit /b 0
