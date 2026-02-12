# Uninstall AI Cost Observer scheduled task.
$TaskName = "AI Cost Observer"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Task '$TaskName' removed."
} else {
    Write-Host "Task '$TaskName' not found."
}
