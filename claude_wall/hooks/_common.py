"""Shared helpers for hook entry points.

Each hook runs as `python -m claude_wall.hooks.<name>`: reads a single JSON
event from stdin, processes it, optionally writes a JSON response to stdout,
and exits with the appropriate code (0 = pass, 2 = block).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from ..audit import AuditLog, generate_key
from ..session import SessionStore


# Tool name normalization: CLI-specific names → canonical names used in logic
TOOL_ALIASES: dict[str, str] = {
    # Gemini CLI tool names
    "run_shell_command": "Bash",
    "run_code": "Bash",
    "read_file": "Read",
    "write_file": "Write",
    "replace_in_file": "Edit",
    "fetch_webpage": "WebFetch",
    "fetch_url": "WebFetch",
    # Codex CLI aliases
    "bash": "Bash",
    "read": "Read",
    "apply_patch": "Edit",
}


def normalize_tool(name: str | None) -> str:
    if not name:
        return ""
    return TOOL_ALIASES.get(name, name)


_event_cache: dict[str, Any] | None = None


def read_event() -> dict[str, Any]:
    global _event_cache
    if _event_cache is not None:
        return _event_cache
    try:
        raw = sys.stdin.read()
    except Exception:
        _event_cache = {}
        return {}
    if not raw.strip():
        _event_cache = {}
        return {}
    try:
        _event_cache = json.loads(raw)
        return _event_cache
    except json.JSONDecodeError:
        _event_cache = {}
        return {}


def _resolve_session_id(event: dict[str, Any]) -> str:
    # Try all known CLI session ID env vars
    for var in ("CLAUDE_SESSION_ID", "GEMINI_SESSION_ID", "CODEX_SESSION_ID"):
        val = os.environ.get(var)
        if val:
            return val
    # Fall back to session_id in the stdin event JSON (Gemini passes it here)
    sid = event.get("session_id") or event.get("sessionId")
    return str(sid) if sid else "default"


def write_output(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def _load_persistent_hmac_key() -> bytes:
    """Load (or create) the persistent HMAC key stored next to the audit log.

    Stored at ~/.local/share/claude-wall/hmac.key so it survives across
    sessions and /tmp clears — enabling cross-session chain verification.
    """
    from ..audit import default_audit_path
    key_path = default_audit_path().parent / "hmac.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        data = key_path.read_bytes()
        if len(data) == 32:
            return data
    key = generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    return key


def open_session_and_audit() -> tuple[SessionStore, AuditLog]:
    event = read_event()
    _resolve_session_id(event)
    s = SessionStore.open()
    key = _load_persistent_hmac_key()
    audit = AuditLog(hmac_key=key)
    return s, audit


def block(reason: str, exit_code: int = 2) -> None:
    sys.stderr.write(f"claude-wall: {reason}\n")
    sys.exit(exit_code)
