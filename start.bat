@echo off
setlocal
cd /d "%~dp0"
title Wilds Quest Tracker
if not exist ".python-path" goto standard
set /p "tracker_python="<".python-path"
if not exist "%tracker_python%" goto standard
"%tracker_python%" app.py %*
goto end
:standard
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    py -3 app.py %*
    goto end
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    python app.py %*
    goto end
)
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    python3 app.py %*
    goto end
)
echo Python 3.10 oder neuer wurde nicht gefunden.
echo Bitte Python von https://www.python.org/downloads/ installieren.
echo Bei der Windows-Installation "Add Python to PATH" aktivieren.
:end
pause
