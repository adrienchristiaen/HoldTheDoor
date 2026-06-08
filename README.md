# claude-wall

> Privacy-first security layer for AI coding CLIs. Three deterministic hooks the LLM cannot bypass — secrets get redacted, sensitive files get blocked, prompts get scanned.

[![tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)](#testing)
[![python](https://img.shields.io/badge/python-3.11+-blue)](#requirements)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Read in:** [Français](docs/README.fr.md) · [中文](docs/README.zh.md) · [日本語](docs/README.ja.md)

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
| **PreToolUse / BeforeTool** | Before any file/shell tool call | Blocks calls targeting sensitive paths (`.env`, SSH keys, credentials, `*.pem`). Exit code 2 = CLI aborts. |
| **UserPromptSubmit** | Every user prompt (Claude Code + Codex only) | Scans your prompt for structured secrets. Warns by default, blocks in strict mode. |

Every event is recorded in an HMAC-chained audit log (`~/.local/share/claude-wall/audit.jsonl`). Tampering with any entry breaks the chain.

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

---

## Targeting a specific CLI

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
[Claude Code]
  settings file: /Users/you/.claude/settings.json
  installed:     True
  buckets:       PostToolUse, PreToolUse, UserPromptSubmit

session dir:   /tmp/claude-wall/<session-id>
```

Open a new CLI session — hooks activate automatically.

---

## Usage

### `claude-wall status [--cli auto|claude|codex|gemini|all]`

Show installed hooks per CLI, session DB path, last 5 audit events.

### `claude-wall reveal <token>`

Return the original value behind a session token:

```
$ claude-wall reveal '[WALL:openai_key:1]'
sk-proj-••••••••••••••••••••••••••••••••••••••
```

Tokens are session-scoped — they only resolve while the current session is alive.

### `claude-wall audit [--verify] [--last N]`

Print the audit log. `--verify` walks the HMAC chain:

```
$ claude-wall audit --verify
audit chain OK
```

### `claude-wall uninstall [--cli ...] [--yes]`

Strips only claude-wall entries. Other hooks are untouched.

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
├── workspace.py   # workspace scan + check_path / check_bash
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

Extend by adding entries to `claude_wall/patterns.py`.

---

## Testing

```bash
pip install -e '.[dev]'
pytest -q   # 86 passed
```

---

## Threat model

**Mitigated:**
1. LLM reads secrets via tool output → PostToolUse/AfterTool redaction
2. LLM reads `.env` / SSH keys → PreToolUse/BeforeTool block (exit 2)
3. Secrets in prompts → UserPromptSubmit scan
4. Post-hoc log tampering → HMAC-chained audit

**Not mitigated:**
- Copy-paste propagation (LLM copies secret to another file)
- Full filesystem isolation (use a container)
- Novel secret formats not in `patterns.py`
- Gemini CLI prompts (no `UserPromptSubmit` equivalent)

---

## Roadmap (v0.2)

- [ ] Ollama contextual rewriting (200 ms timeout, regex fallback)
- [ ] `Stop` hook with per-session redaction summary
- [ ] Placeholder-before-execution (secret never enters LLM context)
- [ ] Homebrew formula + PyPI release
- [ ] GitHub Actions CI (Python 3.11–3.14, macOS/Linux/Windows)

---

## License

MIT — see [LICENSE](LICENSE).
