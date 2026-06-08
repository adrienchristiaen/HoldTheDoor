from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_wall import settings as S


@pytest.fixture
def settings_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "settings.json"
    monkeypatch.setenv("CLAUDE_WALL_SETTINGS_PATH", str(p))
    return p


class TestInstallFresh:
    def test_creates_file_if_missing(self, settings_path: Path):
        report = S.install(yes=True)
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]
        assert "PostToolUse" in hooks
        assert "PreToolUse" in hooks
        assert "UserPromptSubmit" in hooks
        assert report["added"] == 3

    def test_dry_run_does_not_write(self, settings_path: Path):
        report = S.install(dry_run=True, yes=True)
        assert not settings_path.exists()
        assert report["dry_run"] is True
        assert report["added"] == 3

    def test_commands_use_python_module(self, settings_path: Path):
        S.install(yes=True)
        data = json.loads(settings_path.read_text())
        cmds = []
        for hook_list in data["hooks"].values():
            for entry in hook_list:
                for h in entry.get("hooks", []):
                    cmds.append(h["command"])
        assert all("claude_wall.hooks." in c for c in cmds)


class TestInstallExisting:
    def test_preserves_user_hooks(self, settings_path: Path):
        user_hook = {
            "type": "command",
            "command": "echo user-defined-hook",
            "timeout": 10,
        }
        existing = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Edit", "hooks": [user_hook]},
                ]
            },
            "theme": "dark",
        }
        settings_path.write_text(json.dumps(existing))
        S.install(yes=True)
        data = json.loads(settings_path.read_text())
        assert data["theme"] == "dark"
        post = data["hooks"]["PostToolUse"]
        all_hooks = [h for entry in post for h in entry.get("hooks", [])]
        assert any(h["command"] == "echo user-defined-hook" for h in all_hooks)
        assert any("claude_wall.hooks.post_tool_use" in h["command"] for h in all_hooks)

    def test_idempotent(self, settings_path: Path):
        S.install(yes=True)
        first = settings_path.read_text()
        S.install(yes=True)
        second = settings_path.read_text()
        data1 = json.loads(first)
        data2 = json.loads(second)
        assert data1 == data2

    def test_creates_backup(self, settings_path: Path):
        settings_path.write_text(json.dumps({"theme": "dark"}))
        S.install(yes=True)
        backup = settings_path.with_suffix(".json.claude-wall.bak")
        assert backup.exists()
        assert json.loads(backup.read_text()) == {"theme": "dark"}


class TestUninstall:
    def test_removes_only_our_hooks(self, settings_path: Path):
        user_hook = {"type": "command", "command": "echo me", "timeout": 5}
        settings_path.write_text(json.dumps({
            "hooks": {"PostToolUse": [{"matcher": "Edit", "hooks": [user_hook]}]},
            "theme": "dark",
        }))
        S.install(yes=True)
        S.uninstall(yes=True)
        data = json.loads(settings_path.read_text())
        assert data["theme"] == "dark"
        post = data["hooks"]["PostToolUse"]
        all_hooks = [h for entry in post for h in entry.get("hooks", [])]
        assert any(h["command"] == "echo me" for h in all_hooks)
        assert not any("claude_wall" in h["command"] for h in all_hooks)

    def test_removes_empty_buckets(self, settings_path: Path):
        S.install(yes=True)
        S.uninstall(yes=True)
        data = json.loads(settings_path.read_text())
        # After uninstall on a fresh install, all buckets we added should be empty
        for bucket in ("PostToolUse", "PreToolUse", "UserPromptSubmit"):
            assert data.get("hooks", {}).get(bucket, []) == []


class TestStatus:
    def test_reports_installed(self, settings_path: Path):
        S.install(yes=True)
        status = S.status()
        assert status["installed"] is True
        assert set(status["hooks"]) == {"PostToolUse", "PreToolUse", "UserPromptSubmit"}

    def test_reports_not_installed(self, settings_path: Path):
        status = S.status()
        assert status["installed"] is False
        assert status["hooks"] == []
