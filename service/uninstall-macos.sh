#!/bin/bash
# Uninstall AI Cost Observer macOS LaunchAgent.
set -e

PLIST_NAME="com.ai-cost-observer.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

# Unload if running
if launchctl list | grep -q "com.ai-cost-observer"; then
    echo "Stopping agent..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Remove plist
if [ -f "$PLIST_DST" ]; then
    rm "$PLIST_DST"
    echo "Removed $PLIST_DST"
else
    echo "Plist not found at $PLIST_DST (already removed?)"
fi

echo "AI Cost Observer uninstalled."
