<#
.SYNOPSIS
  Register (or remove) a Windows Scheduled Task that runs daily.bat once a day.

.USAGE
  # Register at 02:30 local time (pick a time AFTER 01:00 UTC so the bar is closed):
  powershell -ExecutionPolicy Bypass -File scripts\schedule_daily.ps1 -At 02:30

  # Remove the task:
  powershell -ExecutionPolicy Bypass -File scripts\schedule_daily.ps1 -Remove

.NOTES
  Task Scheduler uses LOCAL time. Binance daily bars close at 00:00 UTC, so
  choose a local time that is comfortably past that. The task runs daily.bat,
  which only fetches data and updates the cockpit/paper account -- it never
  places real orders.
#>
param(
  [string]$At = "02:30",
  [string]$TaskName = "TradingSystemDaily",
  [switch]$Remove
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$bat = Join-Path $projectDir "daily.bat"

if ($Remove) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed scheduled task '$TaskName'."
  exit 0
}

if (-not (Test-Path $bat)) { throw "daily.bat not found at $bat" }

$action  = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Description "Daily fetch + cockpit (paper mode)" -Force | Out-Null

Write-Host "Registered '$TaskName' to run daily at $At (local time)."
Write-Host "It runs: $bat"
Write-Host "Check it in Task Scheduler, or run 'Get-ScheduledTask -TaskName $TaskName'."
