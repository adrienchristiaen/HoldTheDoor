"""Manage claude-wall hook registration in `~/.claude/settings.json`.

Operations:

- `install()` — register the three hooks, backing up the original file first
- `uninstall()` — strip only entries we own (identified by command prefix)
- `status()` — report whether each hook is registered

Hook ownership is tracked by command prefix: anything starting with
`python -m claude_wall.hooks.` or `python3 -m claude_wall.hooks.` is ours;
everything else (user-defined hooks, hooks from other tools) is left alone.
"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

OUR_COMMAND_PREFIXES = (
    "python -m claude_wall.hooks.",
    "python3 -m claude_wall.hooks.",
    f"{sys.executable} -m claude_wall.hooks.",
)

HOOKS_SPEC = [
    {
        "bucket": "PostToolUse",
        "matcher": "Bash|Read|WebFetch",
        "module": "claude_wall.hooks.post_tool_use",
        "timeout": 5,
    },
    {
        "bucket": "PreToolUse",
        "matcher": "Bash|Read|Edit|Write|WebFetch",
        "module": "claude_wall.hooks.pre_tool_use",
        "timeout": 5,
    },
    {
        "bucket": "UserPromptSubmit",
        "matcher": "*",
        "module": "claude_wall.hooks.user_prompt_submit",
        "timeout": 5,
    },
]


def settings_path() -> Path:
    override = os.environ.get("CLAUDE_WALL_SETTINGS_PATH")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "settings.json"


def backup_path() -> Path:
    p = settings_path()
    return p.with_suffix(p.suffix + ".claude-wall.bak")


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def _is_ours(command: str) -> bool:
    return any(command.startswith(p) for p in OUR_COMMAND_PREFIXES)


def _hook_command(module: str) -> str:
    py = "python3" if sys.platform == "darwin" else "python"
    return f"{py} -m {module}"


def _build_hook_entry(spec: dict) -> dict:
    return {
        "matcher": spec["matcher"],
        "hooks": [
            {
                "type": "command",
                "command": _hook_command(spec["module"]),
                "timeout": spec["timeout"],
            }
        ],
    }


def _strip_ours(bucket_entries: list) -> list:
    cleaned: list = []
    for entry in bucket_entries:
        hooks = entry.get("hooks", [])
        kept = [h for h in hooks if not _is_ours(h.get("command", ""))]
        if kept:
            new_entry = dict(entry)
            new_entry["hooks"] = kept
            cleaned.append(new_entry)
        elif not hooks:
            cleaned.append(entry)
    return cleaned


def install(*, dry_run: bool = False, yes: bool = False) -> dict:
    """Register the three hooks. Returns a report dict."""
    path = settings_path()
    data = _load(path)
    before = deepcopy(data)

    hooks = data.setdefault("hooks", {})
    added = 0
    for spec in HOOKS_SPEC:
        bucket = hooks.setdefault(spec["bucket"], [])
        stripped = _strip_ours(bucket)
        stripped.append(_build_hook_entry(spec))
        hooks[spec["bucket"]] = stripped
        added += 1

    report = {
        "added": added,
        "dry_run": dry_run,
        "path": str(path),
        "diff_summary": f"+{added} claude-wall hook entries",
        "before": before,
        "after": data,
    }
    if dry_run:
        return report

    if path.exists():
        backup_path().write_text(path.read_text())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return report


def uninstall(*, yes: bool = False) -> dict:
    path = settings_path()
    data = _load(path)
    hooks = data.get("hooks", {})
    removed = 0
    for spec in HOOKS_SPEC:
        bucket = hooks.get(spec["bucket"])
        if not bucket:
            continue
        original_n = sum(len(e.get("hooks", [])) for e in bucket)
        hooks[spec["bucket"]] = _strip_ours(bucket)
        new_n = sum(len(e.get("hooks", [])) for e in hooks[spec["bucket"]])
        removed += original_n - new_n
    if path.exists():
        path.write_text(json.dumps(data, indent=2))
    return {"removed": removed, "path": str(path)}


def status() -> dict:
    path = settings_path()
    data = _load(path)
    hooks = data.get("hooks", {})
    installed_buckets: list[str] = []
    for spec in HOOKS_SPEC:
        bucket = hooks.get(spec["bucket"], [])
        for entry in bucket:
            for h in entry.get("hooks", []):
                if _is_ours(h.get("command", "")):
                    installed_buckets.append(spec["bucket"])
                    break
            if spec["bucket"] in installed_buckets:
                break
    return {
        "installed": len(installed_buckets) == len(HOOKS_SPEC),
        "hooks": installed_buckets,
        "path": str(path),
    }
