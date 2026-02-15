#!/usr/bin/env bash
# Validate a single message against: <emoji> <type>[(<scope>)][!]: <description>
# Usage: lint-message.sh "message string"
# Exit 0 = valid, Exit 1 = invalid (error printed to stderr)
set -e

MSG="$1"

if [[ -z "$MSG" ]]; then
    echo "❌ Message is empty." >&2
    exit 1
fi

# Allow merge commits and reverts
if [[ "$MSG" =~ ^(Merge\ |Revert\ ) ]]; then
    exit 0
fi

TYPES="feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"

# Rule 1: Must start with an emoji (Unicode or GitHub :shortcode:)
SHORTCODE_RE='^:[a-z0-9_+-]+: '
if [[ "$MSG" =~ $SHORTCODE_RE ]]; then
    # GitHub emoji shortcode (e.g., :arrow_up: ci: bump ...)
    AFTER_EMOJI="${MSG#*: }"
elif [[ "$MSG" =~ ^:[a-z0-9_+-]+: ]]; then
    echo "❌ Missing space after emoji." >&2
    echo "   Expected: <emoji> <type>[(<scope>)][!]: <description>" >&2
    echo "   Got:      $MSG" >&2
    exit 1
else
    FIRST_BYTE=$(printf '%s' "$MSG" | LC_ALL=C head -c1 | od -An -tx1 | tr -d ' ')
    if [[ -z "$FIRST_BYTE" ]] || [[ "$((16#${FIRST_BYTE}))" -lt 128 ]]; then
        echo "❌ Must start with an emoji." >&2
        echo "   Expected: <emoji> <type>[(<scope>)][!]: <description>" >&2
        echo "   Got:      $MSG" >&2
        exit 1
    fi
    AFTER_EMOJI="${MSG#* }"
    if [[ "$AFTER_EMOJI" == "$MSG" ]]; then
        echo "❌ Missing space after emoji." >&2
        echo "   Expected: <emoji> <type>[(<scope>)][!]: <description>" >&2
        echo "   Got:      $MSG" >&2
        exit 1
    fi
fi

# Rule 2: Conventional Commits format after the emoji
if ! printf '%s' "$AFTER_EMOJI" | grep -qE "^($TYPES)(\([a-zA-Z0-9_./-]+\))?!?: .+"; then
    echo "❌ Must follow Conventional Commits after the emoji." >&2
    echo "   Expected: <emoji> <type>[(<scope>)][!]: <description>" >&2
    echo "   Got:      $MSG" >&2
    echo "   Types: $TYPES" >&2
    exit 1
fi
