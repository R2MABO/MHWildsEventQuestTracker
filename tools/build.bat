@echo off
setlocal
cd /d "%~dp0.."
title Wilds Quest Tracker - Build

if exist ".venv-build\Scripts\python.exe" (
    ".venv-build\Scripts\python.exe" tools\package_release.py %*
    goto result
)

if not exist ".python-path" goto standard
set /p "tracker_python="<".python-path"
if not exist "%tracker_python%" goto standard
"%tracker_python%" tools\package_release.py %*
goto result

:standard
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto try_python
py -3 tools\package_release.py %*
goto result

:try_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto try_python3
python tools\package_release.py %*
goto result

:try_python3
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto missing_python
python3 tools\package_release.py %*

:result
set "build_exit=%errorlevel%"
echo.
if not "%build_exit%"=="0" goto failed
echo Build erfolgreich. ZIP-Pfade siehe oben (Standard: Quellcode-ZIP und Windows-ZIP).
goto end

:failed
echo Build fehlgeschlagen. Fehlercode: %build_exit%
echo Build-Abhaengigkeiten installieren: python -m pip install -r tools\requirements-build.txt
goto end

:missing_python
set "build_exit=1"
echo Python 3.10 oder neuer wurde nicht gefunden.
echo Bitte Python von https://www.python.org/downloads/ installieren.
echo Bei der Windows-Installation "Add Python to PATH" aktivieren.

:end
echo.
pause
exit /b %build_exit%
