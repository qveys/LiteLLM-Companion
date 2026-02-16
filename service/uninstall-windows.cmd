@echo off
set "TASK_NAME=AI Cost Observer"

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo Task "%TASK_NAME%" not found.
  pause
  exit /b 0
)

schtasks /Delete /TN "%TASK_NAME%" /F
echo Task "%TASK_NAME%" removed.
pause
