# claude-wall

> AI 编程 CLI 的隐私安全层。三个确定性钩子，LLM 无法绕过——密钥被脱敏、敏感文件被屏蔽、提示词被扫描。

[![tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)](#测试)
[![python](https://img.shields.io/badge/python-3.11+-blue)](#要求)
[![license](https://img.shields.io/badge/license-MIT-green)](../LICENSE)

**其他语言：** [English](../README.md) · [Français](README.fr.md) · [日本語](README.ja.md)

---

## 支持的 CLI

| CLI | 钩子支持 | 说明 |
|---|---|---|
| **Claude Code** | 完整（3 个钩子） | `PostToolUse`、`PreToolUse`、`UserPromptSubmit` |
| **OpenAI Codex CLI** | 完整（3 个钩子） | 与 Claude Code 格式相同 |
| **Gemini CLI** | 部分（2 个钩子） | `BeforeTool`、`AfterTool` — 无提示词钩子 |

---

## 工作原理

| 钩子 | 触发时机 | 操作 |
|---|---|---|
| **PostToolUse / AfterTool** | `Bash` / `Read` / `WebFetch` 调用返回后 | 将检测到的密钥替换为可逆 session token（如 `[WALL:openai_key:1]`），在 LLM 读取前完成脱敏。 |
| **PreToolUse / BeforeTool** | 任何文件/Shell 工具调用之前 | 屏蔽指向敏感路径（`.env`、SSH 密钥、凭据、`*.pem`）的调用。退出码 2 = CLI 中止操作。 |
| **UserPromptSubmit** | 每次用户输入（仅 Claude Code + Codex） | 扫描结构化密钥。默认警告，严格模式下阻止发送。 |

所有事件记录在 HMAC 链式审计日志（`~/.local/share/claude-wall/audit.jsonl`）中，任何篡改都会破坏链式结构。

---

## 要求

- Python 3.11+
- 以下任一 CLI：Claude Code、OpenAI Codex CLI、Gemini CLI
- 零外部依赖——仅使用 Python 标准库（`sqlite3`、`hmac`、`re`、`json`）

---

## 安装

### macOS

```bash
# 安装 pipx（如未安装）
brew install pipx

# 安装 claude-wall
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# 注册钩子（自动检测已安装的 CLI）
claude-wall install
```

### Linux

```bash
# 安装 pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# 重启终端后执行：
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# 注册钩子
claude-wall install
```

### Windows（PowerShell）

```powershell
# 安装 pipx
pip install pipx
pipx ensurepath

# 重启终端后执行：
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# 注册钩子
claude-wall install
```

> **Windows 说明：** 配置文件分别写入 `%APPDATA%\Claude\settings.json`、
> `%APPDATA%\Codex\hooks.json` 和 `%APPDATA%\Gemini\settings.json`。

### 从源码安装（开发模式）

```bash
git clone https://github.com/adrienchristiaen/claude-wall.git
cd claude-wall
pipx install --editable .
claude-wall install
```

---

## 指定目标 CLI

默认情况下 `install` 自动检测已安装的 CLI。也可显式指定：

```bash
claude-wall install --cli claude   # 仅 Claude Code
claude-wall install --cli codex    # 仅 Codex CLI
claude-wall install --cli gemini   # 仅 Gemini CLI
claude-wall install --cli all      # 所有检测到的 CLI
```

`uninstall` 和 `status` 命令支持相同的 `--cli` 参数。

---

## 验证安装

```bash
claude-wall status
```

预期输出：

```
[Claude Code]
  settings file: /Users/you/.claude/settings.json
  installed:     True
  buckets:       PostToolUse, PreToolUse, UserPromptSubmit

session dir:   /tmp/claude-wall/<session-id>
```

重新打开 CLI 会话后，钩子将自动生效。

---

## 常用命令

### `claude-wall status [--cli ...]`
显示每个 CLI 的钩子安装状态、session DB 路径、最近 5 条审计事件。

### `claude-wall reveal <token>`
返回 session token 对应的原始值。

### `claude-wall audit [--verify] [--last N]`
打印审计日志，`--verify` 校验 HMAC 链完整性。

### `claude-wall uninstall [--cli ...] [--yes]`
仅移除 claude-wall 的条目，其他钩子不受影响。

### 紧急禁用

```bash
export CLAUDE_WALL_DISABLED=1
# ... 处理含示例密钥的文档等操作 ...
unset CLAUDE_WALL_DISABLED
```

---

## 严格模式

默认情况下，`UserPromptSubmit` 钩子仅发出警告，不阻止发送。如需阻止：

```bash
export CLAUDE_WALL_STRICT=1
```

---

## 可检测的密钥类型

| 类别 | 模式示例 |
|---|---|
| `anthropic_key` | `sk-ant-api03-…` |
| `openai_key` | `sk-proj-…` |
| `github_token` | `ghp_…`、`gho_…`、`ghs_…` |
| `aws_access_key` | `AKIA…` |
| `google_api_key` | `AIza…` |
| `jwt` | `eyJ….eyJ….` |
| `private_key_block` | `-----BEGIN … KEY-----` |
| `slack_token` | `xoxb-…` |
| `email` | `user@domain.tld` |
| `private_ip` | RFC 1918 地址段 |
| `internal_hostname` | `*.internal`、`*.corp`、`*.local` |

如需添加自定义类别，编辑 `claude_wall/patterns.py` 即可。

---

## 测试

```bash
pip install -e '.[dev]'
pytest -q   # 86 passed
```

---

## 许可证

MIT — 详见 [LICENSE](../LICENSE)。
