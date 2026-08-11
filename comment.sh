#!/usr/bin/env bash
# Upsert a PR comment with a marker. Updates existing comment if found, creates new if not.
# Usage: echo "body" | ./comment.sh <pr_number> <repo> <marker>

set -euo pipefail

PR="$1"
REPO="$2"
MARKER="${3:-<!-- greenlight-agent -->}"
BODY=$(cat)

# Prepend marker (hidden in rendered markdown)
FULL_BODY="$MARKER"$'\n'"$BODY"

# Find existing comment with marker
COMMENT_ID=$(gh api "repos/$REPO/issues/$PR/comments" --paginate --jq ".[] | select(.body | startswith(\"$MARKER\")) | .id" 2>/dev/null | head -1)

if [ -n "$COMMENT_ID" ]; then
  gh api "repos/$REPO/issues/comments/$COMMENT_ID" -X PATCH -f body="$FULL_BODY" --silent
else
  echo "$FULL_BODY" | gh pr comment "$PR" --repo "$REPO" --body-file -
fi
