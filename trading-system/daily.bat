@echo off
REM Daily routine: pull the new completed bar, then step the paper account
REM and refresh the cockpit. Double-click this, or schedule it (see
REM scripts\schedule_daily.ps1). Runs in DRY/paper mode only -- no real orders.
setlocal
cd /d "%~dp0"

echo [1/2] Fetching latest data...
python scripts\fetch_data.py --config h1b
if errorlevel 1 goto :err

echo [2/2] Updating cockpit and paper account...
python scripts\cockpit.py --config h1b
if errorlevel 1 goto :err

echo.
echo Done. Open out\cockpit.html
start "" "out\cockpit.html"
exit /b 0

:err
echo.
echo FAILED -- see the messages above. (Network blocked? Re-run later.)
exit /b 1
