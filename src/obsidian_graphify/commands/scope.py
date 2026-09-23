from __future__ import annotations

from pathlib import Path
from typing import Any
import re
from obsidian_graphify.config import current_vault
from obsidian_graphify.graph import adjacency, build_edges, find_impacted_notes
from obsidian_graphify.model import Note, RawItem
from obsidian_graphify.refs import dedupe_preserve_order, resolve_reference
from obsidian_graphify.utils import as_string


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
        path = current_vault().root / path
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
