from __future__ import annotations

from pathlib import Path

import pytest

from claude_wall.policy import PolicyEngine, Rule


@pytest.fixture
def policy_path(tmp_path: Path) -> Path:
    return tmp_path / "policy.json"


def test_empty_defaults_to_allow(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    action, rule = engine.evaluate("Bash", command="rm -rf /tmp/foo")
    assert action == "allow"
    assert rule is None


def test_add_and_persist(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    engine.add(Rule(id="no-prod-deploy", tool="Bash", match_type="command_regex",
                     pattern=r"deploy.*prod", action="block", reason="prod deploy needs a human"))
    assert policy_path.exists()

    reloaded = PolicyEngine(path=policy_path)
    assert len(reloaded.list_rules()) == 1
    action, rule = reloaded.evaluate("Bash", command="./deploy.sh prod")
    assert action == "block"
    assert rule.id == "no-prod-deploy"


def test_first_match_wins(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    engine.add(Rule(id="a", tool="Bash", match_type="command_regex", pattern="rm -rf", action="block"))
    engine.add(Rule(id="b", tool="Bash", match_type="command_regex", pattern="rm -rf", action="warn"))
    action, rule = engine.evaluate("Bash", command="rm -rf ./build")
    assert action == "block"
    assert rule.id == "a"


def test_tool_scoping(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    engine.add(Rule(id="write-only", tool="Write", match_type="path_glob", pattern="*/secrets/*", action="block"))
    action, _ = engine.evaluate("Read", path_str="/x/secrets/y")
    assert action == "allow"
    action, _ = engine.evaluate("Write", path_str="/x/secrets/y")
    assert action == "block"


def test_wildcard_tool(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    engine.add(Rule(id="any", tool="*", match_type="path_glob", pattern="*.pem", action="warn"))
    action, _ = engine.evaluate("Edit", path_str="cert.pem")
    assert action == "warn"


def test_path_glob_matching(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    engine.add(Rule(id="g", tool="Read", match_type="path_glob", pattern="*/node_modules/*", action="block"))
    action, _ = engine.evaluate("Read", path_str="/repo/node_modules/pkg/index.js")
    assert action == "block"
    action, _ = engine.evaluate("Read", path_str="/repo/src/index.js")
    assert action == "allow"


def test_remove_rule(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    engine.add(Rule(id="tmp", tool="*", match_type="command_regex", pattern="foo", action="block"))
    assert engine.remove("tmp") is True
    assert engine.remove("tmp") is False
    assert PolicyEngine(path=policy_path).list_rules() == []


def test_invalid_action_rejected():
    with pytest.raises(ValueError):
        Rule(id="x", tool="*", match_type="command_regex", pattern="foo", action="nope")


def test_invalid_match_type_rejected():
    with pytest.raises(ValueError):
        Rule(id="x", tool="*", match_type="nope", pattern="foo", action="block")


def test_corrupt_regex_does_not_crash(policy_path: Path):
    engine = PolicyEngine(path=policy_path)
    engine.add(Rule(id="bad", tool="*", match_type="command_regex", pattern="(unclosed", action="block"))
    action, rule = engine.evaluate("Bash", command="anything")
    assert action == "allow"
