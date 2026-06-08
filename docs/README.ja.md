# claude-wall

> AI コーディング CLI 向けプライバシーファーストなセキュリティレイヤー。LLM が回避できない3つの決定的フック — シークレットを難読化し、機密ファイルをブロックし、プロンプトをスキャンします。

[![tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)](#テスト)
[![python](https://img.shields.io/badge/python-3.11+-blue)](#要件)
[![license](https://img.shields.io/badge/license-MIT-green)](../LICENSE)

**他の言語：** [English](../README.md) · [Français](README.fr.md) · [中文](README.zh.md)

---

## 対応 CLI

| CLI | フックサポート | 備考 |
|---|---|---|
| **Claude Code** | 完全（3フック） | `PostToolUse`、`PreToolUse`、`UserPromptSubmit` |
| **OpenAI Codex CLI** | 完全（3フック） | Claude Code と同一フォーマット |
| **Gemini CLI** | 部分（2フック） | `BeforeTool`、`AfterTool` — プロンプトフックなし |

---

## 動作概要

| フック | トリガー | アクション |
|---|---|---|
| **PostToolUse / AfterTool** | `Bash` / `Read` / `WebFetch` 実行後 | ツール出力に含まれるシークレットを可逆セッショントークン（例: `[WALL:openai_key:1]`）に置換し、LLM に渡る前に難読化します。 |
| **PreToolUse / BeforeTool** | ファイル/シェルツール呼び出し前 | 機密パス（`.env`、SSH キー、認証情報、`*.pem`）へのアクセスをブロックします。終了コード 2 = CLI がキャンセル。 |
| **UserPromptSubmit** | ユーザー入力ごと（Claude Code + Codex のみ） | 構造化シークレットをスキャン。デフォルトは警告のみ、厳格モードではブロック。 |

全イベントは HMAC チェーン型の監査ログ（`~/.local/share/claude-wall/audit.jsonl`）に記録されます。改ざんするとチェーンが壊れます。

---

## 要件

- Python 3.11+
- 以下のいずれか：Claude Code CLI、OpenAI Codex CLI、Gemini CLI
- 外部依存ゼロ — Python 標準ライブラリのみ（`sqlite3`、`hmac`、`re`、`json`）

---

## インストール

### macOS

```bash
# pipx のインストール（未インストールの場合）
brew install pipx

# claude-wall のインストール
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# フックの登録（インストール済み CLI を自動検出）
claude-wall install
```

### Linux

```bash
# pipx のインストール
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# ターミナルを再起動してから：
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# フックの登録
claude-wall install
```

### Windows（PowerShell）

```powershell
# pipx のインストール
pip install pipx
pipx ensurepath

# ターミナルを再起動してから：
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# フックの登録
claude-wall install
```

> **Windows の注意：** 設定ファイルはそれぞれ `%APPDATA%\Claude\settings.json`、
> `%APPDATA%\Codex\hooks.json`、`%APPDATA%\Gemini\settings.json` に書き込まれます。

### ソースからインストール（開発用）

```bash
git clone https://github.com/adrienchristiaen/claude-wall.git
cd claude-wall
pipx install --editable .
claude-wall install
```

---

## 対象 CLI の指定

デフォルトでは `install` がインストール済みの CLI を自動検出します。明示的に指定する場合：

```bash
claude-wall install --cli claude   # Claude Code のみ
claude-wall install --cli codex    # Codex CLI のみ
claude-wall install --cli gemini   # Gemini CLI のみ
claude-wall install --cli all      # 検出された全 CLI
```

`uninstall` と `status` も同じ `--cli` フラグに対応しています。

---

## インストールの確認

```bash
claude-wall status
```

期待される出力：

```
[Claude Code]
  settings file: /Users/you/.claude/settings.json
  installed:     True
  buckets:       PostToolUse, PreToolUse, UserPromptSubmit

session dir:   /tmp/claude-wall/<session-id>
```

新しい CLI セッションを開くと、フックが自動的に有効になります。

---

## コマンド一覧

### `claude-wall status [--cli ...]`
各 CLI のフック状態、セッション DB パス、直近5件の監査イベントを表示します。

### `claude-wall reveal <token>`
セッショントークンの元の値を返します。

### `claude-wall audit [--verify] [--last N]`
監査ログを表示します。`--verify` で HMAC チェーンの整合性を検証します。

### `claude-wall uninstall [--cli ...] [--yes]`
claude-wall のエントリのみ削除します。他のフックはそのまま保持されます。

### 緊急無効化

```bash
export CLAUDE_WALL_DISABLED=1
# ... シークレットパターン例を含むドキュメント編集などの操作 ...
unset CLAUDE_WALL_DISABLED
```

---

## 厳格モード

デフォルトでは `UserPromptSubmit` フックは警告のみでプロンプトを通過させます。ブロックするには：

```bash
export CLAUDE_WALL_STRICT=1
```

---

## 検出されるシークレットカテゴリ

| カテゴリ | パターン例 |
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
| `private_ip` | RFC 1918 アドレス範囲 |
| `internal_hostname` | `*.internal`、`*.corp`、`*.local` |

`claude_wall/patterns.py` にエントリを追加することでカスタムカテゴリを追加できます。

---

## テスト

```bash
pip install -e '.[dev]'
pytest -q   # 86 passed
```

---

## ライセンス

MIT — [LICENSE](../LICENSE) 参照。
