from __future__ import annotations

import argparse
import sys
from obsidian_graphify.commands.lint import command_lint
from obsidian_graphify.commands.lookup import command_lookup
from obsidian_graphify.commands.maintenance import command_changes, command_export, command_impact, command_scan, command_status
from obsidian_graphify.commands.scope import command_scope
from obsidian_graphify.config import resolve_vault, use_vault
from obsidian_graphify.commands.init import command_init
from obsidian_graphify.vault import load_vault


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Graphify vault maintenance helper")
    parser.add_argument("--vault", help="Vault directory (overrides GRAPHIFY_VAULT and discovery)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="Create a Vault, preserving existing files by default")
    init_parser.add_argument("path", help="Directory to initialize")
    init_parser.add_argument("--force", action="store_true", help="Replace existing scaffold files")
    scan_parser = subparsers.add_parser("scan", help="Rebuild _logs/pending.md from raw material")
    scan_parser.add_argument("--scope", help="Optional processing list path; empty or missing lists default to full scope")
    changes_parser = subparsers.add_parser("changes", help="Show added/modified/removed raw/knowledge files since the last baseline")
    changes_parser.add_argument("--save", action="store_true", help="Write the current file snapshot as the new baseline after reporting")
    lookup_parser = subparsers.add_parser("lookup", help="Locate matching knowledge and related notes")
    lookup_parser.add_argument("query", help="Search term, alias, or partial note title")
    lookup_parser.add_argument("--limit", type=int, default=5, help="Maximum number of primary matches to show")
    impact_parser = subparsers.add_parser("impact", help="Show downstream notes affected by a changed knowledge note")
    impact_parser.add_argument("path", help="Path, wikilink, alias, or title of the changed note")
    scope_parser = subparsers.add_parser("scope", help="Show full scope or processing-list-scoped work set")
    scope_parser.add_argument("path", nargs="?", help="Processing list path; defaults to full scope when omitted")
    subparsers.add_parser("status", help="Show a high-level vault summary")
    lint_parser = subparsers.add_parser("lint", help="Validate note contracts and graph integrity")
    lint_parser.add_argument("--scope", help="Optional processing list path; validates only scoped knowledge notes")
    subparsers.add_parser("export", help="Export graph artifacts and protected-link snapshot")
    compile_parser = subparsers.add_parser("compile-media", help="Compile local media into a Source-grade canonical note")
    compile_parser.add_argument("path", help="Path to a media file under raw/inbox/video-visual/")
    compile_parser.add_argument("--force", action="store_true", help="Overwrite an existing generated markdown note")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    try:
        if args.command == "init":
            return command_init(args.path, force=args.force)
        context = resolve_vault(args.vault)
        if not context.root.is_dir():
            raise ValueError(f"Vault directory does not exist: {context.root}. Run graphify init first.")
        with use_vault(context):
            return dispatch(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"graphify: {exc}", file=sys.stderr)
        return 1


def dispatch(args: argparse.Namespace) -> int:
    if args.command == "compile-media":
        from obsidian_graphify.media.transfer_platform import command_compile_media
        return command_compile_media(target_path=args.path, force=args.force)
    data = load_vault()
    if args.command == "scan":
        return command_scan(data, scope_path=args.scope)
    if args.command == "changes":
        return command_changes(data, save_baseline=args.save)
    if args.command == "lookup":
        return command_lookup(data, query=args.query, limit=max(1, args.limit))
    if args.command == "impact":
        return command_impact(data, target_ref=args.path)
    if args.command == "scope":
        return command_scope(data, scope_path=args.path)
    if args.command == "status":
        return command_status(data)
    if args.command == "lint":
        return command_lint(data, scope_path=args.scope)
    if args.command == "export":
        return command_export(data)
    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 2
