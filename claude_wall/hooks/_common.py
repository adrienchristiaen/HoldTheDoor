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


def read_event() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def write_output(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def open_session_and_audit() -> tuple[SessionStore, AuditLog]:
    sid = os.environ.get("CLAUDE_SESSION_ID") or "default"
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
