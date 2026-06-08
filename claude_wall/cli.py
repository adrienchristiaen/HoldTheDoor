"""claude-wall CLI entry point.

Subcommands:

- install      — register the three hooks in ~/.claude/settings.json
- uninstall    — strip claude-wall hooks (leaves user hooks intact)
- status       — show installed hooks, session dir, recent events
- reveal TOK   — print the original value for a session token
- audit        — print the audit log, with --verify to check the HMAC chain
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import settings as S
from .audit import AuditLog, generate_key
from .session import SessionStore, session_db_path, session_root
from .settings import SUPPORTED_CLIS, detect_cli


def _exit(msg: str, code: int = 1) -> int:
    sys.stderr.write(f"claude-wall: {msg}\n")
    return code


def _confirm(msg: str, yes: bool) -> bool:
    if yes:
        return True
    sys.stderr.write(f"{msg} [y/N] ")
    sys.stderr.flush()
    try:
        ans = input().strip().lower()
    except EOFError:
        return False
    return ans in {"y", "yes"}


def _resolve_clis(cli_arg: str) -> list[str]:
    if cli_arg == "all":
        found = detect_cli()
        return found if found else ["claude"]
    if cli_arg == "auto":
        found = detect_cli()
        return [found[0]] if found else ["claude"]
    return [cli_arg]


def cmd_install(args: argparse.Namespace) -> int:
    clis = _resolve_clis(args.cli)
    for cli in clis:
        report = S.install(cli=cli, dry_run=True, yes=args.yes)
        if args.dry_run:
            print(f"--- {cli} ({report['path']}) ---")
            print(json.dumps(report["after"], indent=2))
            continue
        if not _confirm(
            f"register claude-wall hooks in {report['path']}?", args.yes
        ):
            return _exit("aborted")
        S.install(cli=cli, yes=True)
        print(f"[{cli}] installed {report['added']} hooks in {report['path']}")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    clis = _resolve_clis(args.cli)
    for cli in clis:
        if not _confirm(f"remove claude-wall hooks from {cli}?", args.yes):
            return _exit("aborted")
        report = S.uninstall(cli=cli, yes=True)
        print(f"[{cli}] removed {report['removed']} hook command(s) from {report['path']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    clis = _resolve_clis(getattr(args, "cli", "auto"))
    for cli in clis:
        st = S.status(cli=cli)
        print(f"\n[{st['label']}]")
        print(f"  settings file: {st['path']}")
        print(f"  installed:     {st['installed']}")
        print(f"  buckets:       {', '.join(st['hooks']) or '(none)'}")
    print(f"\nsession dir:   {session_db_path().parent}")
    print(f"session db:    {session_db_path()}")
    try:
        log = _open_log()
        entries = log.read_last(5)
        print(f"\nlast {len(entries)} audit event(s):")
        for e in entries:
            print(
                f"  {e['hook']:<20} {e['event']:<8} tool={e.get('tool') or '-':<10}"
                f" count={e['count']} categories={e['categories']}"
            )
    except Exception as exc:
        print(f"\n(no audit available: {exc})")
    return 0


def _open_log() -> AuditLog:
    s = SessionStore.open()
    try:
        key_hex = s.get_meta("hmac_key")
    finally:
        s.close()
    if key_hex is None:
        return AuditLog(hmac_key=generate_key())
    return AuditLog(hmac_key=bytes.fromhex(key_hex))


def cmd_reveal(args: argparse.Namespace) -> int:
    s = SessionStore.open()
    try:
        original = s.get_original(args.token)
    finally:
        s.close()
    if original is None:
        return _exit(f"token {args.token!r} not found in current session")
    print(original)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    log = _open_log()
    if args.verify:
        ok, msg = log.verify()
        if ok:
            print("audit chain OK")
            return 0
        return _exit(f"audit chain BROKEN: {msg}")
    entries = log.read_last(args.last) if args.last else log.read_all()
    for e in entries:
        print(json.dumps(e))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude-wall",
        description="Privacy-first security layer for Claude Code",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    cli_choices = SUPPORTED_CLIS + ["all", "auto"]

    install = sub.add_parser("install", help="register hooks in CLI settings file")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--yes", "-y", action="store_true")
    install.add_argument("--cli", default="auto", choices=cli_choices,
                         help="target CLI: claude, codex, gemini, all, auto (default: auto-detect)")
    install.set_defaults(func=cmd_install)

    uninstall = sub.add_parser("uninstall", help="remove claude-wall hooks")
    uninstall.add_argument("--yes", "-y", action="store_true")
    uninstall.add_argument("--cli", default="auto", choices=cli_choices)
    uninstall.set_defaults(func=cmd_uninstall)

    status = sub.add_parser("status", help="show hook + session status")
    status.add_argument("--cli", default="auto", choices=cli_choices)
    status.set_defaults(func=cmd_status)

    reveal = sub.add_parser("reveal", help="reveal original value for a token")
    reveal.add_argument("token")
    reveal.set_defaults(func=cmd_reveal)

    audit = sub.add_parser("audit", help="print audit log")
    audit.add_argument("--verify", action="store_true", help="verify HMAC chain")
    audit.add_argument("--last", type=int, default=0, help="show only last N entries")
    audit.set_defaults(func=cmd_audit)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
