@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "VENV_DIR=%REPO_ROOT%\.venv"
set "TASK_NAME=AI Cost Observer"

cd /d "%REPO_ROOT%" 2>nul && set "REPO_ROOT=%CD%"

echo Checking AI Cost Observer installation...
echo.

set "ERR=0"

:: Task exists
schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo [FAIL] Scheduled task "%TASK_NAME%" not found.
  set "ERR=1"
) else (
  echo [OK] Scheduled task "%TASK_NAME%" exists.
)

:: Venv and pythonw
if not exist "%VENV_DIR%\Scripts\pythonw.exe" (
  echo [FAIL] Venv pythonw.exe not found: %VENV_DIR%\Scripts\pythonw.exe
  set "ERR=1"
) else (
  echo [OK] Venv pythonw.exe present.
)

:: Launcher
if not exist "%SCRIPT_DIR%launcher.cmd" (
  echo [FAIL] launcher.cmd not found in service folder.
  set "ERR=1"
) else (
  echo [OK] launcher.cmd present.
)

:: Module import
if exist "%VENV_DIR%\Scripts\python.exe" (
  "%VENV_DIR%\Scripts\python.exe" -c "import ai_cost_observer" 2>nul
  if %ERRORLEVEL% neq 0 (
    echo [FAIL] ai_cost_observer module not importable.
    set "ERR=1"
  ) else (
    echo [OK] ai_cost_observer imports correctly.
  )
) else (
  echo [SKIP] python.exe missing, cannot test import.
)

:: Agent HTTP server reachable (default port 8080)
set "AGENT_URL=http://127.0.0.1:8080/health"
set "HTTP_CODE=0"
for /f %%i in ('powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri '%AGENT_URL%' -UseBasicParsing -TimeoutSec 3).StatusCode } catch { 0 }" 2^>nul') do set "HTTP_CODE=%%i"
if "%HTTP_CODE%"=="200" (
  echo [OK] Agent is running ^(HTTP 127.0.0.1:8080^).
) else (
  echo [FAIL] Agent not reachable at %AGENT_URL% — start with: schtasks /Run /TN "%TASK_NAME%"
  set "ERR=1"
)

:: Task details (trigger + task to run)
if %ERR% equ 0 (
  echo.
  echo Task details:
  schtasks /Query /TN "%TASK_NAME%" /V /FO LIST | findstr /I "TaskName Status TaskToRun NextRunTime"
)

echo.
if %ERR% neq 0 (
  echo Verification failed. Re-run install-windows.cmd as Administrator.
) else (
  echo All checks passed. Installation is correct.
)
goto :end
:end
echo.
pause
exit /b %ERR%
