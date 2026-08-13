@echo off
REM TESTNET daily routine: the normal paper flow (fetch + cockpit), then
REM place the day's orders on Binance Spot TESTNET (play money).
REM
REM Requires BINANCE_KEY / BINANCE_SECRET env vars holding TESTNET keys from
REM https://testnet.binance.vision. This script can NEVER trade real money:
REM the venue is hardcoded to testnet, and live additionally requires the
REM ALLOW_LIVE_TRADING env var plus an explicit --i-understand-live flag
REM that nothing here passes.
REM
REM Point the scheduler at THIS file instead of daily.bat once you enter the
REM testnet stage (see scripts\schedule_daily.ps1 -- edit $bat or re-register).
setlocal
cd /d "%~dp0"

if "%BINANCE_KEY%"=="" (
  echo BINANCE_KEY is not set. Get free TESTNET keys at
  echo https://testnet.binance.vision then run:
  echo     setx BINANCE_KEY "your_testnet_key"
  echo     setx BINANCE_SECRET "your_testnet_secret"
  echo and open a NEW terminal. Never paste keys into chats or files.
  goto :err
)

call daily.bat
if errorlevel 1 goto :err

echo.
echo [3/3] Placing today's orders on TESTNET (play money)...
python scripts\execute.py --config h1b --venue testnet --execute
if errorlevel 1 (
  echo Testnet execution reported a problem -- see above. The paper run
  echo above still completed; fix the testnet issue and re-run this file.
  goto :err
)

echo.
echo Testnet routine complete.
exit /b 0

:err
echo.
pause
exit /b 1
