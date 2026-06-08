# claude-wall

> Couche de sécurité privacy-first pour les CLI d'IA. Trois hooks déterministes que le LLM ne peut pas contourner — les secrets sont masqués, les fichiers sensibles bloqués, les prompts analysés.

[![tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)](#tests)
[![python](https://img.shields.io/badge/python-3.11+-blue)](#prérequis)
[![license](https://img.shields.io/badge/license-MIT-green)](../LICENSE)

**Lire en :** [English](../README.md) · [中文](README.zh.md) · [日本語](README.ja.md)

---

## CLI supportés

| CLI | Support hooks | Notes |
|---|---|---|
| **Claude Code** | Complet (3 hooks) | `PostToolUse`, `PreToolUse`, `UserPromptSubmit` |
| **OpenAI Codex CLI** | Complet (3 hooks) | Même format que Claude Code |
| **Gemini CLI** | Partiel (2 hooks) | `BeforeTool`, `AfterTool` — pas de hook prompt |

---

## Ce que ça fait

| Hook | Déclencheur | Action |
|---|---|---|
| **PostToolUse / AfterTool** | Après `Bash` / `Read` / `WebFetch` | Remplace les secrets détectés par des tokens réversibles `[WALL:openai_key:1]` avant que le LLM les voie. |
| **PreToolUse / BeforeTool** | Avant tout appel fichier/shell | Bloque les appels ciblant des chemins sensibles (`.env`, clés SSH, credentials, `*.pem`). Code de sortie 2 = le CLI annule. |
| **UserPromptSubmit** | Chaque prompt utilisateur (Claude Code + Codex) | Analyse les secrets structurés. Avertit par défaut, bloque en mode strict. |

Chaque événement est enregistré dans un log d'audit HMAC-chaîné (`~/.local/share/claude-wall/audit.jsonl`). Toute modification rompt la chaîne.

---

## Prérequis

- Python 3.11+
- Un de : Claude Code CLI, OpenAI Codex CLI, Gemini CLI
- Zéro dépendance externe — stdlib Python uniquement (`sqlite3`, `hmac`, `re`, `json`)

---

## Installation

### macOS

```bash
# Installer pipx si absent
brew install pipx

# Installer claude-wall
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# Enregistrer les hooks (détection auto des CLI installés)
claude-wall install
```

### Linux

```bash
# Installer pipx
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Redémarrer le terminal, puis :
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# Enregistrer les hooks
claude-wall install
```

### Windows (PowerShell)

```powershell
# Installer pipx
pip install pipx
pipx ensurepath

# Redémarrer le terminal, puis :
pipx install git+https://github.com/adrienchristiaen/claude-wall.git

# Enregistrer les hooks
claude-wall install
```

> **Note Windows :** Les settings sont écrits dans `%APPDATA%\Claude\settings.json`,
> `%APPDATA%\Codex\hooks.json` et `%APPDATA%\Gemini\settings.json` selon le CLI.

### Depuis les sources (développement)

```bash
git clone https://github.com/adrienchristiaen/claude-wall.git
cd claude-wall
pipx install --editable .
claude-wall install
```

---

## Cibler un CLI spécifique

Par défaut, `install` détecte automatiquement les CLI installés :

```bash
claude-wall install --cli claude   # Claude Code uniquement
claude-wall install --cli codex    # Codex CLI uniquement
claude-wall install --cli gemini   # Gemini CLI uniquement
claude-wall install --cli all      # Tous les CLI détectés
```

Le même flag fonctionne pour `uninstall` et `status`.

---

## Vérifier l'installation

```bash
claude-wall status
```

Sortie attendue :

```
[Claude Code]
  settings file: /Users/vous/.claude/settings.json
  installed:     True
  buckets:       PostToolUse, PreToolUse, UserPromptSubmit

session dir:   /tmp/claude-wall/<session-id>
```

Ouvrez une nouvelle session CLI — les hooks s'activent automatiquement.

---

## Commandes

### `claude-wall status [--cli auto|claude|codex|gemini|all]`
Affiche les hooks installés par CLI, le chemin de la session DB, les 5 derniers événements d'audit.

### `claude-wall reveal <token>`
Retourne la valeur originale d'un token de session.

### `claude-wall audit [--verify] [--last N]`
Affiche le log d'audit. `--verify` parcourt la chaîne HMAC.

### `claude-wall uninstall [--cli ...] [--yes]`
Retire uniquement les entrées de claude-wall. Les autres hooks sont préservés.

### Désactivation d'urgence

```bash
export CLAUDE_WALL_DISABLED=1
# ... opérations avec exemples de patterns de secrets ...
unset CLAUDE_WALL_DISABLED
```

---

## Mode strict

Par défaut, le hook `UserPromptSubmit` avertit sans bloquer. Pour bloquer :

```bash
export CLAUDE_WALL_STRICT=1
```

---

## Catégories de secrets détectées

| Catégorie | Pattern |
|---|---|
| `anthropic_key` | `sk-ant-api03-…` |
| `openai_key` | `sk-proj-…` |
| `github_token` | `ghp_…`, `gho_…`, `ghs_…` |
| `aws_access_key` | `AKIA…` |
| `google_api_key` | `AIza…` |
| `jwt` | `eyJ….eyJ….` |
| `private_key_block` | `-----BEGIN … KEY-----` |
| `slack_token` | `xoxb-…` |
| `email` | `utilisateur@domaine.tld` |
| `private_ip` | Plages RFC 1918 |
| `internal_hostname` | `*.internal`, `*.corp`, `*.local` |

Étendre en ajoutant des entrées dans `claude_wall/patterns.py`.

---

## Tests

```bash
pip install -e '.[dev]'
pytest -q   # 86 passed
```

---

## Licence

MIT — voir [LICENSE](../LICENSE).
