from __future__ import annotations

from collections import Counter
from collections import defaultdict
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape as xml_escape
from obsidian_graphify.model import CLAIM_REF_FIELDS, Edge, Note, RELATION_FIELDS
from obsidian_graphify.refs import resolve_reference
from obsidian_graphify.utils import as_string, is_stale


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
