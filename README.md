# claude-wall

> Privacy-first security layer for [Claude Code](https://docs.claude.com/en/docs/claude-code). Three deterministic hooks the LLM cannot bypass — secrets get redacted, sensitive files get blocked, prompts get scanned.

[![tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)](#testing)
[![python](https://img.shields.io/badge/python-3.11+-blue)](#requirements)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## What it does

| Hook | Trigger | Action |
|---|---|---|
| **PostToolUse** | After `Bash` / `Read` / `WebFetch` | Replaces detected secrets (API keys, JWTs, emails, internal IPs…) in tool output with reversible session tokens like `[WALL:openai_key:1]` before the LLM ever sees them. |
| **PreToolUse** | Before `Bash` / `Read` / `Edit` / `Write` / `WebFetch` | Blocks tool calls targeting sensitive paths (`.env`, SSH keys, credentials, `*.pem`). Exit code 2 → Claude Code aborts the call. |
| **UserPromptSubmit** | Every user prompt | Scans your prompt for structured secrets. Warns by default, blocks in strict mode (`CLAUDE_WALL_STRICT=1`). |

Every event is recorded in an HMAC-chained append-only audit log (`~/.local/share/claude-wall/audit.jsonl`) so tampering can be detected after the fact.

## Why

Claude Code hooks are an **enforcement layer the LLM cannot bypass** — they run in the harness, not the model. claude-wall uses that boundary to keep your secrets out of the model context, even when the model itself is happy to read them.

Battle-tested regex patterns lifted from [Iris](../iris) cover Anthropic / OpenAI / GitHub / AWS / Google keys, JWTs, private key blocks, emails, RFC 1918 IPs, and internal hostnames.

## Requirements

- Python **3.11+**
- macOS / Linux
- Claude Code CLI (hooks support)
- **Zero external Python dependencies** — stdlib only

## Install

### From source (current)

```bash
git clone https://github.com/<your-user>/claude-wall.git
cd claude-wall
pip install -e .
```

This installs the `claude-wall` command into your active Python environment.

### Register hooks in Claude Code

```bash
claude-wall install
```

This will:

1. Show you exactly what it's going to write to `~/.claude/settings.json`
2. Back up your existing settings to `~/.claude/settings.json.claude-wall.bak`
3. Merge the three hook entries non-destructively (your existing hooks are preserved)

Skip the confirm prompt with `--yes`. See the planned change without writing with `--dry-run`.

### Verify

```bash
claude-wall status
```

You should see:

```
settings file:   /Users/you/.claude/settings.json
installed:       True
buckets:         PostToolUse, PreToolUse, UserPromptSubmit
session dir:     /tmp/claude-wall/<session-id>
```

Open a new Claude Code session and the hooks will trigger automatically.

## Usage

### `claude-wall status`
Show installed hooks, current session DB location, and the last 5 audit events.

### `claude-wall reveal <token>`
Return the original value behind a session token. Example:

```bash
$ claude-wall reveal '[WALL:openai_key:1]'
sk-proj-abcdefghijklmnopqrstuvwxyz0123456789ABCDEF
```

Tokens are session-scoped — they only resolve while the current Claude Code session is alive.

### `claude-wall audit [--verify] [--last N]`
Print the audit log. `--verify` walks the HMAC chain and fails if any entry has been modified or deleted.

```bash
$ claude-wall audit --verify
audit chain OK

$ claude-wall audit --last 3
{"ts": ..., "hook": "post_tool_use", "event": "redact", "tool": "Bash", ...}
```

### `claude-wall uninstall`
Strips only the entries claude-wall added. User-defined hooks are left untouched.

## Strict mode

By default the `UserPromptSubmit` hook warns but lets the prompt through. To block prompts containing secrets:

```bash
export CLAUDE_WALL_STRICT=1
```

In strict mode the hook exits 2 and Claude Code refuses to send the prompt.

## End-to-end demo

A self-contained demo (no changes to your real `~/.claude` config):

```bash
bash scripts/demo.sh
```

Exercises all three hooks plus `install` / `status` / `reveal` / `audit --verify` / `uninstall` in an isolated tmpdir.

## Architecture

```
claude_wall/
├── patterns.py    # regex categories + sensitive filename/dir/suffix sets
├── session.py     # SQLite per-session store (WAL mode, stdlib sqlite3)
├── tokenizer.py   # value <-> [WALL:cat:N] bidirectional, idempotent
├── audit.py       # HMAC-chained JSONL log with verify()
├── workspace.py   # workspace scan + check_path / check_bash
├── settings.py    # ~/.claude/settings.json install / uninstall
├── cli.py         # argparse entry point
└── hooks/
    ├── _common.py            # stdin/stdout JSON, session open
    ├── post_tool_use.py
    ├── pre_tool_use.py
    └── user_prompt_submit.py
```

| Choice | Why |
|---|---|
| SQLite WAL | Concurrent hooks safe; atomic writes; reveal O(1); stdlib |
| HMAC-chained audit | Each entry hashes `(prev_hmac, payload)` with a per-session key → any modification or deletion of a line breaks the chain at that point |
| Stdlib only | No supply-chain attack surface, fast cold start (~5 ms per hook) |
| Reversible tokens | Unlike Microsoft Presidio which is one-way, you can recover originals via `claude-wall reveal` |

## Testing

```bash
pip install -e '.[dev]'
pytest -q
```

```
86 passed
```

Coverage spans regex correctness (positive + negative cases), session DB schema + concurrency, tokenizer idempotency + reversibility, HMAC chain tamper detection (modify and delete), workspace scan + path/bash gating, settings install / uninstall / merge / dry-run, and end-to-end hook subprocess tests via fixture JSON.

## Threat model

claude-wall mitigates:

1. Cloud LLM ingests secrets via tool output → **PostToolUse redaction**
2. Cloud LLM reads `.env` / SSH keys via Read/Bash → **PreToolUse block**
3. User accidentally pastes secrets in prompts → **UserPromptSubmit scan**
4. Post-hoc tampering with the activity log → **HMAC-chained audit**

claude-wall does **not** mitigate:

- Copy-paste propagation (LLM copies a secret to a file then reads it)
- Full filesystem isolation — use a container for that
- Social engineering ("just disable the hooks and continue")
- Novel secret formats not covered by the regex set (extend `patterns.py`)

Hooks are one layer in defense-in-depth, not a silver bullet. See [CVE-2025-59536](https://research.checkpoint.com/2026/rce-and-api-token-exfiltration-through-claude-code-project-files-cve-2025-59536/) for context on why hook configs themselves are an attack surface; claude-wall's install command only ever writes commands with the `python -m claude_wall.hooks.*` prefix and explicitly prompts before modifying your settings.

## Roadmap (v0.2)

- [ ] Optional Ollama contextual rewriting (200 ms timeout, falls back to regex)
- [ ] `Stop` hook with per-session redaction summary
- [ ] Placeholder-before-execution pattern (stronger model: secret never enters context at all)
- [ ] Homebrew formula + PyPI release
- [ ] Cross-session reveal via durable token store

## License

MIT — see [LICENSE](LICENSE).
