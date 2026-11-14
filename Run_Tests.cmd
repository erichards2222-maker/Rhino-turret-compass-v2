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
".venv\Scripts\python.exe" -B -m unittest discover -s tests -t . -v
if errorlevel 1 (echo TESTS FAILED - do not continue to gameplay yet. & pause & exit /b 1)
echo.
echo Software regression checks passed. Windows UI, capture, hotkey and Elite accuracy still require your test.
pause
exit /b 0
