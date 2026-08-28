# claude-wall

> Privacy-first security layer for AI coding CLIs. Deterministic hooks the LLM cannot bypass — secrets get redacted, sensitive files get blocked, prompts get scanned, and every tool call can be governed by rules you define.

[![tests](https://img.shields.io/badge/tests-96%20passed-brightgreen)](#testing)
[![python](https://img.shields.io/badge/python-3.11+-blue)](#requirements)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Read in:** [Français](docs/README.fr.md) · [中文](docs/README.zh.md) · [日本語](docs/README.ja.md)

---

## Table of contents

- [Why](#why)
- [Supported CLIs](#supported-clis)
- [What it does](#what-it-does)
- [Tool-call policy engine](#tool-call-policy-engine)
- [Requirements](#requirements)
- [Installation](#installation)
- [Verify installation](#verify-installation)
- [Usage](#usage)
- [Strict mode](#strict-mode)
- [End-to-end demo](#end-to-end-demo)
- [Architecture](#architecture)
- [Detected secret categories](#detected-secret-categories)
- [Testing](#testing)
- [Threat model](#threat-model)
- [Roadmap](#roadmap-v02)
- [License](#license)

---

## Why

AI coding agents read your filesystem, run shell commands, and fetch web pages — then feed the results straight back into an LLM context. That's how secrets leak: a `cat .env` in an agent's own reasoning, a stray API key in a curl response, a credential pasted by mistake into a prompt. Prompt-based instructions ("don't read secrets") are not a security boundary — the LLM can be talked out of them. claude-wall sits **outside** the model, as CLI hooks that run in plain Python before/after every tool call. The LLM cannot see, disable, or negotiate with a hook — it either lets the call through or it doesn't.

---

## Supported CLIs

| CLI | Hook support | Notes |
|---|---|---|
| **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** | Full (3 hooks) | `PostToolUse`, `PreToolUse`, `UserPromptSubmit` |
| **[OpenAI Codex CLI](https://openai.com/codex)** | Full (3 hooks) | Same hook format as Claude Code |
| **[Gemini CLI](https://gemini.google.com/cli)** | Partial (2 hooks) | `BeforeTool`, `AfterTool` — no prompt hook |

---

## What it does

| Hook | Trigger | Action |
|---|---|---|
| **PostToolUse / AfterTool** | After `Bash` / `Read` / `WebFetch` (or CLI equivalents) | Replaces detected secrets in tool output with reversible session tokens like `[WALL:openai_key:1]` before the LLM sees them. |
| **PreToolUse / BeforeTool** | Before any file/shell tool call | Blocks calls targeting sensitive paths (`.env`, SSH keys, credentials, `*.pem`) **and** evaluates your custom [policy rules](#tool-call-policy-engine). Exit code 2 = CLI aborts the call. |
| **UserPromptSubmit** | Every user prompt (Claude Code + Codex only) | Scans your prompt for structured secrets. Warns by default, blocks in strict mode. |

Every event — redaction, block, warning, policy match — is recorded in an HMAC-chained audit log (`~/.local/share/claude-wall/audit.jsonl`). Tampering with any entry breaks the chain, and `claude-wall audit --verify` proves it.

---

## Tool-call policy engine

Sensitive-path blocking (`.env`, SSH keys, …) is built in and always on. On top of that, you can define your own **allow / warn / block** rules — no code changes, no redeploy:

```bash
# Block force-pushes to any branch
claude-wall policy add --id no-force-push \
  --tool Bash --match 'push.*--force' --action block \
  --reason "force push needs a human"

# Warn (but don't block) writes under any node_modules-like path
claude-wall policy add --id watch-writes \
  --tool Write --match-type path_glob --match '*/node_modules/*' \
  --action warn

# List active rules
claude-wall policy list

# Dry-run a command against current rules — no side effects
claude-wall policy test "git push --force origin main"
# → block  (matched rule 'no-force-push': force push needs a human)

# Remove a rule
claude-wall policy remove no-force-push
```

Rules live in `~/.local/share/claude-wall/policy.json`, are evaluated in the order they were added, and the first match wins (no match → allow). Each rule is scoped to a tool (`Bash`, `Read`, `Write`, `*` for all, or `Tool1|Tool2`) and matches either:

- `command_regex` (default) — a regex tested against the shell command (`Bash` calls)
- `path_glob` — a glob tested against the file path (`Read`/`Write`/`Edit` calls)

Every match is written to the audit log as `policy_block` or `policy_warn`, alongside the built-in events, so `claude-wall audit` shows a complete picture.

This is the mechanism to reach for when the built-in checks aren't enough for your team: pin dangerous commands, restrict writes to specific paths, or require review for anything touching a directory you care about — all enforced deterministically, outside the model's control.

---

## Requirements

- Python 3.11+
- One of: Claude Code CLI, OpenAI Codex CLI, Gemini CLI
- Zero external Python dependencies — stdlib only (`sqlite3`, `hmac`, `re`, `json`)

---

## Installation

### macOS

```bash
# Install pipx if not already present
brew install pipx

# Install claude-wall
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# Register hooks (auto-detects installed CLIs)
claude-wall install
```

### Linux

```bash
# Install pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Restart terminal, then:
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# Register hooks
claude-wall install
```

### Windows (PowerShell)

```powershell
# Install pipx
pip install pipx
pipx ensurepath

# Restart terminal, then:
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# Register hooks
claude-wall install
```

> **Windows note:** Settings are written to `%APPDATA%\Claude\settings.json`,
> `%APPDATA%\Codex\hooks.json`, and `%APPDATA%\Gemini\settings.json` respectively.

### From source (development)

```bash
git clone https://github.com/adrienchristiaen/claude-wall.git
cd claude-wall
pipx install --editable .
claude-wall install
```

### Targeting a specific CLI

By default `install` auto-detects which CLIs are installed. To target explicitly:

```bash
claude-wall install --cli claude   # Claude Code only
claude-wall install --cli codex    # Codex CLI only
claude-wall install --cli gemini   # Gemini CLI only
claude-wall install --cli all      # all detected CLIs
```

Same flag works for `uninstall` and `status`.

---

## Verify installation

```bash
claude-wall status
```

Expected output:

```
[Claude Code]  ✓ installed
  /Users/you/.claude/settings.json
  hooks: PostToolUse · PreToolUse · UserPromptSubmit

SESSION  /tmp/claude-wall/<session-id>/session.db
  0 values redacted this session

RECENT EVENTS
  (none)
```

Open a new CLI session — hooks activate automatically.

---

## Usage

| Command | What it does |
|---|---|
| `claude-wall status [--cli auto\|claude\|codex\|gemini\|all]` | Installed hooks per CLI, session DB path, last 5 audit events. |
| `claude-wall reveal <token>` | Print the original value behind a session token (session-scoped — dies with the session). |
| `claude-wall audit [--verify] [--last N] [--json] [--follow]` | Print the audit log. `--verify` walks the HMAC chain. `--follow` (`-f`) tails new events live, for monitoring in a second terminal. |
| `claude-wall policy list \| add \| remove \| test` | Manage custom rules — see [policy engine](#tool-call-policy-engine). |
| `claude-wall uninstall [--cli ...] [--yes]` | Strips only claude-wall entries. Other hooks are untouched. |

```
$ claude-wall reveal '[WALL:openai_key:1]'
sk-proj-••••••••••••••••••••••••••••••••••••••

$ claude-wall audit --verify
  ✓ chain intact

$ claude-wall audit --follow
SESSION AUDIT  —  live (Ctrl-C to stop)
────────────────────────────────────────────────────────────────
  16:11:02  ✗ block  pre-tool  Read  /you/project/.env  →  filename '.env' is sensitive
```

### Emergency disable

Set `CLAUDE_WALL_DISABLED=1` to bypass all hooks (e.g., to write documentation containing example secret patterns):

```bash
export CLAUDE_WALL_DISABLED=1
# ... do your thing ...
unset CLAUDE_WALL_DISABLED
```

---

## Strict mode

By default the `UserPromptSubmit` hook warns but lets the prompt through. To block:

```bash
export CLAUDE_WALL_STRICT=1
```

---

## End-to-end demo

```bash
bash scripts/demo.sh
```

Runs in an isolated tmpdir — does not touch your real CLI config.

---

## Architecture

```
claude_wall/
├── patterns.py    # regex categories + sensitive filename/dir/suffix sets
├── session.py     # SQLite WAL per-session store
├── tokenizer.py   # value <-> [WALL:cat:N] bidirectional, idempotent
├── audit.py       # HMAC-chained JSONL log + verify()
├── workspace.py   # workspace scan + check_path / check_bash (built-in rules)
├── policy.py      # user-defined allow/warn/block rules (policy engine)
├── settings.py    # multi-CLI install / uninstall (Claude/Codex/Gemini adapters)
├── cli.py         # argparse entry point
└── hooks/
    ├── _common.py             # stdin/stdout JSON, session, tool name normalization
    ├── post_tool_use.py       # AfterTool / PostToolUse
    ├── pre_tool_use.py        # BeforeTool / PreToolUse
    └── user_prompt_submit.py  # UserPromptSubmit (Claude Code + Codex)
```

### CLI adapter mapping

| Feature | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| Post-tool event | `PostToolUse` | `PostToolUse` | `AfterTool` |
| Pre-tool event | `PreToolUse` | `PreToolUse` | `BeforeTool` |
| Prompt event | `UserPromptSubmit` | `UserPromptSubmit` | *(not available)* |
| Shell tool name | `Bash` | `Bash` | `run_shell_command` |
| File read tool | `Read` | `Read` | `read_file` |
| Web fetch tool | `WebFetch` | `WebFetch` | `fetch_webpage` |
| Timeout unit | seconds | seconds | milliseconds |

---

## Detected secret categories

| Category | Pattern |
|---|---|
| `anthropic_key` | `sk-ant-api03-…` |
| `openai_key` | `sk-proj-…` |
| `github_token` | `ghp_…`, `gho_…`, `ghs_…` |
| `aws_access_key` | `AKIA…` |
| `google_api_key` | `AIza…` |
| `jwt` | `eyJ….eyJ….` |
| `private_key_block` | `-----BEGIN … KEY-----` |
| `slack_token` | `xoxb-…` |
| `email` | `user@domain.tld` |
| `private_ip` | RFC 1918 ranges |
| `internal_hostname` | `*.internal`, `*.corp`, `*.local` |

Extend by adding entries to `claude_wall/patterns.py`. Extend blocking behavior for anything else — a command, a path, a whole category of writes — with the [policy engine](#tool-call-policy-engine) instead, no code change needed.

---

## Testing

```bash
pip install -e '.[dev]'
pytest -q   # 96 passed
```

---

## Threat model

**Mitigated:**
1. LLM reads secrets via tool output → PostToolUse/AfterTool redaction
2. LLM reads `.env` / SSH keys → PreToolUse/BeforeTool block (exit 2)
3. LLM runs a command or touches a path your team has flagged → policy engine block/warn
4. Secrets in prompts → UserPromptSubmit scan
5. Post-hoc log tampering → HMAC-chained audit

**Not mitigated:**
- Copy-paste propagation (LLM copies secret to another file)
- Full filesystem isolation (use a container)
- Novel secret formats not in `patterns.py`
- Gemini CLI prompts (no `UserPromptSubmit` equivalent)
- A user with local write access editing `policy.json` or the hooks themselves — this protects against the *LLM* bypassing controls, not against a malicious local operator

---

## Roadmap (v0.2)

- [ ] Ollama contextual rewriting (200 ms timeout, regex fallback)
- [ ] `Stop` hook with per-session redaction summary
- [ ] Placeholder-before-execution (secret never enters LLM context)
- [ ] Homebrew formula + PyPI release
- [ ] GitHub Actions CI (Python 3.11–3.14, macOS/Linux/Windows)
- [ ] Compliance/audit export (SOC2-style report from the HMAC log)
- [ ] Supply-chain vetting for installed skills/MCP servers

---

## License

MIT — see [LICENSE](LICENSE).
