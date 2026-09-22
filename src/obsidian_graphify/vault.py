from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
from obsidian_graphify.config import current_vault
from obsidian_graphify.model import IGNORED_FILENAMES, MARKDOWN_EXTENSIONS, Note, RAW_EXCLUDED_DIRS, RELATION_FIELDS, RawItem
from obsidian_graphify.parsing import extract_wikilinks, infer_knowledge_kind, infer_source_type, infer_title, load_markdown
from obsidian_graphify.refs import candidate_keys
from obsidian_graphify.utils import as_string, listify, to_float


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
        current_vault().cluster_root,
        current_vault().source_root,
        current_vault().index_root,
    )
    notes: list[Note] = []
    for root in roots:
        notes.extend(collect_markdown_notes(root))
    return sorted(notes, key=lambda note: note.rel_path)


def collect_raw_items() -> list[RawItem]:
    items: list[RawItem] = []
    if not current_vault().raw_root.exists():
        return items
    for path in sorted(p for p in current_vault().raw_root.rglob("*") if p.is_file()):
        if path.name in IGNORED_FILENAMES:
            continue
        rel_parts = path.relative_to(current_vault().root).parts
        if len(rel_parts) > 1 and rel_parts[1] in RAW_EXCLUDED_DIRS:
            continue
        rel_path = path.relative_to(current_vault().root).as_posix()
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
        rel_path = path.relative_to(current_vault().root).as_posix()
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


def build_file_snapshot(raw_items: list[RawItem], wiki_notes: list[Note]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    tracked_paths = [item.path for item in raw_items] + [note.path for note in wiki_notes]
    for path in tracked_paths:
        stat = path.stat()
        rel_path = path.relative_to(current_vault().root).as_posix()
        snapshot[rel_path] = {
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }
    return snapshot
