"""PreToolUse hook: block calls targeting sensitive paths."""

from __future__ import annotations

import os
import sys
from typing import Any

from ..workspace import WorkspaceGuard
from ._common import block, normalize_tool, open_session_and_audit, read_event


def _extract_path(event: dict[str, Any]) -> str | None:
    inp = event.get("tool_input") or {}
    if isinstance(inp, dict):
        for key in ("file_path", "path", "filename"):
            v = inp.get(key)
            if isinstance(v, str) and v:
                return v
    return None


def _extract_command(event: dict[str, Any]) -> str | None:
    inp = event.get("tool_input") or {}
    if isinstance(inp, dict):
        v = inp.get("command")
        if isinstance(v, str) and v:
            return v
    return None


def main() -> int:
    if os.environ.get("CLAUDE_WALL_DISABLED") == "1":
        return 0
    event = read_event()
    tool = normalize_tool(event.get("tool_name"))
    session, audit, cli = open_session_and_audit()
    try:
        guard = WorkspaceGuard()
        guard.scan()
        if tool == "Bash":
            cmd = _extract_command(event)
            if cmd:
                blocked, reason = guard.check_bash(cmd)
                if blocked:
                    audit.append(
                        hook="pre_tool_use",
                        event="block",
                        tool=tool,
                        categories=[],
                        count=0,
                        reason=reason,
                        target=cmd[:120],
                        cli=cli,
                    )
                    block(f"bash command blocked: {reason}")
        else:
            path = _extract_path(event)
            if path:
                blocked, reason = guard.check_path(path)
                if blocked:
                    audit.append(
                        hook="pre_tool_use",
                        event="block",
                        tool=tool,
                        categories=[],
                        count=0,
                        reason=reason,
                        target=path,
                        cli=cli,
                    )
                    block(f"path {path!r} blocked: {reason}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
