#!/bin/bash
# Install AI Cost Observer as a macOS LaunchAgent (runs at login, auto-restarts).
set -e

PLIST_NAME="com.ai-cost-observer.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

# Check uv is available
if ! command -v uv &>/dev/null; then
    echo "ERROR: uv not found. Install it: https://docs.astral.sh/uv/"
    exit 1
fi

UV_PATH="$(command -v uv)"
echo "Using uv: $UV_PATH"
echo "Project:  $PROJECT_DIR"

# Resolve venv Python path
PYTHON_PATH="$PROJECT_DIR/.venv/bin/python"
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Virtual env not found. Running uv sync..."
    (cd "$PROJECT_DIR" && uv sync --extra macos)
fi

# Check package is importable from the venv
if ! "$PYTHON_PATH" -c "import ai_cost_observer" 2>/dev/null; then
    echo "ERROR: ai_cost_observer not importable. Run: cd $PROJECT_DIR && uv sync"
    exit 1
fi
echo "Python:   $PYTHON_PATH"

# Unload if already running
if launchctl list 2>/dev/null | grep -q "com.ai-cost-observer"; then
    echo "Stopping existing agent..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Generate plist with absolute venv Python path
cat > "$PLIST_DST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ai-cost-observer</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>-m</string>
        <string>ai_cost_observer</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/tmp/ai-cost-observer.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/ai-cost-observer.stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
PLIST

echo "Installed $PLIST_DST"

# Load and start
launchctl load "$PLIST_DST"
echo "Agent loaded and started."
echo ""
echo "Check status:  launchctl list | grep ai-cost"
echo "View logs:     tail -f /tmp/ai-cost-observer.stderr.log"
echo "Stop:          launchctl unload $PLIST_DST"
echo "Uninstall:     bash $SCRIPT_DIR/uninstall-macos.sh"
