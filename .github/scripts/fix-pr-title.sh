#!/usr/bin/env bash
# Auto-fix a PR title by prepending the correct gitmoji.
# Usage: fix-pr-title.sh <pr-number>
# Env:   GH_TOKEN must be set (GITHUB_TOKEN)
set -euo pipefail

PR_NUMBER="$1"

# Fetch current title
TITLE=$(gh pr view "$PR_NUMBER" --json title -q .title)
echo "Current title: $TITLE"

# Already starts with a non-ASCII char (emoji)? Nothing to do.
FIRST_BYTE=$(printf '%s' "$TITLE" | LC_ALL=C head -c1 | od -An -tx1 | tr -d ' ')
if [[ -n "$FIRST_BYTE" ]] && [[ "$((16#${FIRST_BYTE}))" -ge 128 ]]; then
    echo "Title already starts with an emoji — nothing to fix."
    exit 0
fi

# Extract the conventional commit type
if [[ "$TITLE" =~ ^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(|!:|:\ ) ]]; then
    TYPE="${BASH_REMATCH[1]}"
else
    echo "Could not extract a valid type from title — cannot auto-fix." >&2
    exit 1
fi

# Map type → gitmoji
declare -A GITMOJI=(
    [feat]="✨"
    [fix]="🐛"
    [docs]="📝"
    [style]="🎨"
    [refactor]="🧼"
    [perf]="⚡"
    [test]="🧪"
    [build]="🏗️"
    [ci]="🔧"
    [chore]="🧹"
    [revert]="⏪"
)

EMOJI="${GITMOJI[$TYPE]}"
if [[ -z "$EMOJI" ]]; then
    echo "No gitmoji mapping for type '$TYPE'." >&2
    exit 1
fi

FIXED_TITLE="${EMOJI} ${TITLE}"
echo "Fixed title:   $FIXED_TITLE"

gh pr edit "$PR_NUMBER" --title "$FIXED_TITLE"
echo "PR title updated successfully."
