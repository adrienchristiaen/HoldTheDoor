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


def open_session_and_audit() -> tuple[SessionStore, AuditLog]:
    event = read_event()
    sid = _resolve_session_id(event)
    s = SessionStore.open()
    key_hex = s.get_meta("hmac_key")
    if key_hex is None:
        key = generate_key()
        s.set_meta("hmac_key", key.hex())
    else:
        key = bytes.fromhex(key_hex)
    audit = AuditLog(hmac_key=key)
    return s, audit


def block(reason: str, exit_code: int = 2) -> None:
    sys.stderr.write(f"claude-wall: {reason}\n")
    sys.exit(exit_code)
