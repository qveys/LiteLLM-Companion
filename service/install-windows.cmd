@echo off
setlocal EnableDelayedExpansion

:: Run as Administrator (right-click -> Run as administrator)
net session >nul 2>&1 || (
  echo Please right-click this script and choose "Run as administrator".
  pause
  exit /b 1
)

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
set "VENV_DIR=%REPO_ROOT%\.venv"
set "TASK_NAME=AI Cost Observer"

:: Resolve REPO_ROOT to absolute path
cd /d "%REPO_ROOT%"
set "REPO_ROOT=%CD%"
cd /d "%SCRIPT_DIR%"

echo Installing AI Cost Observer as a scheduled task...
echo Repo root: %REPO_ROOT%

:: Find Python: try py with 3.12, 3.11, 3, then python
set "PY="
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
  for %%v in (3.12 3.11 3) do (
    py -%%v -c "exit(0)" 2>nul && (set "PY=py -%%v" & goto :have_py)
  )
)
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
  for /f "tokens=*" %%i in ('where python 2^>nul') do (set "PY=%%i" & goto :have_py)
)
echo Error: No Python 3.x found.
echo Install from https://www.python.org/downloads/ or run: py install 3.12
pause
exit /b 1

:have_py
echo Using Python: %PY%

:: Create venv if missing
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo Creating venv at %VENV_DIR%
  %PY% -m venv "%VENV_DIR%"
  if %ERRORLEVEL% neq 0 (echo Error: venv creation failed. & exit /b 1)
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
if not exist "%VENV_PY%" (echo Error: venv Python not found. & exit /b 1)

echo Using venv: %VENV_PY%

:: Remove broken pip leftovers in site-packages (e.g. ~ip from failed uninstall)
if exist "%VENV_DIR%\Lib\site-packages\~ip" rmdir /s /q "%VENV_DIR%\Lib\site-packages\~ip" 2>nul
for /d %%d in ("%VENV_DIR%\Lib\site-packages\~ip*") do rmdir /s /q "%%d" 2>nul

:install_deps
:: Ensure pip is available in venv (e.g. venv created without pip)
"%VENV_PY%" -m ensurepip --upgrade 2>nul
"%VENV_PY%" -m pip install -U pip --quiet 2>nul
cd /d "%REPO_ROOT%"
"%VENV_PY%" -m pip install -e . --quiet
if %ERRORLEVEL% neq 0 goto :recreate_venv
goto :deps_ok

:recreate_venv
echo.
echo Repairing pip in venv (without removing .venv)...
set "SP=%VENV_DIR%\Lib\site-packages"
if exist "%SP%\pip" rmdir /s /q "%SP%\pip" 2>nul
if exist "%SP%\pip-*.dist-info" for /d %%d in ("%SP%\pip-*.dist-info") do rmdir /s /q "%%d" 2>nul
if exist "%SP%\~ip" rmdir /s /q "%SP%\~ip" 2>nul
for /d %%d in ("%SP%\~ip*") do rmdir /s /q "%%d" 2>nul
"%VENV_PY%" -m ensurepip --upgrade
if %ERRORLEVEL% neq 0 (
  echo ensurepip failed. Try closing IDE/terminals, delete the .venv folder manually, then re-run.
  pause
  exit /b 1
)
echo Pip reinstalled. Retrying package install...
goto :install_deps

:deps_ok

"%VENV_PY%" -c "import ai_cost_observer; print('ai_cost_observer import OK')"
if %ERRORLEVEL% neq 0 (echo Error: ai_cost_observer import failed. & exit /b 1)

:: Remove existing task if present
schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% equ 0 (
  echo Removing existing task...
  schtasks /Delete /TN "%TASK_NAME%" /F
)

:: Create scheduled task: run launcher.cmd at logon (launcher sets CWD and runs pythonw)
set "LAUNCHER=%SCRIPT_DIR%launcher.cmd"
schtasks /Create /TN "%TASK_NAME%" /TR ^"\"%LAUNCHER%\"^" /SC ONLOGON /RU "%USERNAME%" /F
if %ERRORLEVEL% neq 0 (
  echo Error: schtasks /Create failed. Try without elevation: remove /RL if you added it.
  exit /b 1
)

:: Verify installation
echo.
echo --- Verification ---
schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% neq 0 (
  echo [FAIL] Scheduled task not found after create.
  exit /b 1
)
echo [OK] Scheduled task exists.

if not exist "%VENV_DIR%\Scripts\pythonw.exe" (
  echo [FAIL] pythonw.exe not found in venv.
  exit /b 1
)
echo [OK] Venv pythonw.exe present.

if not exist "%SCRIPT_DIR%launcher.cmd" (
  echo [FAIL] launcher.cmd not found.
  exit /b 1
)
echo [OK] launcher.cmd present.

"%VENV_PY%" -c "import ai_cost_observer" 2>nul
if %ERRORLEVEL% neq 0 (
  echo [FAIL] ai_cost_observer module not importable.
  exit /b 1
)
echo [OK] ai_cost_observer imports correctly.

:: Start agent now (like macOS: load and start)
echo.
echo Starting agent...
schtasks /Run /TN "%TASK_NAME%" >nul 2>&1
if %ERRORLEVEL% equ 0 (echo Agent started.) else (echo Could not start task; run manually: schtasks /Run /TN "%TASK_NAME%")

echo.
echo Installation verified. Task "%TASK_NAME%" will also start at next logon.
echo Start now:    schtasks /Run /TN "%TASK_NAME%"
echo Check status: schtasks /Query /TN "%TASK_NAME%" /V /FO LIST
echo Remove:       schtasks /Delete /TN "%TASK_NAME%" /F
echo.
pause
