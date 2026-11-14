@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto failed
set "PYTHONDONTWRITEBYTECODE=1"
echo RHINO Turret Compass v0.2.2-beta.2 - project-local beta environment
echo Run as an ordinary user in a fresh extracted project folder.
py -3.12 -c "import sys,struct,platform;sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 and platform.machine().lower() in ('amd64','x86_64') else 1)" >nul 2>nul
if errorlevel 1 goto python_missing
rem PySide6 ships deeply nested resources. Verify the FULL extracted folder
rem path before creating a venv or downloading any package on Windows.
py -3.12 -c "import os,sys; n=len(os.path.abspath('.')); print('Project folder path length:',n); sys.exit(0 if n<=70 else 2)"
if errorlevel 1 goto path_too_long
if exist ".venv\Scripts\python.exe" goto check_existing
if exist ".venv" goto bad_venv
py -3.12 -m venv .venv
if errorlevel 1 goto failed
:check_existing
".venv\Scripts\python.exe" -c "import sys,struct,platform;sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 and platform.machine().lower() in ('amd64','x86_64') else 1)" >nul 2>nul
if errorlevel 1 goto bad_venv
echo.
echo This setup step uses the internet to download three pinned packages from PyPI.
echo The compass processes the selected HUD image locally.
".venv\Scripts\python.exe" -m pip --isolated install --index-url https://pypi.org/simple --require-hashes --only-binary=:all: --disable-pip-version-check --no-input --no-cache-dir -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -B environment_check.py
if errorlevel 1 goto failed
echo.
echo Setup complete. Next: Run_Tests.cmd, then Run_Beta.cmd.
pause
exit /b 0
:path_too_long
echo Installation location is too deep for some PySide6 wheel files.
echo Copy/extract the whole project to a SHORT path, for example:
echo     %USERPROFILE%\RTC
echo Do not install into a long deeply nested Downloads or project folders.
echo No virtual environment was created and no dependencies were downloaded.
pause
exit /b 1
:python_missing
echo Python 3.12 Windows 64-bit was not found through the Python launcher.
echo Install Python 3.12 x86-64 from python.org; see START_HERE.html or README.md.
pause
exit /b 1
:bad_venv
echo An existing .venv here is incompatible or incomplete. Nothing was deleted.
echo Use a fresh extracted beta folder for setup.
pause
exit /b 1
:failed
echo Setup stopped. Read the error above. Do not bypass a checksum failure.
echo Keep the displayed error for troubleshooting.
pause
exit /b 1
