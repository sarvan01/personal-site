@echo off
REM Daily routine: pull the new completed bar, then step the paper account
REM and refresh the cockpit. Double-click this, or schedule it (see
REM scripts\schedule_daily.ps1). Runs in DRY/paper mode only -- no real orders.
setlocal
cd /d "%~dp0"

REM Guard: Python must be installed and actually runnable (the window stays
REM open on failure so the reason is readable). "where python" is not enough
REM -- Windows ships a python.exe stub under WindowsApps (the "App execution
REM alias") that satisfies "where" but just redirects to the Store when run,
REM so we actually invoke it instead.
python --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found -- or only the Windows Store placeholder is on
  echo PATH ^(it satisfies "where python" but fails when actually run^).
  echo Install it from https://www.python.org/downloads/ and tick
  echo "Add python.exe to PATH" in the installer, then run:
  echo     pip install -r requirements.txt
  echo.
  echo If Python is already installed and you still see this, turn off the
  echo Store placeholder: Settings ^> Apps ^> Advanced app settings ^>
  echo App execution aliases ^> switch OFF "python.exe" / "python3.exe".
  goto :err
)

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
echo FAILED -- see the messages above. (Missing Python/packages? Network blocked?)
pause
exit /b 1
