# Story 8 Review Brief: Daemon Installation + README

## What was built

- macOS launchd daemon with auto-start on login and crash restart
- Windows Task Scheduler daemon with logon trigger and failure retry
- Comprehensive README.md with cross-platform install guide

### Files created
- `service/com.ai-cost-observer.plist` — macOS launchd configuration
- `service/install-macos.sh` — macOS install script (checks dependencies, unloads existing, installs)
- `service/install-windows.ps1` — Windows install script (Task Scheduler)
- `service/uninstall-windows.ps1` — Windows uninstall script
- `README.md` — Full documentation

### Key design decisions
1. **`/usr/bin/env python3`** in plist — avoids hardcoding Python path, works with Homebrew/system Python
2. **`KeepAlive` on failure only** (`SuccessfulExit: false`) — restarts crashed agent but respects intentional stops
3. **Logs to `/tmp/`** — avoids permission issues, easy to find for debugging
4. **Windows `pythonw.exe`** — windowless execution, no console window at login
5. **3 restart retries** on Windows — matches macOS KeepAlive behavior
6. **Install scripts verify prerequisites** — checks Python, package installation before proceeding

## Acceptance criteria results

- [x] macOS: launchd plist with RunAtLoad, KeepAlive on failure — **PASS**
- [x] macOS: install script checks dependencies, copies plist, loads service — **PASS**
- [x] Windows: Task Scheduler with logon trigger, restart on failure, windowless — **PASS**
- [x] Windows: install/uninstall scripts — **PASS**
- [x] README: prerequisites, quick start (macOS + Windows), backend setup — **PASS**
- [x] README: config guide with YAML example and env vars — **PASS**
- [x] README: troubleshooting section (connection, detection, extension issues) — **PASS**
- [x] README: separate macOS and Windows sections — **PASS**

## Review questions

1. **macOS plist**: The plist uses `/usr/bin/env python3` which resolves at runtime. If the user has multiple Python versions, this might pick the wrong one. Should we detect and hardcode the venv Python path during install?

2. **Windows path**: The PowerShell script assumes `pythonw.exe` is on PATH. Should it resolve the full path during installation?

3. **Log rotation**: Neither platform has log rotation configured. macOS logs to `/tmp/` (cleared on reboot) which is self-cleaning, but Windows has no equivalent. Should we add `logrotate` or limit file size?

4. **README completeness**: The README covers quick start but doesn't mention the review/feedback workflow (BMAD methodology). Should development workflow be documented?

5. **Uninstall on macOS**: There's no `uninstall-macos.sh` script. The README documents manual `launchctl unload` commands. Should we add a matching uninstall script?

## Code excerpts for review

### macOS plist key sections
```xml
<key>ProgramArguments</key>
<array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>-m</string>
    <string>ai_cost_observer</string>
</array>
<key>RunAtLoad</key>
<true/>
<key>KeepAlive</key>
<dict><key>SuccessfulExit</key><false/></dict>
```

### Windows Task Scheduler trigger
```powershell
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)
```

## Gemini Review Conclusions

This story successfully delivers the necessary components for daemon installation and user documentation. However, the review identifies two major reliability issues that should be addressed to ensure a stable user experience.

1.  **Python Path Resolution (Q1, Q2)**
    - **Severity**: Major
    - **Finding**: The install scripts for both macOS and Windows depend on the Python executable being available in the system's default `PATH` for the daemon user. This is not a safe assumption and will fail for users with non-standard Python installations or complex environments (e.g., `pyenv`, virtual environments not on the PATH).
    - **Recommendation**: The install scripts **must be modified** to be more robust. During installation, they should detect the absolute path to the Python executable that is running the install process and hardcode that full path into the generated service file (`.plist` or Task Scheduler action). This ensures the daemon always uses the correct, intended Python interpreter.

2.  **Log Rotation on Windows (Q3)**
    - **Severity**: Major
    - **Finding**: The agent does not implement any log rotation or cleanup strategy on Windows. This will cause the log file to grow indefinitely, which can consume significant disk space over time.
    - **Recommendation**: A log management strategy must be implemented for Windows. A simple approach is to add logic to the agent to truncate the log file at startup if it exceeds a certain size (e.g., 10MB). A more robust solution would be to use a dedicated logging handler, such as Python's `RotatingFileHandler`.

3.  **Missing macOS Uninstall Script (Q5)**
    - **Severity**: Minor
    - **Finding**: A `uninstall-windows.ps1` is provided, but no corresponding `uninstall-macos.sh` exists, leading to an inconsistent user experience.
    - **Recommendation**: Create an `uninstall-macos.sh` script to provide symmetrical functionality. It should unload the `launchd` service and remove the `.plist` file.

4.  **Development Workflow Documentation (Q4)**
    - **Severity**: Suggestion
    - **Finding**: The project's development methodology (BMAD, reviews) is not documented.
    - **Recommendation**: Create a `CONTRIBUTING.md` file in the repository root to document the development workflow. The `README.md` should remain focused on end-user instructions.

**Overall Verdict**: **Approved, with reservations.** The story is functionally complete, but the `Major` issues concerning Python path resolution and Windows log rotation should be addressed to prevent common installation and runtime failures.

## Resolution Notes (Post-Review)

### Finding 1 — Python Path Resolution: **FIXED**
- `service/install-macos.sh`: Now resolves the absolute Python path via `sys.executable` and injects it into the plist using `sed`, replacing `/usr/bin/env python3`.
- `service/install-windows.ps1`: Now resolves the full path via `python -c "import sys; print(sys.executable)"` and derives `pythonw.exe` from the same directory.
**Status:** Resolved.

### Finding 2 — Log Rotation: **FIXED**
- Added `RotatingFileHandler` to `src/ai_cost_observer/main.py` (10 MB max, 3 backups).
- Cross-platform log paths: `/tmp/ai-cost-observer.log` (macOS), `%LOCALAPPDATA%/ai-cost-observer/logs/` (Windows).
**Status:** Resolved.

### Finding 3 — macOS Uninstall Script: **FIXED**
- Created `service/uninstall-macos.sh` with `launchctl unload` + plist removal.
**Status:** Resolved.

### Finding 4 — CONTRIBUTING.md: **Deferred**
- Development workflow documentation is out of scope for MVP. Will be addressed post-MVP.
**Status:** Deferred.

**Updated Verdict**: **Approved.** All Major and Minor findings resolved.

## How to provide feedback

Argue against decisions, suggest alternatives, challenge assumptions.
Format: structured feedback with severity (Critical/Major/Minor/Suggestion).
