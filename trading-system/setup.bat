@echo off
REM One-time setup: fetch the majors AND the privacy basket, then build the
REM cockpit. Run this once. After this, use daily.bat (or the scheduler) for
REM the recurring daily run. Non-destructive: it does NOT touch an existing
REM paper ledger.
setlocal
cd /d "%~dp0"

echo [1/3] Fetching majors (BTC/ETH/BNB/XRP/SOL)...
python scripts\fetch_data.py --config h1b
if errorlevel 1 goto :err

echo [2/3] Fetching privacy basket for the Railgun study...
python scripts\fetch_privacy.py
if errorlevel 1 echo   (privacy fetch failed -- continuing; retry later with: python scripts\fetch_privacy.py)

echo [3/3] Building the cockpit...
python scripts\cockpit.py --config h1b
if errorlevel 1 goto :err

echo.
echo Setup complete. Opening the cockpit.
start "" "out\cockpit.html"
echo From now on, run daily.bat once a day (or schedule it).
exit /b 0

:err
echo.
echo FAILED -- see the messages above.
exit /b 1
