# Install AI Cost Observer as a Windows Scheduled Task (runs at logon, auto-restarts).
#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"
$TaskName = "AI Cost Observer"

# Resolve absolute Python path (handles venv, pyenv, standard installs)
$PythonExe = & python -c "import sys; print(sys.executable)" 2>$null
if (-not $PythonExe) {
    Write-Error "python not found. Install Python 3.10+ first."
    exit 1
}
# Prefer pythonw.exe for windowless execution
$PythonDir = Split-Path $PythonExe
$PythonW = Join-Path $PythonDir "pythonw.exe"
if (-not (Test-Path $PythonW)) {
    $PythonW = $PythonExe
    Write-Warning "pythonw.exe not found, using python.exe (console window will be visible)"
}
Write-Host "Using Python: $PythonW"

# Check package is installed
& $PythonW -c "import ai_cost_observer" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "ai_cost_observer not installed. Run: pip install -e ."
    exit 1
}

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the scheduled task
$Action = New-ScheduledTaskAction -Execute $PythonW -Argument "-m ai_cost_observer"
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "AI Cost Observer — monitors AI tool usage and exports metrics via OpenTelemetry"

Write-Host ""
Write-Host "Task '$TaskName' installed and will start at next logon."
Write-Host ""
Write-Host "Start now:    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Check status: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove:       Unregister-ScheduledTask -TaskName '$TaskName'"
