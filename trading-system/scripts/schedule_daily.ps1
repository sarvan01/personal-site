<#
.SYNOPSIS
  Register (or remove) a Windows Scheduled Task that runs the daily routine.

.USAGE
  # Paper-only stage (runs daily.bat):
  powershell -ExecutionPolicy Bypass -File scripts\schedule_daily.ps1 -At 02:30

  # Testnet stage (runs daily_testnet.bat = paper flow + testnet orders):
  powershell -ExecutionPolicy Bypass -File scripts\schedule_daily.ps1 -At 02:30 -Script daily_testnet.bat

  # Remove the task:
  powershell -ExecutionPolicy Bypass -File scripts\schedule_daily.ps1 -Remove

.NOTES
  Task Scheduler uses LOCAL time. Binance daily bars close at 00:00 UTC, so
  choose a local time comfortably past that (e.g. 02:30 works for most
  timezones west of UTC; if you are east of UTC, any morning hour is fine).
  Re-running this script simply replaces the existing task (-Force), so
  switching stages is just re-running with a different -Script.
  Neither script can trade real money: live requires ALLOW_LIVE_TRADING plus
  an explicit --i-understand-live flag that no scheduled script passes.
#>
param(
  [string]$At = "02:30",
  [string]$Script = "daily.bat",
  [string]$TaskName = "TradingSystemDaily",
  [switch]$Remove
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$bat = Join-Path $projectDir $Script

if ($Remove) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed scheduled task '$TaskName'."
  exit 0
}

if (-not (Test-Path $bat)) { throw "$Script not found at $bat" }

$action  = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Description "Trading system daily routine ($Script)" -Force | Out-Null

Write-Host "Registered '$TaskName' to run daily at $At (local time)."
Write-Host "It runs: $bat"
Write-Host "Check it in Task Scheduler, or run 'Get-ScheduledTask -TaskName $TaskName'."
