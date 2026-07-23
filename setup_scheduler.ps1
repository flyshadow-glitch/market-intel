# setup_scheduler.ps1 — register a weekly Windows Task Scheduler job
# Run once as Administrator: .\setup_scheduler.ps1
# Edit SCHEDULE_DAY / SCHEDULE_TIME to change cadence.

param(
    [string]$ScheduleDay  = "Monday",
    [string]$ScheduleTime = "08:00",
    [string]$TaskName     = "MarketIntelWeekly"
)

$REPO   = $PSScriptRoot
$Script = Join-Path $REPO "run.ps1"

if (-not (Test-Path $Script)) {
    Write-Error "run.ps1 not found at $Script"; exit 1
}

$Action   = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$Script`""

$Trigger  = New-ScheduledTaskTrigger `
    -Weekly -DaysOfWeek $ScheduleDay -At $ScheduleTime

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable    # catches missed runs (e.g., laptop was off Monday)

$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Highest

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Replaced existing task '$TaskName'."
}

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Settings  $Settings `
    -Principal $Principal

Write-Host ""
Write-Host "Scheduled: '$TaskName' runs every $ScheduleDay at $ScheduleTime."
Write-Host "Credentials go in: $REPO\.env"
Write-Host "Test now: Start-ScheduledTask -TaskName '$TaskName'"
