"""User-defined tool-call policy engine.

Complements `WorkspaceGuard`'s built-in sensitive-path checks with custom
rules a user can add without touching code: block/warn on a bash command
regex or a path glob, per tool. Rules are stored as JSON at
`~/.local/share/claude-wall/policy.json`, evaluated in file order, first
match wins. No match => allow (WorkspaceGuard's built-ins still apply
independently and cannot be weakened by a policy rule).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

VALID_ACTIONS = {"block", "warn", "allow"}
VALID_MATCH_TYPES = {"command_regex", "path_glob"}


def default_policy_path() -> Path:
    override = os.environ.get("CLAUDE_WALL_POLICY_PATH")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "claude-wall" / "policy.json"


@dataclass
class Rule:
    id: str
    tool: str  # "*" or "Bash"/"Read"/"Write"/... ("|"-separated for several)
    match_type: str  # "command_regex" | "path_glob"
    pattern: str
    action: str  # "block" | "warn" | "allow"
    reason: str = ""

    def __post_init__(self) -> None:
        if self.match_type not in VALID_MATCH_TYPES:
            raise ValueError(f"invalid match_type {self.match_type!r}, choose from {VALID_MATCH_TYPES}")
        if self.action not in VALID_ACTIONS:
            raise ValueError(f"invalid action {self.action!r}, choose from {VALID_ACTIONS}")

    def tools(self) -> list[str]:
        return ["*"] if self.tool == "*" else [t.strip() for t in self.tool.split("|")]

    def applies_to(self, tool: str) -> bool:
        ts = self.tools()
        return "*" in ts or tool in ts

    def matches(self, target: str) -> bool:
        if self.match_type == "command_regex":
            try:
                return re.search(self.pattern, target) is not None
            except re.error:
                return False
        return fnmatch.fnmatch(target, self.pattern)


def _load_raw(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_raw(path: Path, rules: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rules, indent=2), encoding="utf-8")


class PolicyEngine:
    """Loads and evaluates user-defined rules against tool-call events."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_policy_path()
        self.rules: list[Rule] = [Rule(**r) for r in _load_raw(self.path)]

    def evaluate(
        self, tool: str, *, command: str | None = None, path_str: str | None = None
    ) -> tuple[str, Rule | None]:
        """Return (action, rule): action is 'block', 'warn', or 'allow'."""
        for rule in self.rules:
            if not rule.applies_to(tool):
                continue
            target = command if rule.match_type == "command_regex" else path_str
            if not target:
                continue
            if rule.matches(target):
                return rule.action, rule
        return "allow", None

    def add(self, rule: Rule) -> None:
        raw = _load_raw(self.path)
        raw.append(asdict(rule))
        _save_raw(self.path, raw)
        self.rules.append(rule)

    def remove(self, rule_id: str) -> bool:
        raw = _load_raw(self.path)
        new_raw = [r for r in raw if r.get("id") != rule_id]
        removed = len(new_raw) != len(raw)
        if removed:
            _save_raw(self.path, new_raw)
            self.rules = [Rule(**r) for r in new_raw]
        return removed

    def list_rules(self) -> list[Rule]:
        return list(self.rules)
