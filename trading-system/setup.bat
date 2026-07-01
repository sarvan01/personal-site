@echo off
REM One-time setup: fetch the majors and build the cockpit. Run this once.
REM After this, use daily.bat (or the scheduler) for the recurring daily run.
REM Non-destructive: it does NOT touch an existing paper ledger.
REM (The H2 privacy research is closed/archived; see scripts\research\.)
setlocal
cd /d "%~dp0"

REM Guard: Python must be installed and on PATH.
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install it from https://www.python.org/downloads/ and tick
  echo "Add python.exe to PATH" in the installer, then run:
  echo     pip install -r requirements.txt
  goto :err
)

echo [1/2] Fetching majors (BTC/ETH/BNB/XRP/SOL)...
python scripts\fetch_data.py --config h1b
if errorlevel 1 goto :err

echo [2/2] Building the cockpit...
python scripts\cockpit.py --config h1b
if errorlevel 1 goto :err

echo.
echo Setup complete. Opening the cockpit.
start "" "out\cockpit.html"
echo From now on, run daily.bat once a day (or schedule it).
exit /b 0

:err
echo.
echo FAILED -- see the messages above. (Missing Python/packages? Network blocked?)
pause
exit /b 1
