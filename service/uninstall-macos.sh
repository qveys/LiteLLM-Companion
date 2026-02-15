#!/bin/bash
# Uninstall AI Cost Observer macOS LaunchAgent.
set -e

PLIST_NAME="com.ai-cost-observer.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

# Unload if running
SERVICE_NAME="${PLIST_NAME%.plist}"
SERVICE_TARGET="gui/$(id -u)/$SERVICE_NAME"
if launchctl print "$SERVICE_TARGET" &>/dev/null; then
    echo "Stopping agent..."
    launchctl bootout "$SERVICE_TARGET" 2>/dev/null || true
fi

# Remove plist
if [ -f "$PLIST_DST" ]; then
    rm "$PLIST_DST"
    echo "Removed $PLIST_DST"
else
    echo "Plist not found at $PLIST_DST (already removed?)"
fi

echo "AI Cost Observer uninstalled."
