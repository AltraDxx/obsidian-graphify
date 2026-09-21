#!/usr/bin/env python3
"""Graphify vault maintenance utilities.

This script keeps the Graphify vault lightweight for core maintenance tasks.
Most vault commands rely on the Python standard library only; `compile-media`
uses optional local media/OCR dependencies. It provides core operator commands:

- scan: rebuild `_logs/pending.md` from current raw material
- changes: detect added/modified/removed tracked files since the last baseline
- lookup: locate the best matching knowledge note(s) and nearby related nodes
- impact: show notes affected by a changed Source, Claim, Wiki, or Index note
- scope: show the full or processing-list-scoped work set
- status: print vault counts and health signals
- lint: validate note contracts and graph integrity
- export: emit graph artifacts and protect-link snapshots
- compile-media: compile local visual-first raw video into a structured markdown note
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "raw"
CLUSTER_ROOT = ROOT / "知识簇"
GRAPHIFY_ROOT = ROOT / "_graphify"
SOURCE_ROOT = GRAPHIFY_ROOT / "sources"
INDEX_ROOT = GRAPHIFY_ROOT / "indexes"
LOG_ROOT = ROOT / "_logs"
EXPORT_ROOT = ROOT / "exports"
LINK_MANIFEST_PATH = LOG_ROOT / "link-manifest.json"
PENDING_PATH = LOG_ROOT / "pending.md"
STATE_PATH = LOG_ROOT / "vault-state.json"
DEFAULT_SCOPE_PATH = ROOT / "处理清单.md"

RELATION_FIELDS = ("see_also", "part_of", "depends_on", "supports", "contradicts")
CLAIM_REF_FIELDS = ("claim_refs", "summary_claim_refs", "conflict_refs")
COMMON_WIKI_FIELDS = (
    "type",
    "status",
    "aliases",
    "source_refs",
    "tags",
    "confidence",
    "updated_at",
    "review_after",
    *RELATION_FIELDS,
)
SOURCE_FIELDS = ("source_kind", "traceability_level")
CLAIM_FIELDS = (
    "statement",
    "claim_type",
    "support_state",
    "verification_state",
    "scope",
    "boundary_note",
    "claim_origin",
    "claim_status",
    "conflict_refs",
)
WIKI_FIELDS = (
    "core_focus",
    "claim_refs",
    "summary_claim_refs",
    "draft_state",
    "version_no",
    "importance",
)
VALID_TYPES = {"source", "claim", "wiki", "index"}
VALID_STATUSES = {"draft", "reviewed", "verified", "stale", "archived"}
VALID_SUPPORT_STATES = {"supported", "weak", "conflicting", "unclear"}
VALID_VERIFICATION_STATES = {"source_supported", "cross_source_supported", "disputed", "unclear"}
VALID_CLAIM_STATUSES = {"active", "disputed", "outdated", "pending"}
STANDALONE_CLAIM_GRAPH_ROLE = "standalone_claim"
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
RAW_EXCLUDED_DIRS = {"assets"}
IGNORED_FILENAMES = {".DS_Store"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
MEDIA_COMPILE_MODES = {"video-visual", "video-audio", "audio"}
VISUAL_MODE = "video-visual"
DEFAULT_VISUAL_MAX_INTERVAL_SECONDS = 15.0
DEFAULT_VISUAL_MAX_FRAMES = 24
VISUAL_OCR_NOISE_PATTERNS = (
    r"^\d{1,2}:\d{2}$",
    r"^5G\d*$",
    r"^\d+\s*%$",
    r"^\d+\s*(天|小时|分钟)前$",
    r"^@\S+·\d+\s*(天|小时|分钟)前$",
    r"^第?\d+\s*(赞|评论|收藏|分享)?$",
    r"^全屏观看$",
    r"^点击推荐[>＞]?$",
    r"^下一集[>＞]?$",
    r"^第\d+集.*展开$",
    r"^合集[·:：].*$",
    r"^拍同款$",
    r"^展开$",
    r"^\d*个人观点，仅供参考$",
    r"^搜索$",
    r"^弹$",
    r"^善语结善缘，恶言伤人心$",
    r"^汽水音乐[>＞].*$",
)


@dataclass
class Note:
    path: Path
    rel_path: str
    title: str
    body: str
    frontmatter: dict[str, Any]
    kind: str
    note_type: str
    status: str
    source_type: str
    aliases: list[str]
    tags: list[str]
    source_refs: list[str]
    relations: dict[str, list[str]]
    claim_refs: list[str]
    summary_claim_refs: list[str]
    conflict_refs: list[str]
    wikilinks: list[str]
    confidence: float | None
    updated_at: str
    review_after: str


@dataclass
class RawItem:
    path: Path
    rel_path: str
    title: str
    source_type: str
    status: str
    origin: str
    captured_at: str
    tags: list[str]
    is_markdown: bool
    frontmatter: dict[str, Any]
    body: str
    wikilinks: list[str]


@dataclass
class Edge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class LookupUnit:
    note_path: str
    note_type: str
    section: str
    text: str


@dataclass(frozen=True)
class LookupMatch:
    note: Note
    score: float
    section: str


@dataclass(frozen=True)
class RelatedMatch:
    path: str
    score: int
    kinds: tuple[str, ...]


@dataclass(frozen=True)
class MediaProbe:
    duration_seconds: float
    width: int | None
    height: int | None
    has_audio: bool
    has_video: bool


@dataclass(frozen=True)
class VisualRegionRecord:
    region_id: str
    bbox: list[float]
    text: str
    order: int
    review: str = ""


@dataclass(frozen=True)
class VisualAnchorRecord:
    anchor_id: str
    text: str
    review: str = ""
    region_ids: tuple[str, ...] = ()


@dataclass
class VisualFrameRecord:
    index: int
    cover_start_seconds: float
    cover_end_seconds: float
    rel_image_path: str
    regions: list[VisualRegionRecord]
    anchors: list[VisualAnchorRecord]
    error: str = ""


@dataclass(frozen=True)
class VisualCompileArtifact:
    note_path: Path
    asset_dir: Path
    sidecar_path: Path
    frame_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Graphify vault maintenance helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "compile-media":
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


def load_vault() -> dict[str, Any]:
    raw_items = collect_raw_items()
    wiki_notes = collect_knowledge_notes()
    all_notes = {note.rel_path: note for note in wiki_notes}
    all_nodes = build_node_specs(raw_items, wiki_notes)
    alias_map = build_alias_map(raw_items, wiki_notes)
    processed_raw_refs = collect_processed_raw_refs(wiki_notes)
    return {
        "raw_items": raw_items,
        "wiki_notes": wiki_notes,
        "wiki_map": all_notes,
        "node_specs": all_nodes,
        "alias_map": alias_map,
        "processed_raw_refs": processed_raw_refs,
        "file_snapshot": build_file_snapshot(raw_items, wiki_notes),
    }


def collect_knowledge_notes() -> list[Note]:
    roots = (
        CLUSTER_ROOT,
        SOURCE_ROOT,
        INDEX_ROOT,
    )
    notes: list[Note] = []
    for root in roots:
        notes.extend(collect_markdown_notes(root))
    return sorted(notes, key=lambda note: note.rel_path)


def collect_raw_items() -> list[RawItem]:
    items: list[RawItem] = []
    if not RAW_ROOT.exists():
        return items
    for path in sorted(p for p in RAW_ROOT.rglob("*") if p.is_file()):
        if path.name in IGNORED_FILENAMES:
            continue
        rel_parts = path.relative_to(ROOT).parts
        if len(rel_parts) > 1 and rel_parts[1] in RAW_EXCLUDED_DIRS:
            continue
        rel_path = path.relative_to(ROOT).as_posix()
        source_type = infer_source_type(path)
        if path.suffix.lower() in MARKDOWN_EXTENSIONS:
            frontmatter, body = load_markdown(path)
            status = as_string(frontmatter.get("status")) or "inbox"
            origin = as_string(frontmatter.get("origin"))
            captured_at = as_string(frontmatter.get("captured_at"))
            tags = listify(frontmatter.get("tags"))
            title = infer_title(path, frontmatter, body)
            wikilinks = extract_wikilinks(body)
            items.append(
                RawItem(
                    path=path,
                    rel_path=rel_path,
                    title=title,
                    source_type=as_string(frontmatter.get("source_type")) or source_type,
                    status=status,
                    origin=origin,
                    captured_at=captured_at,
                    tags=tags,
                    is_markdown=True,
                    frontmatter=frontmatter,
                    body=body,
                    wikilinks=wikilinks,
                )
            )
            continue
        items.append(
            RawItem(
                path=path,
                rel_path=rel_path,
                title=path.stem,
                source_type=source_type,
                status="inbox",
                origin="",
                captured_at="",
                tags=[],
                is_markdown=False,
                frontmatter={},
                body="",
                wikilinks=[],
            )
        )
    return items


def collect_markdown_notes(root: Path) -> list[Note]:
    notes: list[Note] = []
    if not root.exists():
        return notes
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in MARKDOWN_EXTENSIONS):
        rel_path = path.relative_to(ROOT).as_posix()
        frontmatter, body = load_markdown(path)
        title = infer_title(path, frontmatter, body)
        inferred_kind = infer_knowledge_kind(path)
        note_type = as_string(frontmatter.get("type")) or inferred_kind
        status = as_string(frontmatter.get("status"))
        source_type = infer_source_type(path)
        aliases = listify(frontmatter.get("aliases"))
        tags = listify(frontmatter.get("tags"))
        source_refs = listify(frontmatter.get("source_refs"))
        relations = {field: listify(frontmatter.get(field)) for field in RELATION_FIELDS}
        claim_refs = listify(frontmatter.get("claim_refs"))
        summary_claim_refs = listify(frontmatter.get("summary_claim_refs"))
        conflict_refs = listify(frontmatter.get("conflict_refs"))
        confidence = to_float(frontmatter.get("confidence"))
        updated_at = as_string(frontmatter.get("updated_at"))
        review_after = as_string(frontmatter.get("review_after"))
        wikilinks = extract_wikilinks(body)
        notes.append(
            Note(
                path=path,
                rel_path=rel_path,
                title=title,
                body=body,
                frontmatter=frontmatter,
                kind=inferred_kind,
                note_type=note_type,
                status=status,
                source_type=source_type,
                aliases=aliases,
                tags=tags,
                source_refs=source_refs,
                relations=relations,
                claim_refs=claim_refs,
                summary_claim_refs=summary_claim_refs,
                conflict_refs=conflict_refs,
                wikilinks=wikilinks,
                confidence=confidence,
                updated_at=updated_at,
                review_after=review_after,
            )
        )
    return notes


def build_node_specs(raw_items: list[RawItem], wiki_notes: list[Note]) -> dict[str, dict[str, Any]]:
    node_specs: dict[str, dict[str, Any]] = {}
    processed_raw_refs = collect_processed_raw_refs(wiki_notes)
    for item in raw_items:
        status = item.status or ("processed" if item.rel_path in processed_raw_refs else "inbox")
        node_specs[item.rel_path] = {
            "id": item.rel_path,
            "path": item.rel_path,
            "title": item.title,
            "type": "raw",
            "status": status,
            "tags": item.tags,
            "aliases": [],
            "confidence": None,
        }
    for note in wiki_notes:
        node_specs[note.rel_path] = {
            "id": note.rel_path,
            "path": note.rel_path,
            "title": note.title,
            "type": note.note_type or "unknown",
            "status": note.status or "",
            "tags": note.tags,
            "aliases": note.aliases,
            "confidence": note.confidence,
        }
    return node_specs


def build_alias_map(raw_items: list[RawItem], wiki_notes: list[Note]) -> dict[str, str | None]:
    candidates: defaultdict[str, set[str]] = defaultdict(set)
    for item in raw_items:
        for key in candidate_keys(item.rel_path, item.title, []):
            candidates[key].add(item.rel_path)
    for note in wiki_notes:
        for key in candidate_keys(note.rel_path, note.title, note.aliases):
            candidates[key].add(note.rel_path)
    alias_map: dict[str, str | None] = {}
    for key, values in candidates.items():
        alias_map[key] = next(iter(values)) if len(values) == 1 else None
    return alias_map


def collect_processed_raw_refs(wiki_notes: list[Note]) -> set[str]:
    refs: set[str] = set()
    for note in wiki_notes:
        for ref in note.source_refs:
            if ref.startswith("raw/"):
                refs.add(ref)
    return refs


def extract_scope_refs(text: str) -> list[str]:
    refs: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not re.match(r"^-\s+\[\s\]\s+", line):
            continue
        for link in re.findall(r"\[\[([^\]]+)\]\]", line):
            target = link.split("|", 1)[0].split("#", 1)[0].strip()
            if target:
                refs.append(target)
        backticks = re.findall(r"`([^`]+)`", line)
        refs.extend(item.strip() for item in backticks if item.strip())
        if "[[" in line or backticks:
            continue
        text = re.sub(r"^-\s+\[\s\]\s+", "", line).strip()
        text = text.split(" #", 1)[0].strip()
        if text:
            refs.append(text)
    return dedupe_preserve_order(refs)


def resolve_scope(data: dict[str, Any], scope_path: str | None = None) -> dict[str, Any]:
    raw_items: list[RawItem] = data["raw_items"]
    wiki_notes: list[Note] = data["wiki_notes"]
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    alias_map: dict[str, str | None] = data["alias_map"]
    all_paths = {item.rel_path for item in raw_items} | {note.rel_path for note in wiki_notes}
    if not scope_path:
        return {"mode": "full", "is_scoped": False, "paths": all_paths, "seeds": []}

    path = Path(scope_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return {"mode": "full", "is_scoped": False, "paths": all_paths, "seeds": []}

    refs = extract_scope_refs(path.read_text(encoding="utf-8"))
    if not refs:
        return {"mode": "full", "is_scoped": False, "paths": all_paths, "seeds": []}

    seeds: list[str] = []
    for ref in refs:
        resolved = resolve_reference(ref, alias_map, node_specs)
        if resolved:
            seeds.append(resolved)
    seeds = dedupe_preserve_order(seeds)
    paths = expand_scope_paths(seeds, data)
    return {"mode": "list", "is_scoped": True, "paths": paths, "seeds": seeds}


def expand_scope_paths(seeds: list[str], data: dict[str, Any]) -> set[str]:
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    edges = build_edges(data)
    incoming, outgoing = adjacency(edges)
    paths: set[str] = set(seeds)

    for seed in seeds:
        node_type = as_string(node_specs.get(seed, {}).get("type"))
        if node_type == "raw":
            continue
        impact = find_impacted_notes(seed, edges, node_specs)
        for key in ("claims", "wiki", "indexes"):
            paths.update(impact[key])
        if node_type == "wiki":
            for edge in outgoing.get(seed, []):
                if as_string(node_specs.get(edge.target, {}).get("type")) in {"claim", "index"}:
                    paths.add(edge.target)
        if node_type == "claim":
            for edge in outgoing.get(seed, []):
                if as_string(node_specs.get(edge.target, {}).get("type")) in {"source", "claim"}:
                    paths.add(edge.target)
            for edge in incoming.get(seed, []):
                if as_string(node_specs.get(edge.source, {}).get("type")) == "claim":
                    paths.add(edge.source)
        if node_type == "source":
            for edge in incoming.get(seed, []):
                if as_string(node_specs.get(edge.source, {}).get("type")) == "claim":
                    paths.add(edge.source)

    return paths


def command_scope(data: dict[str, Any], scope_path: str | None = None) -> int:
    scoped = resolve_scope(data, scope_path)
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    print(f"Scope mode: {scoped['mode']}")
    if scoped["seeds"]:
        print("")
        print("Seeds")
        for path in scoped["seeds"]:
            node = node_specs.get(path, {})
            print(f"- {node.get('title', path)} | path={path} | type={node.get('type', '-')}")

    print("")
    print("Scope paths")
    for path in sorted(scoped["paths"]):
        node = node_specs.get(path, {})
        print(f"- {node.get('title', path)} | path={path} | type={node.get('type', '-')}")
    return 0


def command_scan(data: dict[str, Any], scope_path: str | None = None) -> int:
    scoped = resolve_scope(data, scope_path)
    raw_items: list[RawItem] = [
        item for item in data["raw_items"] if not scoped["is_scoped"] or item.rel_path in scoped["paths"]
    ]
    processed_raw_refs: set[str] = data["processed_raw_refs"]
    pending_items = []
    for item in raw_items:
        status = item.status or "inbox"
        if item.rel_path in processed_raw_refs:
            status = "processed"
        if status != "processed":
            pending_items.append(item)
    pending_items.sort(key=lambda item: item.rel_path)
    by_type: defaultdict[str, list[RawItem]] = defaultdict(list)
    for item in pending_items:
        by_type[item.source_type].append(item)

    lines = [
        "# Pending Raw Items",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "## Summary",
        f"- Pending items: {len(pending_items)}",
        f"- Processed raw refs detected in wiki: {len(processed_raw_refs)}",
        "",
    ]
    if not pending_items:
        lines.extend(["## Queue", "- No pending raw items.", ""])
    else:
        for source_type in sorted(by_type):
            lines.append(f"## {source_type.title()}")
            for item in by_type[source_type]:
                origin = f" | origin: {item.origin}" if item.origin else ""
                captured = f" | captured_at: {item.captured_at}" if item.captured_at else ""
                lines.append(f"- [ ] `{item.rel_path}`{origin}{captured}")
            lines.append("")
    write_text(PENDING_PATH, "\n".join(lines).rstrip() + "\n")
    print(f"Updated {PENDING_PATH.relative_to(ROOT).as_posix()} with {len(pending_items)} pending items.")
    return 0


def command_changes(data: dict[str, Any], save_baseline: bool = False) -> int:
    current_snapshot: dict[str, dict[str, Any]] = data["file_snapshot"]
    previous_state = load_json(STATE_PATH) or {}
    previous_snapshot: dict[str, dict[str, Any]] = previous_state.get("files", {})

    added = sorted(path for path in current_snapshot if path not in previous_snapshot)
    removed = sorted(path for path in previous_snapshot if path not in current_snapshot)
    modified = sorted(
        path
        for path, meta in current_snapshot.items()
        if path in previous_snapshot
        and (
            meta.get("mtime_ns") != previous_snapshot[path].get("mtime_ns")
            or meta.get("size") != previous_snapshot[path].get("size")
        )
    )

    if not previous_snapshot:
        print("No baseline snapshot found yet. Treating current tracked files as newly seen.")
    print("Tracked changes")
    print(f"  added: {len(added)}")
    print(f"  modified: {len(modified)}")
    print(f"  removed: {len(removed)}")

    if added:
        print("")
        print("Added")
        for path in added:
            print(f"- {path}")
    if modified:
        print("")
        print("Modified")
        for path in modified:
            print(f"- {path}")
    if removed:
        print("")
        print("Removed")
        for path in removed:
            print(f"- {path}")
    if not added and not modified and not removed:
        print("")
        print("No tracked raw/knowledge changes since the last baseline.")

    if save_baseline:
        write_text(
            STATE_PATH,
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "files": current_snapshot,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        print("")
        print(f"Saved current file snapshot to {STATE_PATH.relative_to(ROOT).as_posix()}.")
    return 0


def command_lookup(data: dict[str, Any], query: str, limit: int = 5) -> int:
    wiki_notes: list[Note] = data["wiki_notes"]
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    edges = build_edges(data)

    route_candidates: list[tuple[float, Note]] = []
    for note in wiki_notes:
        if note.note_type not in {"index", "wiki"}:
            continue
        score = score_match(query, title=note.title, rel_path=note.rel_path, aliases=note.aliases, tags=note.tags, body=route_text(note))
        if score > 0:
            route_candidates.append((score, note))

    route_candidates.sort(key=lambda item: (-item[0], item[1].rel_path))
    routes = route_candidates[:limit]
    route_clusters = infer_route_clusters([note for _score, note in routes])
    knowledge_candidates: list[LookupMatch] = []
    for note in wiki_notes:
        if note.note_type not in {"wiki", "claim"}:
            continue
        if route_clusters and not note_in_clusters(note, route_clusters):
            continue
        best_match = best_lookup_match(query, note)
        if best_match:
            knowledge_candidates.append(best_match)
    knowledge_candidates.sort(key=lambda item: (-item.score, item.note.rel_path, item.section))
    knowledge_matches = knowledge_candidates[:limit]
    if not routes and not knowledge_matches:
        print(f"No matches found for: {query}")
        return 1

    print(f"Lookup: {query}")
    print("")
    print("Route matches")
    matched_paths = []
    if routes:
        for score, note in routes:
            matched_paths.append(note.rel_path)
            tags = ", ".join(note.tags) if note.tags else "-"
            print(
                f"- {note.title} | path={note.rel_path} | type={note.note_type or '-'} | status={note.status or '-'} | score={score:.1f} | tags={tags}"
            )
    else:
        print("- No route matches; searched across all wiki and claim notes.")

    if knowledge_matches:
        print("")
        print("Knowledge matches")
        for match in knowledge_matches:
            matched_paths.append(match.note.rel_path)
            tags = ", ".join(match.note.tags) if match.note.tags else "-"
            print(
                f"- {match.note.title} | path={match.note.rel_path} | type={match.note.note_type or '-'} | status={match.note.status or '-'} | score={match.score:.1f} | section={match.section} | tags={tags}"
            )

    related_matches = build_related_matches(
        matched_paths=matched_paths,
        knowledge_matches=knowledge_matches,
        edges=edges,
        node_specs=node_specs,
        limit=limit,
    )

    if related_matches:
        print("")
        print("Related knowledge")
        for match in related_matches:
            node = node_specs.get(match.path, {"title": match.path, "type": "unknown", "status": ""})
            kinds = ", ".join(match.kinds)
            print(
                f"- {node.get('title', match.path)} | path={match.path} | type={node.get('type', 'unknown')} | status={node.get('status', '-') or '-'} | via={kinds} | score={match.score}"
            )

    print("")
    print("Suggested next step")
    if knowledge_matches:
        primary = knowledge_matches[0].note
        print(f"- Start from `{primary.rel_path}` and follow its Claim/Source chain only when evidence verification is needed.")
    else:
        primary = routes[0][1]
        print(f"- Start from `{primary.rel_path}` and then inspect the matching Wiki/Claim notes in that cluster.")
    return 0


def command_impact(data: dict[str, Any], target_ref: str) -> int:
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    alias_map: dict[str, str | None] = data["alias_map"]
    target = resolve_reference(target_ref, alias_map, node_specs)
    if not target:
        print(f"Target not found: {target_ref}", file=sys.stderr)
        return 1

    edges = build_edges(data)
    impact = find_impacted_notes(target, edges, node_specs)
    node = node_specs.get(target, {})
    print(f"Impact: {node.get('title', target)}")
    print(f"  path: {target}")
    print(f"  type: {node.get('type', '-')}")
    print("")
    for label, key in (("Claims", "claims"), ("Wiki", "wiki"), ("Indexes", "indexes")):
        print(label)
        paths = impact[key]
        if not paths:
            print("- None")
            continue
        for path in paths:
            item = node_specs.get(path, {})
            print(f"- {item.get('title', path)} | path={path} | type={item.get('type', '-')}")
        print("")
    if node.get("type") == "source":
        print("Suggested sync order")
        print("1. Update the changed Source summary, anchors, and evidence scope.")
        print("2. Review impacted Claims before touching Wiki notes or Indexes.")
        print("3. Mark overturned Claims as disputed/outdated instead of deleting them.")
        print("4. Remove or rewrite outdated Claim content from affected Wiki notes.")
        print("5. Refresh affected Wiki explanations and claim refs, then update Indexes if navigation changed.")
    return 0


def command_status(data: dict[str, Any]) -> int:
    raw_items: list[RawItem] = data["raw_items"]
    wiki_notes: list[Note] = data["wiki_notes"]
    processed_raw_refs: set[str] = data["processed_raw_refs"]
    raw_statuses = Counter()
    raw_types = Counter()
    for item in raw_items:
        status = item.status or "inbox"
        if item.rel_path in processed_raw_refs:
            status = "processed"
        raw_statuses[status] += 1
        raw_types[item.source_type] += 1

    type_counts = Counter(note.note_type or "unknown" for note in wiki_notes)
    status_counts = Counter(note.status or "missing" for note in wiki_notes)

    print(f"Vault root: {ROOT}")
    print("")
    print("Raw items")
    print(f"  total: {len(raw_items)}")
    print(f"  pending: {raw_statuses.get('inbox', 0)}")
    print(f"  processed: {raw_statuses.get('processed', 0)}")
    for key in sorted(raw_types):
        print(f"  {key}: {raw_types[key]}")

    print("")
    print("Knowledge notes")
    print(f"  total: {len(wiki_notes)}")
    for key in sorted(type_counts):
        print(f"  {key}: {type_counts[key]}")

    print("")
    print("Wiki statuses")
    for key in sorted(status_counts):
        print(f"  {key}: {status_counts[key]}")

    return 0


def validate_notes(
    wiki_notes: list[Note],
    node_specs: dict[str, dict[str, Any]],
    alias_map: dict[str, str | None],
    all_notes: list[Note] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    note_by_path = {note.rel_path: note for note in wiki_notes}
    standalone_claims = find_standalone_claim_paths(all_notes or wiki_notes, node_specs, alias_map)

    def resolved_refs(refs: list[str]) -> list[str]:
        return [resolved for ref in refs if (resolved := resolve_reference(ref, alias_map, node_specs))]

    for note in wiki_notes:
        missing = [field for field in COMMON_WIKI_FIELDS if field not in note.frontmatter]
        if missing:
            errors.append(f"{note.rel_path}: missing frontmatter fields: {', '.join(missing)}")
        if note.note_type and note.note_type not in VALID_TYPES:
            errors.append(f"{note.rel_path}: invalid type '{note.note_type}'")
        if note.kind != "unknown" and note.note_type and note.note_type != note.kind:
            warnings.append(f"{note.rel_path}: type '{note.note_type}' does not match path-inferred type '{note.kind}'")
        if note.status and note.status not in VALID_STATUSES:
            errors.append(f"{note.rel_path}: invalid status '{note.status}'")
        if note.confidence is None:
            errors.append(f"{note.rel_path}: confidence must be a number between 0.0 and 1.0")
        elif not (0.0 <= note.confidence <= 1.0):
            errors.append(f"{note.rel_path}: confidence {note.confidence} is outside 0.0..1.0")

        for field in RELATION_FIELDS:
            for target in note.relations.get(field, []):
                resolved = resolve_reference(target, alias_map, node_specs)
                if not resolved:
                    errors.append(f"{note.rel_path}: {field} target not found: {target}")

        for ref in note.source_refs:
            resolved = resolve_reference(ref, alias_map, node_specs)
            if not resolved:
                errors.append(f"{note.rel_path}: source_refs target not found: {ref}")

        if note.note_type == "source":
            source_missing = [field for field in SOURCE_FIELDS if field not in note.frontmatter]
            if source_missing:
                errors.append(f"{note.rel_path}: missing source fields: {', '.join(source_missing)}")

        if note.note_type == "claim":
            if "_claims" in Path(note.rel_path).parts:
                warnings.append(f"{note.rel_path}: legacy claim directory '_claims' should be migrated to '命题'")
            claim_missing = [field for field in CLAIM_FIELDS if field not in note.frontmatter]
            if claim_missing:
                errors.append(f"{note.rel_path}: missing claim fields: {', '.join(claim_missing)}")
            support_state = as_string(note.frontmatter.get("support_state"))
            if support_state and support_state not in VALID_SUPPORT_STATES:
                errors.append(f"{note.rel_path}: invalid support_state '{support_state}'")
            verification_state = as_string(note.frontmatter.get("verification_state"))
            if verification_state and verification_state not in VALID_VERIFICATION_STATES:
                errors.append(f"{note.rel_path}: invalid verification_state '{verification_state}'")
            claim_status = as_string(note.frontmatter.get("claim_status"))
            if claim_status and claim_status not in VALID_CLAIM_STATUSES:
                errors.append(f"{note.rel_path}: invalid claim_status '{claim_status}'")
            graph_role = as_string(note.frontmatter.get("graph_role"))
            if graph_role and graph_role != STANDALONE_CLAIM_GRAPH_ROLE:
                errors.append(f"{note.rel_path}: invalid graph_role '{graph_role}'")
            if note.rel_path in standalone_claims and graph_role != STANDALONE_CLAIM_GRAPH_ROLE:
                errors.append(
                    f"{note.rel_path}: standalone claim must set graph_role to {STANDALONE_CLAIM_GRAPH_ROLE}"
                )
            if note.rel_path not in standalone_claims and graph_role == STANDALONE_CLAIM_GRAPH_ROLE:
                errors.append(
                    f"{note.rel_path}: claim absorbed by a wiki must not keep graph_role {STANDALONE_CLAIM_GRAPH_ROLE}"
                )
            for target in note.conflict_refs:
                resolved = resolve_reference(target, alias_map, node_specs)
                if not resolved:
                    errors.append(f"{note.rel_path}: conflict_refs target not found: {target}")
            for target in resolved_refs(note.conflict_refs):
                target_note = note_by_path.get(target)
                if target_note and note.rel_path not in resolved_refs(target_note.conflict_refs):
                    errors.append(f"{note.rel_path}: conflict_refs must be bidirectional with {target}")
                if not extract_section(note.body, "可能冲突或待验证"):
                    errors.append(f"{note.rel_path}: conflict_refs require ## 可能冲突或待验证 to describe the conflict")
            for target in resolved_refs(note.relations.get("contradicts", [])):
                target_note = note_by_path.get(target)
                if target_note and note.rel_path not in resolved_refs(target_note.relations.get("contradicts", [])):
                    errors.append(f"{note.rel_path}: contradicts must be bidirectional with {target}")

        if note.note_type == "wiki":
            wiki_missing = [field for field in WIKI_FIELDS if field not in note.frontmatter]
            if wiki_missing:
                errors.append(f"{note.rel_path}: missing wiki fields: {', '.join(wiki_missing)}")
            for field, refs in (("claim_refs", note.claim_refs), ("summary_claim_refs", note.summary_claim_refs)):
                for target in refs:
                    resolved = resolve_reference(target, alias_map, node_specs)
                    if not resolved:
                        errors.append(f"{note.rel_path}: {field} target not found: {target}")
                        continue
                    target_note = note_by_path.get(resolved)
                    if target_note and as_string(target_note.frontmatter.get("claim_status")) in {"outdated", "disputed"}:
                        errors.append(f"{note.rel_path}: active wiki {field} cannot point to inactive claim: {resolved}")

        for link in note.wikilinks:
            resolved = resolve_reference(link, alias_map, node_specs)
            if not resolved:
                errors.append(f"{note.rel_path}: broken wikilink: [[{link}]]")

        if note.review_after and is_stale(note.review_after):
            warnings.append(f"{note.rel_path}: review_after {note.review_after} is due or overdue")

    return errors, warnings


def command_lint(data: dict[str, Any], scope_path: str | None = None) -> int:
    scoped = resolve_scope(data, scope_path)
    wiki_notes: list[Note] = [
        note for note in data["wiki_notes"] if not scoped["is_scoped"] or note.rel_path in scoped["paths"]
    ]
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    alias_map: dict[str, str | None] = data["alias_map"]
    wiki_map: dict[str, Note] = data["wiki_map"]

    errors, warnings = validate_notes(wiki_notes, node_specs, alias_map, all_notes=data["wiki_notes"])

    edges = build_edges(data)
    incoming, outgoing = edge_counts(edges)
    for note in wiki_notes:
        if incoming[note.rel_path] == 0 and outgoing[note.rel_path] == 0:
            warnings.append(f"{note.rel_path}: orphan wiki note (no incoming or outgoing edges)")

    previous_manifest = load_json(LINK_MANIFEST_PATH)
    current_manifest = build_link_manifest(wiki_notes, alias_map, node_specs)
    if scoped["is_scoped"]:
        warnings.append("Scoped lint skipped protected-link snapshot comparison; run full lint/export after batch changes.")
    elif previous_manifest:
        warnings.extend(compare_manifests(previous_manifest, current_manifest, wiki_map))
    else:
        warnings.append(
            f"{LINK_MANIFEST_PATH.relative_to(ROOT).as_posix()}: no previous snapshot yet; run export to seed protected-link tracking"
        )

    if errors:
        print("Errors")
        for item in errors:
            print(f"- {item}")
        print("")
    if warnings:
        print("Warnings")
        for item in warnings:
            print(f"- {item}")
        print("")
    if not errors and not warnings:
        print("No lint findings.")
        return 0
    if errors:
        print(f"Lint failed with {len(errors)} error(s) and {len(warnings)} warning(s).")
        return 1
    print(f"Lint passed with {len(warnings)} warning(s).")
    return 0


def command_export(data: dict[str, Any]) -> int:
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    wiki_notes: list[Note] = data["wiki_notes"]
    alias_map: dict[str, str | None] = data["alias_map"]
    edges = build_edges(data)

    nodes = [node_specs[key] for key in sorted(node_specs)]
    edges_json = [{"source": edge.source, "target": edge.target, "kind": edge.kind} for edge in edges]
    graph_json = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "nodes": nodes,
        "edges": edges_json,
    }
    write_text(EXPORT_ROOT / "graph.json", json.dumps(graph_json, ensure_ascii=False, indent=2) + "\n")
    write_text(EXPORT_ROOT / "graph.graphml", build_graphml(nodes, edges))
    write_text(EXPORT_ROOT / "graph-summary.md", build_graph_summary(nodes, edges, wiki_notes))

    manifest = build_link_manifest(wiki_notes, alias_map, node_specs)
    write_text(LINK_MANIFEST_PATH, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write_text(
        STATE_PATH,
        json.dumps(
            {
                "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "files": data["file_snapshot"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    print(
        "Exported graph artifacts: "
        f"{len(nodes)} nodes, {len(edges)} edges, snapshots written to {LINK_MANIFEST_PATH.relative_to(ROOT).as_posix()} and {STATE_PATH.relative_to(ROOT).as_posix()}."
    )
    return 0


def command_compile_media(target_path: str, force: bool = False) -> int:
    path = Path(target_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"Media path not found: {target_path}", file=sys.stderr)
        return 1

    mode = infer_media_compile_mode(path)
    rel_path = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    if mode != VISUAL_MODE:
        print(
            f"Unsupported media compile path for v1: {rel_path}. Expected a file under raw/inbox/{VISUAL_MODE}/",
            file=sys.stderr,
        )
        return 1
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        print(f"Unsupported video extension: {path.suffix or '(none)'}", file=sys.stderr)
        return 1

    note_path = compiled_visual_note_path(path)
    asset_dir = compiled_visual_asset_dir(path)
    sidecar_path = compiled_visual_ocr_regions_path(path)
    command = [
        resolve_transfer_platform_executable(),
        "compile",
        "visual",
        str(path),
        "--markdown-path",
        str(note_path),
        "--sidecar-path",
        str(sidecar_path),
        "--assets-dir",
        str(asset_dir),
    ]
    if force:
        command.append("--force")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print((result.stderr or result.stdout).strip() or "transfer-platform compile failed", file=sys.stderr)
        return 1

    if result.stdout.strip():
        print(result.stdout.strip())
    print(f"Wrote {note_path.relative_to(ROOT).as_posix()}")
    print(f"Assets: {asset_dir.relative_to(ROOT).as_posix()}")
    print(f"Sidecar: {sidecar_path.relative_to(ROOT).as_posix()}")
    return 0


class LocalVisualCompileBackend:
    def __init__(self, max_interval_seconds: float = DEFAULT_VISUAL_MAX_INTERVAL_SECONDS) -> None:
        self.max_interval_seconds = max_interval_seconds
        self._ocr_engine: Any = None

    def probe(self, video_path: Path) -> MediaProbe:
        return probe_media_with_ffprobe(video_path)

    def select_timestamps(self, video_path: Path, probe: MediaProbe) -> list[float]:
        return detect_visual_timestamps(
            video_path,
            duration_seconds=probe.duration_seconds,
            max_interval_seconds=self.max_interval_seconds,
            max_frames=DEFAULT_VISUAL_MAX_FRAMES,
        )

    def extract_frame(self, video_path: Path, timestamp_seconds: float, output_path: Path) -> None:
        extract_frame_with_ffmpeg(video_path, timestamp_seconds, output_path)

    def ocr_image(self, image_path: Path) -> Any:
        if self._ocr_engine is None:
            try:
                from rapidocr import RapidOCR
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "Missing Python dependency for OCR. Install rapidocr and onnxruntime inside .venv."
                ) from exc
            self._ocr_engine = RapidOCR()
        return self._ocr_engine(str(image_path))

    def frame_fingerprint(self, image_path: Path) -> str:
        return default_visual_frame_fingerprint(image_path)


def compile_video_visual_raw_item(
    video_path: Path,
    *,
    force: bool = False,
    backend: Any | None = None,
    generated_at: datetime | None = None,
) -> VisualCompileArtifact:
    backend = backend or LocalVisualCompileBackend()
    if infer_media_compile_mode(video_path) != VISUAL_MODE:
        raise ValueError(
            f"video-visual compilation expects a file under raw/inbox/{VISUAL_MODE}/, got {video_path.relative_to(ROOT).as_posix()}"
        )
    if video_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video extension: {video_path.suffix or '(none)'}")

    note_path = compiled_visual_note_path(video_path)
    asset_dir = compiled_visual_asset_dir(video_path)
    sidecar_path = compiled_visual_ocr_regions_path(video_path)
    if note_path.exists() and not force:
        raise FileExistsError(
            f"Generated markdown already exists: {note_path.relative_to(ROOT).as_posix()} (rerun with --force to overwrite)"
        )

    probe = backend.probe(video_path)
    if not probe.has_video:
        raise ValueError(f"Media file has no video stream: {video_path.relative_to(ROOT).as_posix()}")

    timestamps = normalize_visual_timestamps(backend.select_timestamps(video_path, probe))
    if not timestamps:
        timestamps = [0.0]

    frames: list[VisualFrameRecord] = []
    anchor_counter = 1
    last_fingerprint = ""
    for candidate_index, timestamp_seconds in enumerate(timestamps, start=1):
        candidate_path = asset_dir / f".candidate-{candidate_index:04d}-{format_timestamp_token(timestamp_seconds)}.png"
        final_image_path = asset_dir / visual_frame_filename(len(frames) + 1, timestamp_seconds)
        regions: list[VisualRegionRecord] = []
        error = ""
        try:
            backend.extract_frame(video_path, timestamp_seconds, candidate_path)
        except Exception as exc:  # pragma: no cover
            error = f"Frame extraction failed: {exc}"
        else:
            fingerprint = get_visual_frame_fingerprint(backend, candidate_path)
            if frames and fingerprint == last_fingerprint:
                frames[-1].cover_end_seconds = timestamp_seconds
                if candidate_path.exists():
                    candidate_path.unlink()
                continue
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            candidate_path.replace(final_image_path)
            try:
                regions = filter_visual_ocr_regions(
                    normalize_ocr_regions(
                        backend.ocr_image(final_image_path) or [],
                        frame_width=probe.width,
                        frame_height=probe.height,
                    )
                )
            except Exception as exc:  # pragma: no cover
                error = f"OCR failed: {exc}"
            last_fingerprint = fingerprint
        anchors, anchor_counter = build_visual_anchor_records(regions, error=error, start=anchor_counter)
        frames.append(
            VisualFrameRecord(
                index=len(frames) + 1,
                cover_start_seconds=timestamp_seconds,
                cover_end_seconds=timestamp_seconds,
                rel_image_path=final_image_path.relative_to(ROOT).as_posix(),
                regions=regions,
                anchors=anchors,
                error=error,
            )
        )

    generated_at = generated_at or datetime.now(UTC)
    sidecar = build_visual_ocr_sidecar(video_path, frames, generated_at=generated_at)
    content = render_visual_source_markdown(video_path, probe, frames, generated_at=generated_at)
    write_text(sidecar_path, json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n")
    write_text(note_path, content)
    return VisualCompileArtifact(note_path=note_path, asset_dir=asset_dir, sidecar_path=sidecar_path, frame_count=len(frames))


def build_edges(data: dict[str, Any]) -> list[Edge]:
    wiki_notes: list[Note] = data["wiki_notes"]
    alias_map: dict[str, str | None] = data["alias_map"]
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    edges: list[Edge] = []
    seen: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target_ref: str, kind: str) -> None:
        target = resolve_reference(target_ref, alias_map, node_specs)
        if not target:
            return
        key = (source, target, kind)
        if key not in seen:
            seen.add(key)
            edges.append(Edge(source=source, target=target, kind=kind))

    for note in wiki_notes:
        for link in note.wikilinks:
            add_edge(note.rel_path, link, "wikilink")
        for ref in note.source_refs:
            add_edge(note.rel_path, ref, "source_ref")
        for field in RELATION_FIELDS:
            for ref in note.relations.get(field, []):
                add_edge(note.rel_path, ref, field)
        for ref in note.claim_refs:
            add_edge(note.rel_path, ref, "claim_ref")
        for ref in note.summary_claim_refs:
            add_edge(note.rel_path, ref, "summary_claim_ref")
        for ref in note.conflict_refs:
            add_edge(note.rel_path, ref, "conflict_ref")
    return sorted(edges, key=lambda edge: (edge.kind, edge.source, edge.target))


def edge_counts(edges: list[Edge]) -> tuple[Counter, Counter]:
    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    for edge in edges:
        outgoing[edge.source] += 1
        incoming[edge.target] += 1
    return incoming, outgoing


def adjacency(edges: list[Edge]) -> tuple[defaultdict[str, list[Edge]], defaultdict[str, list[Edge]]]:
    incoming: defaultdict[str, list[Edge]] = defaultdict(list)
    outgoing: defaultdict[str, list[Edge]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.source].append(edge)
        incoming[edge.target].append(edge)
    return incoming, outgoing


def find_impacted_notes(target: str, edges: list[Edge], node_specs: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    incoming, outgoing = adjacency(edges)

    def node_type(path: str) -> str:
        return as_string(node_specs.get(path, {}).get("type"))

    claims: set[str] = set()
    wiki: set[str] = set()
    indexes: set[str] = set()

    target_type = node_type(target)
    if target_type == "source":
        for edge in incoming.get(target, []):
            if node_type(edge.source) == "claim":
                claims.add(edge.source)
    elif target_type == "claim":
        claims.add(target)
    elif target_type == "wiki":
        wiki.add(target)
    elif target_type == "index":
        indexes.add(target)

    for claim in list(claims):
        for edge in incoming.get(claim, []):
            if node_type(edge.source) == "wiki":
                wiki.add(edge.source)

    for wiki_path in list(wiki):
        for edge in incoming.get(wiki_path, []):
            if node_type(edge.source) == "index":
                indexes.add(edge.source)
        for edge in outgoing.get(wiki_path, []):
            if node_type(edge.target) == "index":
                indexes.add(edge.target)

    return {
        "claims": sorted(claims),
        "wiki": sorted(wiki),
        "indexes": sorted(indexes),
    }


def build_graph_summary(nodes: list[dict[str, Any]], edges: list[Edge], wiki_notes: list[Note]) -> str:
    type_counts = Counter(node["type"] for node in nodes)
    status_counts = Counter(node["status"] for node in nodes if node["status"])
    incoming, outgoing = edge_counts(edges)
    note_paths = {note.rel_path for note in wiki_notes}
    top_notes = sorted(
        (
            (path, incoming[path] + outgoing[path])
            for path in incoming.keys() | outgoing.keys()
            if path in note_paths
        ),
        key=lambda item: (-item[1], item[0]),
    )[:10]
    stale_notes = [note.rel_path for note in wiki_notes if note.review_after and is_stale(note.review_after)]
    orphan_notes = [
        note.rel_path
        for note in wiki_notes
        if incoming[note.rel_path] == 0 and outgoing[note.rel_path] == 0
    ]

    lines = [
        "# Graph Summary",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "## Counts",
        f"- Nodes: {len(nodes)}",
        f"- Edges: {len(edges)}",
        "",
        "## Node Types",
    ]
    for key in sorted(type_counts):
        lines.append(f"- {key}: {type_counts[key]}")
    lines.extend(["", "## Statuses"])
    for key in sorted(status_counts):
        lines.append(f"- {key}: {status_counts[key]}")
    lines.extend(["", "## Top Linked Notes"])
    if top_notes:
        for path, score in top_notes:
            lines.append(f"- `{path}`: {score}")
    else:
        lines.append("- No linked wiki notes yet.")
    lines.extend(["", "## Health Signals"])
    lines.append(f"- Stale wiki notes: {len(stale_notes)}")
    lines.append(f"- Orphan wiki notes: {len(orphan_notes)}")
    return "\n".join(lines).rstrip() + "\n"


def build_graphml(nodes: list[dict[str, Any]], edges: list[Edge]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="title" for="node" attr.name="title" attr.type="string"/>',
        '  <key id="path" for="node" attr.name="path" attr.type="string"/>',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="status" for="node" attr.name="status" attr.type="string"/>',
        '  <key id="tags" for="node" attr.name="tags" attr.type="string"/>',
        '  <key id="aliases" for="node" attr.name="aliases" attr.type="string"/>',
        '  <key id="confidence" for="node" attr.name="confidence" attr.type="string"/>',
        '  <key id="kind" for="edge" attr.name="kind" attr.type="string"/>',
        '  <graph id="G" edgedefault="directed">',
    ]
    for node in nodes:
        lines.append(f'    <node id="{xml_escape(node["id"])}">')
        for key in ("title", "path", "type", "status"):
            lines.append(f'      <data key="{key}">{xml_escape(str(node.get(key, "")))}</data>')
        lines.append(f'      <data key="tags">{xml_escape(", ".join(node.get("tags", [])))}</data>')
        lines.append(f'      <data key="aliases">{xml_escape(", ".join(node.get("aliases", [])))}</data>')
        confidence = "" if node.get("confidence") is None else str(node["confidence"])
        lines.append(f'      <data key="confidence">{xml_escape(confidence)}</data>')
        lines.append("    </node>")
    for index, edge in enumerate(edges):
        lines.append(
            f'    <edge id="e{index}" source="{xml_escape(edge.source)}" target="{xml_escape(edge.target)}">'
        )
        lines.append(f'      <data key="kind">{xml_escape(edge.kind)}</data>')
        lines.append("    </edge>")
    lines.extend(["  </graph>", "</graphml>"])
    return "\n".join(lines) + "\n"


def build_link_manifest(
    wiki_notes: list[Note], alias_map: dict[str, str | None], node_specs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for note in wiki_notes:
        resolved_links = sorted(
            filter(None, (resolve_reference(link, alias_map, node_specs) for link in note.wikilinks))
        )
        relations = {
            field: sorted(
                filter(None, (resolve_reference(target, alias_map, node_specs) for target in note.relations.get(field, [])))
            )
            for field in RELATION_FIELDS
        }
        claim_links = {
            "claim_refs": sorted(filter(None, (resolve_reference(target, alias_map, node_specs) for target in note.claim_refs))),
            "summary_claim_refs": sorted(
                filter(None, (resolve_reference(target, alias_map, node_specs) for target in note.summary_claim_refs))
            ),
            "conflict_refs": sorted(
                filter(None, (resolve_reference(target, alias_map, node_specs) for target in note.conflict_refs))
            ),
        }
        files[note.rel_path] = {
            "wikilinks": resolved_links,
            "relations": relations,
            "claim_links": claim_links,
        }
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "files": files,
    }


def build_file_snapshot(raw_items: list[RawItem], wiki_notes: list[Note]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    tracked_paths = [item.path for item in raw_items] + [note.path for note in wiki_notes]
    for path in tracked_paths:
        stat = path.stat()
        rel_path = path.relative_to(ROOT).as_posix()
        snapshot[rel_path] = {
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }
    return snapshot


def compare_manifests(
    previous_manifest: dict[str, Any], current_manifest: dict[str, Any], wiki_map: dict[str, Note]
) -> list[str]:
    warnings: list[str] = []
    prev_files = previous_manifest.get("files", {})
    curr_files = current_manifest.get("files", {})
    for path, prev_data in sorted(prev_files.items()):
        if path not in wiki_map:
            warnings.append(f"{path}: note existed in previous link snapshot but is missing now")
            continue
        curr_data = curr_files.get(
            path,
            {
                "wikilinks": [],
                "relations": {field: [] for field in RELATION_FIELDS},
                "claim_links": {field: [] for field in CLAIM_REF_FIELDS},
            },
        )
        prev_links = set(prev_data.get("wikilinks", []))
        curr_links = set(curr_data.get("wikilinks", []))
        missing_links = sorted(prev_links - curr_links)
        if missing_links:
            warnings.append(f"{path}: protected wikilinks missing since last export: {', '.join(missing_links)}")
        prev_relations = prev_data.get("relations", {})
        curr_relations = curr_data.get("relations", {})
        for field in RELATION_FIELDS:
            missing_relation_targets = sorted(set(prev_relations.get(field, [])) - set(curr_relations.get(field, [])))
            if missing_relation_targets:
                warnings.append(
                    f"{path}: protected relation targets missing for {field}: {', '.join(missing_relation_targets)}"
                )
        prev_claim_links = prev_data.get("claim_links", {})
        curr_claim_links = curr_data.get("claim_links", {})
        for field in CLAIM_REF_FIELDS:
            missing_claim_targets = sorted(set(prev_claim_links.get(field, [])) - set(curr_claim_links.get(field, [])))
            if missing_claim_targets:
                warnings.append(f"{path}: protected claim targets missing for {field}: {', '.join(missing_claim_targets)}")
    return warnings


def load_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    return parse_frontmatter(frontmatter), body


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return "", text
    frontmatter = parts[0][4:]
    body = parts[1]
    return frontmatter, body


def parse_frontmatter(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        list_match = re.match(r"^\s*-\s+(.*)$", line)
        if list_match and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(parse_scalar(list_match.group(1).strip()))
            continue
        key_match = re.match(r"^([A-Za-z0-9_-]+):(.*)$", line)
        if not key_match:
            current_key = None
            continue
        key, rest = key_match.group(1), key_match.group(2).strip()
        if not rest:
            data[key] = []
            current_key = key
            continue
        data[key] = parse_scalar(rest)
        current_key = None
    return data


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def find_standalone_claim_paths(
    notes: list[Note],
    node_specs: dict[str, dict[str, Any]],
    alias_map: dict[str, str | None],
) -> set[str]:
    absorbed_claims: set[str] = set()
    claim_paths = {note.rel_path for note in notes if note.note_type == "claim"}
    for note in notes:
        if note.note_type != "wiki":
            continue
        for ref in [*note.claim_refs, *note.summary_claim_refs]:
            resolved = resolve_reference(ref, alias_map, node_specs)
            if resolved:
                absorbed_claims.add(resolved)
    return {path for path in claim_paths if path not in absorbed_claims}


def extract_wikilinks(text: str) -> list[str]:
    links = []
    for match in re.findall(r"\[\[([^\]]+)\]\]", text):
        target = match.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            links.append(target)
    return links


def extract_section(body: str, heading: str) -> str:
    lines = body.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            in_section = stripped == f"## {heading}"
            continue
        if in_section:
            collected.append(line)
    return "\n".join(collected).strip()


def extract_top_level_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is not None:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append((current_heading, content))
            current_heading = stripped[3:].strip()
            current_lines = []
            continue
        if current_heading is not None:
            current_lines.append(line)
    if current_heading is not None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_heading, content))
    return sections


def extract_callout(body: str, title: str) -> str:
    lines = body.splitlines()
    collected: list[str] = []
    in_callout = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("> [!") and title in stripped:
            in_callout = True
            continue
        if in_callout:
            if stripped.startswith(">"):
                collected.append(stripped[1:].strip())
                continue
            if stripped:
                break
    return "\n".join(line for line in collected if line).strip()


def body_preview(body: str, limit: int = 1200) -> str:
    text = re.sub(r"^---\n.*?\n---\n", "", body, flags=re.DOTALL)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def route_text(note: Note) -> str:
    fields = [
        extract_callout(note.body, "快速把握"),
        extract_section(note.body, "摘要"),
        as_string(note.frontmatter.get("core_focus")),
        as_string(note.frontmatter.get("core_question")),
        as_string(note.frontmatter.get("page_intent")),
        as_string(note.frontmatter.get("statement")),
        body_preview(note.body, limit=600),
    ]
    fields.extend(as_string(value) for value in listify(note.frontmatter.get("aliases")))
    fields.extend(as_string(value) for value in listify(note.frontmatter.get("tags")))
    return "\n".join(value for value in fields if value)


def knowledge_lookup_text(note: Note) -> str:
    fields = [
        route_text(note),
        as_string(note.frontmatter.get("scope")),
        as_string(note.frontmatter.get("boundary_note")),
        extract_section(note.body, "当前证据如何支撑"),
        extract_section(note.body, "适用边界"),
        extract_section(note.body, "主线解释"),
    ]
    return "\n".join(value for value in fields if value)


def claim_lookup_text(note: Note) -> str:
    fields = [
        route_text(note),
        as_string(note.frontmatter.get("support_state")),
        as_string(note.frontmatter.get("verification_state")),
        as_string(note.frontmatter.get("scope")),
        as_string(note.frontmatter.get("boundary_note")),
        extract_section(note.body, "当前证据如何支撑"),
        extract_section(note.body, "适用边界"),
        extract_section(note.body, "可能冲突或待验证"),
    ]
    return "\n".join(value for value in fields if value)


def build_lookup_units(note: Note) -> list[LookupUnit]:
    if note.note_type == "claim":
        text = claim_lookup_text(note)
        return [LookupUnit(note_path=note.rel_path, note_type="claim", section="claim", text=text)] if text else []
    if note.note_type != "wiki":
        return []

    units: list[LookupUnit] = []
    seen_sections: set[str] = set()
    quick_take = extract_callout(note.body, "快速把握")
    if quick_take:
        units.append(LookupUnit(note_path=note.rel_path, note_type="wiki", section="快速把握", text=quick_take))
        seen_sections.add("快速把握")

    for heading, content in extract_top_level_sections(note.body):
        if heading in {"用户提问与复盘"} or heading in seen_sections:
            continue
        units.append(LookupUnit(note_path=note.rel_path, note_type="wiki", section=heading, text=content))
        seen_sections.add(heading)

    preview = body_preview(note.body, limit=900)
    if preview:
        units.append(LookupUnit(note_path=note.rel_path, note_type="wiki", section="正文预览", text=preview))
    return units


def lookup_section_priority(note_type: str, section: str) -> int:
    if note_type == "claim":
        return 0
    priorities = {
        "快速把握": 0,
        "主线解释": 1,
        "先把这三个东西分开": 2,
        "为什么这条边界决定你会不会走错路": 3,
        "检索到底是怎么发生的": 4,
        "Chunking 为什么会直接决定上限": 5,
        "什么时候该用 RAG，什么时候不该": 6,
        "最容易混淆的几个地方": 7,
        "它和哪些知识要一起看": 8,
        "当前证据如何支撑": 9,
        "适用边界": 10,
        "证据来源": 20,
        "正文预览": 30,
    }
    return priorities.get(section, 15)


def best_lookup_match(query: str, note: Note) -> LookupMatch | None:
    best: LookupMatch | None = None
    for unit in build_lookup_units(note):
        score = score_match(
            query,
            title=note.title,
            rel_path=note.rel_path,
            aliases=note.aliases,
            tags=note.tags,
            body=unit.text,
        )
        if score <= 0:
            continue
        candidate = LookupMatch(note=note, score=score, section=unit.section)
        if best is None:
            best = candidate
            continue
        candidate_key = (candidate.score, -lookup_section_priority(note.note_type or "", candidate.section), candidate.section)
        best_key = (best.score, -lookup_section_priority(note.note_type or "", best.section), best.section)
        if candidate_key > best_key:
            best = candidate
    return best


def build_related_matches(
    matched_paths: list[str],
    knowledge_matches: list[LookupMatch],
    edges: list[Edge],
    node_specs: dict[str, dict[str, Any]],
    limit: int,
) -> list[RelatedMatch]:
    incoming, outgoing = adjacency(edges)
    matched_set = set(matched_paths)
    conflict_kinds = {"conflict_ref", "contradicts"}
    related_scores: Counter[str] = Counter()
    related_kinds: defaultdict[str, set[str]] = defaultdict(set)
    forced_conflicts: set[str] = set()
    matched_claim_paths = {match.note.rel_path for match in knowledge_matches if match.note.note_type == "claim"}

    for path in matched_paths:
        for edge in outgoing.get(path, []):
            if edge.kind in conflict_kinds:
                if path in matched_claim_paths and edge.target not in matched_set:
                    forced_conflicts.add(edge.target)
                continue
            if edge.target not in matched_set:
                related_scores[edge.target] += edge_weight(edge.kind)
                related_kinds[edge.target].add(edge.kind)
        for edge in incoming.get(path, []):
            if edge.kind in conflict_kinds:
                if path in matched_claim_paths and edge.source not in matched_set:
                    forced_conflicts.add(edge.source)
                continue
            if edge.source not in matched_set:
                related_scores[edge.source] += edge_weight(edge.kind)
                related_kinds[edge.source].add(edge.kind)

    ordered = sorted(
        (
            RelatedMatch(path=path, score=score, kinds=tuple(sorted(related_kinds[path])))
            for path, score in related_scores.items()
            if node_specs.get(path, {}).get("type") not in {"raw", "source"}
        ),
        key=lambda item: (-item.score, item.path),
    )

    selected: list[RelatedMatch] = ordered[:limit]
    selected_paths = {item.path for item in selected}
    for path in sorted(forced_conflicts):
        if path in selected_paths:
            continue
        if node_specs.get(path, {}).get("type") in {"raw", "source"}:
            continue
        selected.append(
            RelatedMatch(
                path=path,
                score=sum(
                    edge_weight(edge.kind)
                    for edge in [*incoming.get(path, []), *outgoing.get(path, [])]
                    if edge.kind in conflict_kinds and (edge.source in matched_claim_paths or edge.target in matched_claim_paths)
                ),
                kinds=tuple(sorted(conflict_kinds & ({edge.kind for edge in incoming.get(path, [])} | {edge.kind for edge in outgoing.get(path, [])}))),
            )
        )
        selected_paths.add(path)
    return selected


def infer_route_clusters(notes: list[Note]) -> set[str]:
    clusters: set[str] = set()
    for note in notes:
        parts = Path(note.rel_path).parts
        if len(parts) >= 2 and parts[0] == "知识簇":
            clusters.add(parts[1])
    return clusters


def note_in_clusters(note: Note, clusters: set[str]) -> bool:
    parts = Path(note.rel_path).parts
    if len(parts) >= 2 and parts[0] == "知识簇":
        return parts[1] in clusters
    if note.note_type != "claim":
        return False
    related_refs: list[str] = []
    for field in RELATION_FIELDS:
        related_refs.extend(note.relations.get(field, []))
    related_refs.extend(note.claim_refs)
    related_refs.extend(note.summary_claim_refs)
    related_refs.extend(note.conflict_refs)
    for ref in related_refs:
        ref_parts = Path(ref).parts
        if len(ref_parts) >= 2 and ref_parts[0] == "知识簇" and ref_parts[1] in clusters:
            return True
    return False


def tokenize_query(value: str) -> list[str]:
    tokens = re.split(r"[\s/,_\-]+", value.lower())
    stopwords = {
        "a",
        "an",
        "and",
        "for",
        "from",
        "have",
        "in",
        "into",
        "is",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
    return [token for token in tokens if token and token not in stopwords]


def score_match(query: str, title: str, rel_path: str, aliases: list[str], tags: list[str], body: str) -> float:
    normalized_query = normalize_ref(query)
    query_tokens = tokenize_query(query)
    haystacks = [
        normalize_ref(title),
        normalize_ref(rel_path),
        *(normalize_ref(alias) for alias in aliases),
        *(normalize_ref(tag) for tag in tags),
    ]
    body_text = body.lower()
    score = 0.0
    if not normalized_query and not query_tokens:
        return score
    if normalized_query:
        if any(text == normalized_query for text in haystacks):
            score += 100
        elif any(normalized_query in text for text in haystacks):
            score += 45
        elif normalized_query in body_text:
            score += 15
    for token in query_tokens:
        if len(token) < 2:
            continue
        if any(text == token for text in haystacks):
            score += 20
        elif any(token in text for text in haystacks):
            score += 10
        elif token in body_text:
            score += 3
    return score


def edge_weight(kind: str) -> int:
    if kind in {"supports", "depends_on", "contradicts", "part_of"}:
        return 4
    if kind in {"summary_claim_ref", "conflict_ref"}:
        return 4
    if kind == "claim_ref":
        return 3
    if kind == "see_also":
        return 3
    if kind in {"wikilink", "source_ref"}:
        return 2
    return 1


def infer_media_compile_mode(path: Path) -> str | None:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return None
    if len(relative.parts) < 3 or relative.parts[0] != "raw" or relative.parts[1] != "inbox":
        return None
    mode = relative.parts[2]
    return mode if mode in MEDIA_COMPILE_MODES else None


def compiled_visual_note_path(video_path: Path) -> Path:
    mode_root = RAW_ROOT / "inbox" / VISUAL_MODE
    relative = video_path.relative_to(mode_root).with_suffix("")
    note_dir = RAW_ROOT / "compiled" / "visual"
    for part in relative.parts[:-1]:
        note_dir /= sanitize_filename(part)
    return note_dir / f"{sanitize_filename(relative.name)}（视觉编译）.md"


def compiled_visual_asset_dir(video_path: Path) -> Path:
    mode_root = RAW_ROOT / "inbox" / VISUAL_MODE
    relative = video_path.relative_to(mode_root).with_suffix("")
    asset_dir = RAW_ROOT / "assets" / VISUAL_MODE
    for part in relative.parts[:-1]:
        asset_dir /= sanitize_filename(part)
    return asset_dir / sanitize_filename(relative.name)


def compiled_visual_ocr_regions_path(video_path: Path) -> Path:
    return compiled_visual_asset_dir(video_path) / "ocr_regions.json"


def visual_frame_filename(index: int, timestamp_seconds: float) -> str:
    return f"frame-{index:04d}-{format_timestamp_token(timestamp_seconds)}.png"


def format_timestamp_token(value: float) -> str:
    total_milliseconds = max(0, int(round(value * 1000)))
    hours, rem = divmod(total_milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, milliseconds = divmod(rem, 1000)
    return f"{hours:02d}-{minutes:02d}-{seconds:02d}-{milliseconds:03d}"


def format_timestamp(value: float) -> str:
    return format_timestamp_token(value).replace("-", ":", 2).replace("-", ".", 1)


def normalize_visual_timestamps(values: list[float]) -> list[float]:
    seen: set[int] = set()
    normalized: list[float] = []
    for value in sorted(max(0.0, float(item)) for item in values):
        milliseconds = int(round(value * 1000))
        if milliseconds in seen:
            continue
        seen.add(milliseconds)
        normalized.append(milliseconds / 1000.0)
    return normalized


def probe_media_with_ffprobe(video_path: Path) -> MediaProbe:
    ffprobe_path = require_executable("ffprobe", install_hint="brew install ffmpeg")
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video_path.name}: {result.stderr.strip() or result.stdout.strip()}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned invalid JSON for {video_path.name}") from exc

    streams = payload.get("streams", [])
    duration_seconds = to_float(payload.get("format", {}).get("duration")) or 0.0
    width: int | None = None
    height: int | None = None
    has_audio = False
    has_video = False
    for stream in streams:
        codec_type = as_string(stream.get("codec_type"))
        if codec_type == "video":
            has_video = True
            width = width or (int(stream["width"]) if stream.get("width") is not None else None)
            height = height or (int(stream["height"]) if stream.get("height") is not None else None)
        elif codec_type == "audio":
            has_audio = True
    return MediaProbe(
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        has_audio=has_audio,
        has_video=has_video,
    )


def detect_visual_timestamps(
    video_path: Path,
    *,
    duration_seconds: float,
    max_interval_seconds: float = DEFAULT_VISUAL_MAX_INTERVAL_SECONDS,
    max_frames: int = DEFAULT_VISUAL_MAX_FRAMES,
) -> list[float]:
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Missing Python dependency for scene detection. Install scenedetect inside .venv.") from exc

    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    timestamps: list[float] = []
    if scene_list:
        for start_time, end_time in scene_list:
            start_seconds = max(0.0, float(start_time.get_seconds()))
            end_seconds = max(start_seconds, float(end_time.get_seconds()))
            timestamps.append(start_seconds)
            cursor = start_seconds + max_interval_seconds
            while max_interval_seconds > 0 and cursor < end_seconds - 0.25:
                timestamps.append(cursor)
                cursor += max_interval_seconds
    else:
        timestamps.append(0.0)

    if duration_seconds > 0 and timestamps:
        last_timestamp = max(timestamps)
        cursor = last_timestamp + max_interval_seconds
        while max_interval_seconds > 0 and cursor < duration_seconds - 0.25:
            timestamps.append(cursor)
            cursor += max_interval_seconds

    timestamps = normalize_visual_timestamps(timestamps or [0.0])
    if len(timestamps) <= max_frames:
        return timestamps
    if max_frames <= 1:
        return [timestamps[0]]

    selected = [timestamps[0]]
    for index in range(1, max_frames - 1):
        source_index = round(index * (len(timestamps) - 1) / (max_frames - 1))
        selected.append(timestamps[source_index])
    selected.append(timestamps[-1])
    return normalize_visual_timestamps(selected)


def extract_frame_with_ffmpeg(video_path: Path, timestamp_seconds: float, output_path: Path) -> None:
    ffmpeg_path = require_executable("ffmpeg", install_hint="brew install ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp_seconds:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "ffmpeg frame extraction failed")


def normalize_ocr_lines(result: Any) -> list[str]:
    return [region["text"] for region in normalize_ocr_regions(result)]


def normalize_ocr_regions(
    result: Any,
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> list[dict[str, Any]]:
    candidate = result[0] if isinstance(result, tuple) and result else result
    if candidate is None:
        return []

    parsed_items: list[dict[str, Any]] = []
    if hasattr(candidate, "txts"):
        texts = list(getattr(candidate, "txts", []) or [])
        scores = list(getattr(candidate, "scores", []) or [])
        boxes = list(getattr(candidate, "boxes", []) or [])
        for index, text in enumerate(texts):
            parsed_items.append(
                {
                    "text": text,
                    "score": scores[index] if index < len(scores) else None,
                    "bbox": boxes[index] if index < len(boxes) else None,
                }
            )
    elif isinstance(candidate, list):
        for item in candidate:
            parsed = parse_ocr_region_item(item)
            if parsed:
                parsed_items.append(parsed)
    else:
        text = as_string(candidate)
        if text:
            parsed_items.append({"text": text, "bbox": None, "score": None})

    normalized: list[dict[str, Any]] = []
    for item in parsed_items:
        text = normalize_ocr_text(as_string(item.get("text")))
        if not text:
            continue
        bbox, bbox_missing = normalize_region_bbox(
            item.get("bbox"),
            frame_width=frame_width,
            frame_height=frame_height,
        )
        normalized.append(
            {
                "text": text,
                "bbox": bbox,
                "bbox_missing": bbox_missing,
                "score": to_float(item.get("score")),
            }
        )
    return normalized


def parse_ocr_region_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return {
            "text": item.get("text") or item.get("txt") or item.get("content"),
            "bbox": item.get("bbox") or item.get("box") or item.get("points"),
            "score": item.get("score") or item.get("confidence"),
        }
    if isinstance(item, str):
        return {"text": item, "bbox": None, "score": None}
    if not isinstance(item, (list, tuple)) or not item:
        return None
    if len(item) >= 3 and isinstance(item[1], str):
        return {"bbox": item[0], "text": item[1], "score": item[2]}
    if isinstance(item[0], str):
        bbox = None
        score = None
        if len(item) >= 2:
            if isinstance(item[1], (list, tuple, dict)):
                bbox = item[1]
            else:
                score = to_float(item[1])
        if len(item) >= 3:
            if bbox is None and isinstance(item[2], (list, tuple, dict)):
                bbox = item[2]
            elif score is None:
                score = to_float(item[2])
        return {"text": item[0], "bbox": bbox, "score": score}
    return None


def normalize_region_bbox(
    raw_bbox: Any,
    *,
    frame_width: int | None,
    frame_height: int | None,
) -> tuple[list[float], bool]:
    coords: list[tuple[float, float]] = []
    if isinstance(raw_bbox, dict):
        if all(key in raw_bbox for key in ("x1", "y1", "x2", "y2")):
            coords = [
                (float(raw_bbox["x1"]), float(raw_bbox["y1"])),
                (float(raw_bbox["x2"]), float(raw_bbox["y2"])),
            ]
    elif isinstance(raw_bbox, (list, tuple)):
        if len(raw_bbox) == 4 and all(is_number(value) for value in raw_bbox):
            coords = [(float(raw_bbox[0]), float(raw_bbox[1])), (float(raw_bbox[2]), float(raw_bbox[3]))]
        else:
            for point in raw_bbox:
                if isinstance(point, (list, tuple)) and len(point) >= 2 and is_number(point[0]) and is_number(point[1]):
                    coords.append((float(point[0]), float(point[1])))
    if not coords:
        return [0.0, 0.0, 1.0, 1.0], True

    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]
    if max(abs(value) for value in (*xs, *ys)) > 1.5 and frame_width and frame_height:
        xs = [value / frame_width for value in xs]
        ys = [value / frame_height for value in ys]

    bbox = [
        round(min(max(min(xs), 0.0), 1.0), 4),
        round(min(max(min(ys), 0.0), 1.0), 4),
        round(min(max(max(xs), 0.0), 1.0), 4),
        round(min(max(max(ys), 0.0), 1.0), 4),
    ]
    return bbox, False


def is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def filter_visual_ocr_lines(lines: list[str]) -> list[str]:
    filtered: list[str] = []
    for line in lines:
        text = normalize_ocr_text(line)
        if not text:
            continue
        if is_visual_ocr_noise(text):
            continue
        filtered.append(text)
    return dedupe_preserve_order(filtered)


def filter_visual_ocr_regions(regions: list[dict[str, Any]]) -> list[VisualRegionRecord]:
    filtered: list[VisualRegionRecord] = []
    seen: set[tuple[str, tuple[float, ...]]] = set()
    for item in regions:
        text = normalize_ocr_text(as_string(item.get("text")))
        if not text or is_visual_ocr_noise(text):
            continue
        bbox = [round(float(value), 4) for value in list(item.get("bbox") or [0.0, 0.0, 1.0, 1.0])[:4]]
        bbox_key = tuple(bbox)
        key = (text, bbox_key)
        if key in seen:
            continue
        review = ""
        if maybe_visual_ocr_noise(text):
            review = "maybe_noise"
        score = to_float(item.get("score"))
        if not review and score is not None and score < 0.6:
            review = "ocr_unclear"
        if not review and bool(item.get("bbox_missing")):
            review = "layout_unclear"
        filtered.append(
            VisualRegionRecord(
                region_id=f"r{len(filtered) + 1:02d}",
                bbox=bbox,
                text=text,
                order=len(filtered) + 1,
                review=review,
            )
        )
        seen.add(key)
    return filtered


def normalize_ocr_text(value: str) -> str:
    text = re.sub(r"\s+", " ", as_string(value))
    text = text.strip(" \t\r\n｜|")
    return text


def is_visual_ocr_noise(text: str) -> bool:
    if len(text) <= 1:
        return True
    if any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in VISUAL_OCR_NOISE_PATTERNS):
        return True
    if re.fullmatch(r"[\d\s:：.·,，%]+", text):
        return True
    if re.fullmatch(r"[♡❤★☆💬↗+\-\d\s]+", text):
        return True
    return False


def maybe_visual_ocr_noise(text: str) -> bool:
    return any(
        re.match(pattern, text, flags=re.IGNORECASE)
        for pattern in (
            r"^原声.*$",
            r"^更多.*$",
            r"^置顶.*$",
        )
    )


def default_visual_frame_fingerprint(image_path: Path) -> str:
    return hashlib.sha1(image_path.read_bytes()).hexdigest()


def get_visual_frame_fingerprint(backend: Any, image_path: Path) -> str:
    fingerprint = getattr(backend, "frame_fingerprint", None)
    if callable(fingerprint):
        return as_string(fingerprint(image_path))
    return default_visual_frame_fingerprint(image_path)


def build_visual_anchor_records(
    regions: list[VisualRegionRecord],
    *,
    error: str,
    start: int,
) -> tuple[list[VisualAnchorRecord], int]:
    anchors: list[VisualAnchorRecord] = []
    cursor = start
    for region in regions:
        anchors.append(
            VisualAnchorRecord(
                anchor_id=f"A{cursor:02d}",
                text=region.text,
                review=region.review,
                region_ids=(region.region_id,),
            )
        )
        cursor += 1
    if anchors:
        return anchors, cursor

    fallback_text = error or "未识别到明显文字"
    fallback_review = "ocr_unclear" if error else "layout_unclear"
    return [VisualAnchorRecord(anchor_id=f"A{cursor:02d}", text=fallback_text, review=fallback_review)], cursor + 1


def build_visual_ocr_sidecar(
    video_path: Path,
    frames: list[VisualFrameRecord],
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "compiled_at": generated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "media": {
            "source_path": video_path.relative_to(ROOT).as_posix(),
            "mode": VISUAL_MODE.replace("-", "_"),
            "title": video_path.stem,
        },
        "frames": [
            {
                "frame_id": f"frame-{frame.index:04d}",
                "cover_start": format_timestamp(frame.cover_start_seconds),
                "cover_end": format_timestamp(frame.cover_end_seconds),
                "image_path": frame.rel_image_path,
                "regions": [
                    {
                        "region_id": region.region_id,
                        "bbox": region.bbox,
                        "text": region.text,
                        "order": region.order,
                        **({"review": region.review} if region.review else {}),
                    }
                    for region in frame.regions
                ],
            }
            for frame in frames
        ],
    }


def render_visual_source_markdown(
    video_path: Path,
    probe: MediaProbe,
    frames: list[VisualFrameRecord],
    *,
    generated_at: datetime,
) -> str:
    del probe
    origin = video_path.relative_to(ROOT).as_posix()
    doc_lang = detect_visual_doc_lang(video_path, frames)
    content_title = "内容记录" if doc_lang == "zh" else "Content Records"
    appendix_title = "锚点附录" if doc_lang == "zh" else "Anchor Appendix"
    review_after = (generated_at.date() + timedelta(days=30)).isoformat()
    lines = [
        "---",
        "type: source",
        "status: draft",
        "aliases: []",
        "source_refs:",
        f"  - {origin}",
        "tags:",
        "  - source",
        f"  - {VISUAL_MODE}",
        "  - media-compiled",
        "confidence: 0.55",
        f"updated_at: {generated_at.date().isoformat()}",
        f"review_after: {review_after}",
        "see_also: []",
        "part_of: []",
        "depends_on: []",
        "supports: []",
        "contradicts: []",
        "source_kind: extracted",
        "traceability_level: anchor",
        "---",
        "",
        f"## {content_title}",
    ]
    for frame in frames:
        lines.extend(
            [
                "",
                f"### E{frame.index:02d} | {visual_keywords_for_frame(frame, doc_lang=doc_lang)}",
                f"Time: {format_timestamp_span(frame.cover_start_seconds, frame.cover_end_seconds)}",
            ]
        )
        for anchor in frame.anchors:
            lines.append(f"- [{anchor.anchor_id}] {anchor.text}")

    lines.extend(["", f"## {appendix_title}"])
    for frame in frames:
        lines.extend(
            [
                "",
                f"### Frame {frame.index:02d}",
                f"Covers: {format_timestamp_span(frame.cover_start_seconds, frame.cover_end_seconds)}",
                f"Image: `{frame.rel_image_path}`",
                f"![Frame {frame.index:02d}]({frame.rel_image_path})",
            ]
        )
        for anchor in frame.anchors:
            lines.append(f"- [{anchor.anchor_id}] {anchor.text}")
            if anchor.review:
                lines.append(f"  Review: {anchor.review}")
    lines.append("")
    return "\n".join(lines)


def detect_visual_doc_lang(video_path: Path, frames: list[VisualFrameRecord]) -> str:
    samples = [video_path.stem]
    for frame in frames:
        samples.extend(region.text for region in frame.regions)
    return "zh" if any(has_cjk_text(sample) for sample in samples) else "en"


def has_cjk_text(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def visual_keywords_for_frame(frame: VisualFrameRecord, *, doc_lang: str) -> str:
    texts = [region.text for region in frame.regions] or [anchor.text for anchor in frame.anchors]
    if not texts:
        return "未识别文本" if doc_lang == "zh" else "No OCR text"
    keywords: list[str] = []
    for text in texts[:2]:
        compact = normalize_ocr_text(text)
        if len(compact) > 30:
            compact = compact[:27].rstrip() + "..."
        keywords.append(compact)
    return " / ".join(keywords)


def format_timestamp_span(start_seconds: float, end_seconds: float) -> str:
    start = format_timestamp(start_seconds)
    end = format_timestamp(end_seconds)
    return start if start == end else f"{start}-{end}"


def require_executable(name: str, *, install_hint: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    raise RuntimeError(f"Missing required executable: {name}. Install it first with `{install_hint}`.")


def resolve_transfer_platform_executable() -> str:
    env_path = as_string(os.environ.get("TRANSFER_PLATFORM_BIN"))
    if env_path:
        return env_path

    env_root = as_string(os.environ.get("TRANSFER_PLATFORM_ROOT"))
    if env_root:
        candidate = Path(env_root) / ".venv" / "bin" / "transfer-platform"
        if candidate.exists():
            return str(candidate)

    which_result = shutil.which("transfer-platform")
    if which_result:
        return which_result

    candidate = Path.home() / "Coding" / "transfer_platform" / ".venv" / "bin" / "transfer-platform"
    if candidate.exists():
        return str(candidate)

    raise RuntimeError(
        "Missing transfer-platform executable. Install the standalone tool or set TRANSFER_PLATFORM_BIN."
    )


def infer_title(path: Path, frontmatter: dict[str, Any], body: str) -> str:
    for key in ("title", "statement", "core_focus", "core_question", "question"):
        value = as_string(frontmatter.get(key))
        if value:
            return value
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem


def infer_source_type(path: Path) -> str:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return "unknown"
    if not relative.parts:
        return "unknown"
    if relative.parts[0] == "raw":
        return "raw"
    if relative.parts[0] == "知识簇" and len(relative.parts) > 1:
        return relative.parts[1].rstrip("s")
    if len(relative.parts) >= 2 and relative.parts[0] == "_graphify":
        return relative.parts[1].rstrip("s")
    return relative.parts[0]


def infer_knowledge_kind(path: Path) -> str:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        relative = path
    parts = relative.parts
    if not parts:
        return "unknown"
    if parts[0] == "知识簇":
        if path.name == "_索引.md":
            return "index"
        if "命题" in parts or "_claims" in parts:
            return "claim"
        return "wiki"
    if len(parts) >= 2 and parts[0] == "_graphify":
        if parts[1] == "sources":
            return "source"
        if parts[1] == "indexes":
            return "index"
    return "unknown"


def candidate_keys(rel_path: str, title: str, aliases: list[str]) -> list[str]:
    path_no_ext = rel_path.rsplit(".", 1)[0] if "." in rel_path else rel_path
    stem = Path(rel_path).stem
    keys = {
        normalize_ref(stem),
        normalize_ref(path_no_ext),
        normalize_ref(path_no_ext.split("/", 1)[-1]),
        normalize_ref(title),
    }
    for alias in aliases:
        keys.add(normalize_ref(alias))
    return [key for key in keys if key]


def normalize_ref(value: str) -> str:
    normalized = value.strip().strip("/")
    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"\.md$", "", normalized, flags=re.IGNORECASE)
    return normalized.lower()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[\\\\/:*?\"<>|]+", "-", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    return cleaned[:120]


def resolve_reference(
    value: str, alias_map: dict[str, str | None], node_specs: dict[str, dict[str, Any]]
) -> str | None:
    if not value:
        return None
    clean = value.split("|", 1)[0].split("#", 1)[0].strip()
    if clean in node_specs:
        return clean
    if clean.endswith(".md") and clean[:-3] in node_specs:
        return clean[:-3]
    normalized = normalize_ref(clean)
    if normalized in alias_map:
        return alias_map[normalized]
    if clean.startswith("./"):
        maybe = clean[2:]
        if maybe in node_specs:
            return maybe
    return None


def as_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [as_string(item) for item in value if as_string(item)]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [as_string(value)]


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return None


def is_stale(value: str) -> bool:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() <= date.today()
    except ValueError:
        return False


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
