from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


FIX = Path(__file__).parent.parent / "fixtures"


def _run_hook(module: str, payload: dict, env: dict[str, str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", module],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        cwd=str(cwd) if cwd else None,
        timeout=10,
    )
    return proc.returncode, proc.stdout, proc.stderr


@pytest.fixture
def hook_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".env").write_text("SECRET=1\n")
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("x = 1\n")
    return ({
        "CLAUDE_SESSION_ID": "hook-test",
        "CLAUDE_WALL_SESSION_ROOT": str(tmp_path / "sess"),
        "CLAUDE_WALL_AUDIT_DIR": str(tmp_path / "audit"),
        "PYTHONPATH": str(Path(__file__).parent.parent.parent),
    }, workspace)


class TestPreToolUse:
    def test_blocks_env_read(self, hook_env):
        env, ws = hook_env
        payload = json.loads((FIX / "pre_read_env.json").read_text())
        rc, out, err = _run_hook("claude_wall.hooks.pre_tool_use", payload, env, cwd=ws)
        assert rc == 2, f"expected exit 2, got {rc}: stderr={err}"
        assert ".env" in err or "sensitive" in err.lower()

    def test_allows_safe_read(self, hook_env):
        env, ws = hook_env
        payload = json.loads((FIX / "pre_read_safe.json").read_text())
        rc, _, err = _run_hook("claude_wall.hooks.pre_tool_use", payload, env, cwd=ws)
        assert rc == 0, f"unexpected block: {err}"

    def test_blocks_bash_cat_env(self, hook_env):
        env, ws = hook_env
        payload = {
            "session_id": "test",
            "tool_name": "Bash",
            "tool_input": {"command": "cat .env"},
        }
        rc, _, err = _run_hook("claude_wall.hooks.pre_tool_use", payload, env, cwd=ws)
        assert rc == 2
        assert "sensitive" in err.lower() or ".env" in err

    def test_allows_safe_bash(self, hook_env):
        env, ws = hook_env
        payload = {
            "session_id": "test",
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        }
        rc, _, _ = _run_hook("claude_wall.hooks.pre_tool_use", payload, env, cwd=ws)
        assert rc == 0
