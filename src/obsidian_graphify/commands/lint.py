from __future__ import annotations

from pathlib import Path
from typing import Any
from obsidian_graphify.config import current_vault
from obsidian_graphify.commands.scope import resolve_scope
from obsidian_graphify.graph import build_edges, build_link_manifest, compare_manifests, edge_counts, find_standalone_claim_paths
from obsidian_graphify.model import CLAIM_FIELDS, COMMON_WIKI_FIELDS, Note, RELATION_FIELDS, SOURCE_FIELDS, STANDALONE_CLAIM_GRAPH_ROLE, VALID_CLAIM_STATUSES, VALID_STATUSES, VALID_SUPPORT_STATES, VALID_TYPES, VALID_VERIFICATION_STATES, WIKI_FIELDS
from obsidian_graphify.parsing import extract_section
from obsidian_graphify.refs import resolve_reference
from obsidian_graphify.utils import as_string, is_stale, load_json


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

    previous_manifest = load_json(current_vault().link_manifest_path)
    current_manifest = build_link_manifest(wiki_notes, alias_map, node_specs)
    if scoped["is_scoped"]:
        warnings.append("Scoped lint skipped protected-link snapshot comparison; run full lint/export after batch changes.")
    elif previous_manifest:
        warnings.extend(compare_manifests(previous_manifest, current_manifest, wiki_map))
    else:
        warnings.append(
            f"{current_vault().link_manifest_path.relative_to(current_vault().root).as_posix()}: no previous snapshot yet; run export to seed protected-link tracking"
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
