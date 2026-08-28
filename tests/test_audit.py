from __future__ import annotations

import json
from pathlib import Path

import pytest

from holdthedoor.audit import AuditLog


@pytest.fixture
def log(tmp_path: Path) -> AuditLog:
    return AuditLog(path=tmp_path / "audit.jsonl", hmac_key=b"test-key")


class TestAppendAndRead:
    def test_append_creates_file(self, log: AuditLog):
        log.append(hook="post_tool_use", event="redact", tool="Bash", categories=["email"], count=1)
        assert log.path.exists()
        entries = log.read_all()
        assert len(entries) == 1
        assert entries[0]["hook"] == "post_tool_use"
        assert entries[0]["categories"] == ["email"]

    def test_multiple_entries(self, log: AuditLog):
        log.append(hook="post_tool_use", event="redact", tool="Bash", categories=["email"], count=1)
        log.append(hook="pre_tool_use", event="block", tool="Read", categories=[], count=0, reason="sensitive path .env")
        log.append(hook="user_prompt_submit", event="warn", tool=None, categories=["openai_key"], count=1)
        entries = log.read_all()
        assert len(entries) == 3
        assert entries[1]["event"] == "block"
        assert entries[2]["categories"] == ["openai_key"]

    def test_read_last_n(self, log: AuditLog):
        for i in range(10):
            log.append(hook="post_tool_use", event="redact", tool="Bash", categories=[], count=i)
        last = log.read_last(3)
        assert len(last) == 3
        assert [e["count"] for e in last] == [7, 8, 9]


class TestHmacChain:
    def test_first_entry_has_genesis_prev(self, log: AuditLog):
        log.append(hook="post_tool_use", event="redact", tool="Bash", categories=[], count=0)
        entries = log.read_all()
        assert entries[0]["prev_hmac"] == ""
        assert entries[0]["hmac"] != ""

    def test_chain_links(self, log: AuditLog):
        log.append(hook="post_tool_use", event="redact", tool="Bash", categories=[], count=0)
        log.append(hook="post_tool_use", event="redact", tool="Bash", categories=[], count=1)
        entries = log.read_all()
        assert entries[1]["prev_hmac"] == entries[0]["hmac"]

    def test_verify_clean_chain(self, log: AuditLog):
        for i in range(5):
            log.append(hook="post_tool_use", event="redact", tool="Bash", categories=[], count=i)
        assert log.verify() == (True, None)

    def test_verify_detects_tampering(self, log: AuditLog):
        for i in range(3):
            log.append(hook="post_tool_use", event="redact", tool="Bash", categories=[], count=i)
        lines = log.path.read_text().splitlines()
        tampered = json.loads(lines[1])
        tampered["count"] = 999
        lines[1] = json.dumps(tampered)
        log.path.write_text("\n".join(lines) + "\n")
        ok, msg = log.verify()
        assert ok is False
        assert msg is not None and "line 2" in msg

    def test_verify_detects_deletion(self, log: AuditLog):
        for i in range(3):
            log.append(hook="post_tool_use", event="redact", tool="Bash", categories=[], count=i)
        lines = log.path.read_text().splitlines()
        del lines[1]
        log.path.write_text("\n".join(lines) + "\n")
        ok, _ = log.verify()
        assert ok is False
