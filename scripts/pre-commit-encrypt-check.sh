#!/usr/bin/env bash
# Optional git pre-commit hook: verify model/prompts/*.txt.enc files are in
# sync with their plaintext counterparts before allowing the commit through.
#
# Install with:
#     cp scripts/pre-commit-encrypt-check.sh .git/hooks/pre-commit
#     chmod +x .git/hooks/pre-commit
#
# Requires PROMPTS_ENCRYPTION_KEY in the environment (e.g. via .env loaded
# into your shell, or pass it inline: PROMPTS_ENCRYPTION_KEY=... git commit ...).
#
# Why this exists: editing model/prompts/<name>.txt without re-encrypting
# leaves the committed .txt.enc stale, which means the pod runs old content
# after deployment. This hook catches that drift before it ships.
set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)
PYTHON="${PYTHON:-python3}"

# Find any staged .txt.enc files in model/prompts/
staged_enc=$(git diff --cached --name-only --diff-filter=AM | grep -E '^model/prompts/.*\.txt\.enc$' || true)

if [ -z "$staged_enc" ]; then
    exit 0  # nothing to verify
fi

if [ -z "${PROMPTS_ENCRYPTION_KEY:-}" ]; then
    echo "ERROR: PROMPTS_ENCRYPTION_KEY is not set; cannot verify staged .txt.enc files." >&2
    echo "       Source your .env or pass the key inline: PROMPTS_ENCRYPTION_KEY=... git commit ..." >&2
    exit 1
fi

failed=0
while IFS= read -r enc_path; do
    if ! "$PYTHON" "$REPO_ROOT/scripts/encrypt-prompts.py" verify "$REPO_ROOT/$enc_path"; then
        failed=1
    fi
done <<< "$staged_enc"

if [ "$failed" -ne 0 ]; then
    echo "" >&2
    echo "Drift detected in staged .txt.enc file(s). Re-encrypt with:" >&2
    echo "  python scripts/encrypt-prompts.py encrypt" >&2
    echo "and re-stage the updated .txt.enc file(s) before committing." >&2
    exit 1
fi
