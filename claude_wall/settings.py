"""Manage claude-wall hook registration across Claude Code, Codex CLI, and Gemini CLI.

Operations:

- `install(cli)` — register hooks for the given CLI adapter, backing up first
- `uninstall(cli)` — strip only entries we own
- `status(cli)` — report whether each hook is registered
- `detect_cli()` — return list of installed CLI names

Hook ownership is tracked by command prefix: anything starting with
`python -m claude_wall.hooks.` or `python3 -m claude_wall.hooks.` is ours;
everything else (user-defined hooks, hooks from other tools) is left alone.

Supported CLIs
--------------
claude  — Claude Code  (~/.claude/settings.json)
codex   — OpenAI Codex CLI  (~/.codex/hooks.json)
gemini  — Gemini CLI  (~/.gemini/settings.json)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from copy import deepcopy
from pathlib import Path

# ---------------------------------------------------------------------------
# CLI adapter definitions
# ---------------------------------------------------------------------------

# Each adapter describes where settings live and which event names to use.
# timeout is in seconds for Claude/Codex, milliseconds for Gemini.
CLI_ADAPTERS: dict[str, dict] = {
    "claude": {
        "label": "Claude Code",
        "binary": "claude",
        "settings_env": "CLAUDE_WALL_SETTINGS_PATH",
        "default_settings": "~/.claude/settings.json",
        "windows_settings": "~/AppData/Roaming/Claude/settings.json",
        "hooks_key": "hooks",
        "pre_event": "PreToolUse",
        "post_event": "PostToolUse",
        "prompt_event": "UserPromptSubmit",
        "pre_matcher": "Bash|Read|Edit|Write|WebFetch",
        "post_matcher": "Bash|Read|WebFetch",
        "prompt_matcher": "*",
        "timeout": 5,
        "timeout_unit": "seconds",
    },
    "codex": {
        "label": "OpenAI Codex CLI",
        "binary": "codex",
        "settings_env": None,
        "default_settings": "~/.codex/hooks.json",
        "windows_settings": "~/AppData/Roaming/Codex/hooks.json",
        "hooks_key": "hooks",
        "pre_event": "PreToolUse",
        "post_event": "PostToolUse",
        "prompt_event": "UserPromptSubmit",
        "pre_matcher": "Bash|Edit|apply_patch|Write",
        "post_matcher": "Bash|WebFetch",
        "prompt_matcher": "*",
        "timeout": 5,
        "timeout_unit": "seconds",
    },
    "gemini": {
        "label": "Gemini CLI",
        "binary": "gemini",
        "settings_env": None,
        "default_settings": "~/.gemini/settings.json",
        "windows_settings": "~/AppData/Roaming/Gemini/settings.json",
        "hooks_key": "hooks",
        "pre_event": "BeforeTool",
        "post_event": "AfterTool",
        "prompt_event": None,  # no UserPromptSubmit equivalent
        "pre_matcher": "run_shell_command|run_code|write_file|replace_in_file|read_file",
        "post_matcher": "run_shell_command|run_code|read_file|fetch_webpage",
        "prompt_matcher": None,
        "timeout": 5000,  # milliseconds
        "timeout_unit": "milliseconds",
    },
}

SUPPORTED_CLIS = list(CLI_ADAPTERS.keys())


def _hook_command(module: str) -> str:
    # Use the exact Python that's running claude-wall (pipx venv, conda env, etc.)
    # so the hook process can always import claude_wall regardless of PATH.
    return f"{sys.executable} -m {module}"


OUR_COMMAND_PREFIXES = (
    "python -m claude_wall.hooks.",
    "python3 -m claude_wall.hooks.",
    f"{sys.executable} -m claude_wall.hooks.",
)


def _is_ours(command: str) -> bool:
    return any(command.startswith(p) for p in OUR_COMMAND_PREFIXES)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def settings_path(cli: str = "claude") -> Path:
    adapter = CLI_ADAPTERS[cli]
    env_key = adapter.get("settings_env")
    if env_key:
        override = os.environ.get(env_key)
        if override:
            return Path(override)
    raw = adapter["windows_settings"] if sys.platform == "win32" else adapter["default_settings"]
    return Path(raw).expanduser()


def backup_path(cli: str = "claude") -> Path:
    p = settings_path(cli)
    return p.with_suffix(p.suffix + ".claude-wall.bak")


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Hook entry builders
# ---------------------------------------------------------------------------

def _hooks_spec(cli: str) -> list[dict]:
    a = CLI_ADAPTERS[cli]
    specs = []
    if a["post_event"]:
        specs.append({
            "bucket": a["post_event"],
            "matcher": a["post_matcher"],
            "module": "claude_wall.hooks.post_tool_use",
            "timeout": a["timeout"],
        })
    if a["pre_event"]:
        specs.append({
            "bucket": a["pre_event"],
            "matcher": a["pre_matcher"],
            "module": "claude_wall.hooks.pre_tool_use",
            "timeout": a["timeout"],
        })
    if a["prompt_event"]:
        specs.append({
            "bucket": a["prompt_event"],
            "matcher": a["prompt_matcher"],
            "module": "claude_wall.hooks.user_prompt_submit",
            "timeout": a["timeout"],
        })
    return specs


def _build_hook_entry(spec: dict) -> dict:
    entry: dict = {
        "matcher": spec["matcher"],
        "hooks": [
            {
                "type": "command",
                "command": _hook_command(spec["module"]),
                "timeout": spec["timeout"],
            }
        ],
    }
    return entry


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


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_cli() -> list[str]:
    """Return names of installed CLIs (binary found in PATH)."""
    found = []
    for name, adapter in CLI_ADAPTERS.items():
        if shutil.which(adapter["binary"]):
            found.append(name)
    return found


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install(cli: str = "claude", *, dry_run: bool = False, yes: bool = False) -> dict:
    """Register claude-wall hooks for `cli`. Returns a report dict."""
    if cli not in CLI_ADAPTERS:
        raise ValueError(f"unknown CLI {cli!r}, choose from {SUPPORTED_CLIS}")
    path = settings_path(cli)
    data = _load(path)
    before = deepcopy(data)

    hooks_root = data.setdefault(CLI_ADAPTERS[cli]["hooks_key"], {})
    specs = _hooks_spec(cli)
    added = 0
    for spec in specs:
        bucket = hooks_root.setdefault(spec["bucket"], [])
        stripped = _strip_ours(bucket)
        stripped.append(_build_hook_entry(spec))
        hooks_root[spec["bucket"]] = stripped
        added += 1

    report = {
        "cli": cli,
        "added": added,
        "dry_run": dry_run,
        "path": str(path),
        "diff_summary": f"+{added} claude-wall hook entries for {cli}",
        "before": before,
        "after": data,
    }
    if dry_run:
        return report

    if path.exists():
        backup_path(cli).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return report


def uninstall(cli: str = "claude", *, yes: bool = False) -> dict:
    if cli not in CLI_ADAPTERS:
        raise ValueError(f"unknown CLI {cli!r}")
    path = settings_path(cli)
    data = _load(path)
    hooks_root = data.get(CLI_ADAPTERS[cli]["hooks_key"], {})
    removed = 0
    for spec in _hooks_spec(cli):
        bucket = hooks_root.get(spec["bucket"])
        if not bucket:
            continue
        original_n = sum(len(e.get("hooks", [])) for e in bucket)
        hooks_root[spec["bucket"]] = _strip_ours(bucket)
        new_n = sum(len(e.get("hooks", [])) for e in hooks_root[spec["bucket"]])
        removed += original_n - new_n
    if path.exists():
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"cli": cli, "removed": removed, "path": str(path)}


def status(cli: str = "claude") -> dict:
    if cli not in CLI_ADAPTERS:
        raise ValueError(f"unknown CLI {cli!r}")
    path = settings_path(cli)
    data = _load(path)
    hooks_root = data.get(CLI_ADAPTERS[cli]["hooks_key"], {})
    installed_buckets: list[str] = []
    for spec in _hooks_spec(cli):
        bucket = hooks_root.get(spec["bucket"], [])
        for entry in bucket:
            for h in entry.get("hooks", []):
                if _is_ours(h.get("command", "")):
                    installed_buckets.append(spec["bucket"])
                    break
            if spec["bucket"] in installed_buckets:
                break
    return {
        "cli": cli,
        "label": CLI_ADAPTERS[cli]["label"],
        "installed": len(installed_buckets) == len(_hooks_spec(cli)),
        "hooks": installed_buckets,
        "path": str(path),
    }
