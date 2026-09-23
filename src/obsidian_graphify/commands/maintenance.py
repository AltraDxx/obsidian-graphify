from __future__ import annotations

from collections import Counter
from collections import defaultdict
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any
import json
import sys
from obsidian_graphify.config import current_vault
from obsidian_graphify.commands.scope import resolve_scope
from obsidian_graphify.graph import build_edges, build_graph_summary, build_graphml, build_link_manifest, find_impacted_notes
from obsidian_graphify.model import Note, RawItem
from obsidian_graphify.refs import resolve_reference
from obsidian_graphify.utils import load_json, write_text


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
    write_text(current_vault().pending_path, "\n".join(lines).rstrip() + "\n")
    print(f"Updated {current_vault().pending_path.relative_to(current_vault().root).as_posix()} with {len(pending_items)} pending items.")
    return 0


def command_changes(data: dict[str, Any], save_baseline: bool = False) -> int:
    current_snapshot: dict[str, dict[str, Any]] = data["file_snapshot"]
    previous_state = load_json(current_vault().state_path) or {}
    previous_snapshot: dict[str, dict[str, Any]] = previous_state.get("files", {})

    added = sorted(path for path in current_snapshot if path not in previous_snapshot)
    removed = sorted(path for path in previous_snapshot if path not in current_snapshot)
    modified = sorted(
        path
        for path, meta in current_snapshot.items()
        if path in previous_snapshot
        and (
            meta.get("sha256") != previous_snapshot[path]["sha256"]
            if previous_snapshot[path].get("sha256")
            else (
                meta.get("mtime_ns") != previous_snapshot[path].get("mtime_ns")
                or meta.get("size") != previous_snapshot[path].get("size")
            )
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
            current_vault().state_path,
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
        print(f"Saved current file snapshot to {current_vault().state_path.relative_to(current_vault().root).as_posix()}.")
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

    print(f"Vault root: {current_vault().root}")
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
    write_text(current_vault().export_root / "graph.json", json.dumps(graph_json, ensure_ascii=False, indent=2) + "\n")
    write_text(current_vault().export_root / "graph.graphml", build_graphml(nodes, edges))
    write_text(current_vault().export_root / "graph-summary.md", build_graph_summary(nodes, edges, wiki_notes))

    manifest = build_link_manifest(wiki_notes, alias_map, node_specs)
    write_text(current_vault().link_manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write_text(
        current_vault().state_path,
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
        f"{len(nodes)} nodes, {len(edges)} edges, snapshots written to {current_vault().link_manifest_path.relative_to(current_vault().root).as_posix()} and {current_vault().state_path.relative_to(current_vault().root).as_posix()}."
    )
    return 0
