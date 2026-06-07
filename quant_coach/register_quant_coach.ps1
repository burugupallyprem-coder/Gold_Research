# register_quant_coach.ps1
# ============================================================
# Registers Windows Task Scheduler to run quant_coach.py twice a day:
#   • 8:00 AM  — the day's full, detailed lesson
#   • 8:00 PM  — the matching interview drill, then advances to the next topic
# Teaches you the Gold Quant Lab project, one concept per day.
#
# HOW TO USE (one time only):
#   1. This file lives in: C:\Users\Prem\Desktop\prem\OANDA\quant_coach\
#   2. Copy .env.example to .env and fill in SLACK_BOT_TOKEN + QUANT_COACH_CHANNEL_ID
#   3. Right-click PowerShell -> "Run as Administrator"
#   4. cd "C:\Users\Prem\Desktop\prem\OANDA\quant_coach"
#   5. powershell -ExecutionPolicy Bypass -File .\register_quant_coach.ps1
#
# To remove later:
#   Get-ScheduledTask | Where-Object {$_.TaskName -like 'QuantCoach_*'} | Unregister-ScheduledTask -Confirm:$false
# ============================================================
$ErrorActionPreference = 'Stop'

# ---- Paths ----
$CoachDir = "C:\Users\Prem\Desktop\prem\OANDA\quant_coach"
$CoachPy  = Join-Path $CoachDir "quant_coach.py"
if (-not (Test-Path $CoachPy)) {
    Write-Error "quant_coach.py not found at $CoachPy"
    exit 1
}

# Find Python (prefer a local venv, else system python)
$VenvPython = Join-Path $CoachDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Error "Python not found. Install Python and ensure it is on your PATH."
        exit 1
    }
    $Python = $cmd.Source
}
Write-Host "Using Python: $Python" -ForegroundColor Cyan

# ---- Two tasks per day: morning lesson + evening drill ----
$schedule = @(
    @{ Name = "QuantCoach_AM"; Time = "8:00AM";  Desc = "Quant Coach - morning detailed lesson" },
    @{ Name = "QuantCoach_PM"; Time = "8:00PM";  Desc = "Quant Coach - evening interview drill" }
)

foreach ($task in $schedule) {
    $name = $task.Name
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }

    $action = New-ScheduledTaskAction `
        -Execute $Python `
        -Argument "`"$CoachPy`"" `
        -WorkingDirectory $CoachDir
    $trigger = New-ScheduledTaskTrigger -Daily -At $task.Time
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    $principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description $task.Desc | Out-Null
    Write-Host "  Registered $name -> runs daily at $($task.Time)" -ForegroundColor Green
}

Write-Host ""
Write-Host "SUCCESS! Quant Coach will post ONE detailed lesson at 8 AM and its drill at 8 PM, daily." -ForegroundColor Green
Write-Host ""
Write-Host "Verify:"
Write-Host "  Get-ScheduledTask | Where-Object { `$_.TaskName -like 'QuantCoach_*' } | Select TaskName, State"
Write-Host ""
Write-Host "Test the morning lesson right now:"
Write-Host "  schtasks /Run /TN QuantCoach_AM"
