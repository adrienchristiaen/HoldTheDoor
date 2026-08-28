#!/usr/bin/env bash
# holdthedoor end-to-end demo. Exercises all 3 hooks + CLI without touching ~/.claude.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export PYTHONPATH="$ROOT"
export CLAUDE_SESSION_ID="demo-$$"
export HOLDTHEDOOR_SESSION_ROOT="$TMP/sess"
export HOLDTHEDOOR_AUDIT_DIR="$TMP/audit"
export HOLDTHEDOOR_SETTINGS_PATH="$TMP/settings.json"

echo "=== 1. PostToolUse redact ==="
echo '{"tool_name":"Bash","tool_response":{"stdout":"OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKL\nemail=alice@example.com"}}' \
  | python3 -m holdthedoor.hooks.post_tool_use
echo

echo "=== 2. PreToolUse block .env ==="
cd "$TMP"
echo "SECRET=1" > .env
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' \
  | python3 -m holdthedoor.hooks.pre_tool_use && echo "FAIL: should have blocked" || echo "blocked as expected (exit $?)"
cd "$ROOT"
echo

echo "=== 3. UserPromptSubmit warn ==="
echo '{"prompt":"please email alice@example.com"}' \
  | python3 -m holdthedoor.hooks.user_prompt_submit
echo

echo "=== 4. CLI: install --dry-run ==="
python3 -m holdthedoor.cli install --dry-run --yes | head -20
echo

echo "=== 5. CLI: install ==="
python3 -m holdthedoor.cli install --yes
echo

echo "=== 6. CLI: status ==="
python3 -m holdthedoor.cli status
echo

echo "=== 7. CLI: reveal ==="
python3 -m holdthedoor.cli reveal '[WALL:openai_key:1]'
python3 -m holdthedoor.cli reveal '[WALL:email:1]'
echo

echo "=== 8. CLI: audit --verify ==="
python3 -m holdthedoor.cli audit --verify
echo

echo "=== 9. CLI: uninstall ==="
python3 -m holdthedoor.cli uninstall --yes
echo

echo "demo complete"
