@echo off
REM Sets PY to a working Python command, or exits with errorlevel 1.
REM Tries "python" first, then the "py" launcher: on Windows, "python" can be
REM a Store placeholder or an alias that isn't wired up even when Python is
REM installed (e.g. via the Python install manager), while "py" still works.
REM Deliberately no setlocal, so PY is visible to the calling script.
set "PY="
python --version >nul 2>nul && set "PY=python"
if not defined PY (py --version >nul 2>nul && set "PY=py")
if defined PY exit /b 0

echo Python was not found ^(neither "python" nor "py" runs^).
echo Install it from https://www.python.org/downloads/ ^(tick
echo "Add python.exe to PATH"^), open a NEW terminal, then run:
echo     py -m pip install -r requirements.txt
exit /b 1
