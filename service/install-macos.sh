#!/bin/bash
# Install AI Cost Observer as a macOS LaunchAgent (runs at login, auto-restarts).
set -e

PLIST_NAME="com.ai-cost-observer.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

# Check Python is available
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    exit 1
fi

# Resolve absolute Python path (handles pyenv, venv, Homebrew)
PYTHON_PATH="$(python3 -c "import sys; print(sys.executable)")"
echo "Using Python: $PYTHON_PATH"

# Check package is installed
if ! "$PYTHON_PATH" -c "import ai_cost_observer" 2>/dev/null; then
    echo "ERROR: ai_cost_observer not installed. Run: pip install -e ."
    exit 1
fi

# Unload if already running
if launchctl list | grep -q "com.ai-cost-observer"; then
    echo "Stopping existing agent..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Generate plist with absolute Python path
sed "s|/usr/bin/env</string>|${PYTHON_PATH}</string>|; s|<string>python3</string>||" \
    "$PLIST_SRC" > "$PLIST_DST"
echo "Installed $PLIST_DST (Python: $PYTHON_PATH)"

# Load and start
launchctl load "$PLIST_DST"
echo "Agent loaded and started."
echo ""
echo "Check status:  launchctl list | grep ai-cost"
echo "View logs:     tail -f /tmp/ai-cost-observer.log"
echo "Stop:          launchctl unload $PLIST_DST"
echo "Uninstall:     bash $SCRIPT_DIR/uninstall-macos.sh"
