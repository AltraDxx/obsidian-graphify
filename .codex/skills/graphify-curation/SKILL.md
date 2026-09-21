# Graphify Curation

Use this skill when improving structure, links, and note health across the vault.

## Workflow
1. Review stale, weak, conflicting, duplicate, or orphaned Source, Claim, Wiki, and Index notes.
2. Strengthen traceability with Source -> Claim -> Wiki links and explicit relation arrays.
3. Merge overlapping Claims only after preserving all source refs, useful aliases, boundary notes, and conflict refs.
4. Refresh Wiki notes when their `claim_refs` no longer support the `core_focus`.
5. When Claims conflict, both Claims must keep bidirectional `conflict_refs` and `contradicts`; after user verification, move the original conflict point and decision into `## 复盘记录`.
6. Remove or rewrite Wiki正文 that is still supported by `outdated` or `disputed` Claims; do not keep inactive Claims as current explanation.
7. Downgrade unsupported pages with `draft_state: needs_refresh` instead of hiding uncertainty.
8. Refresh cluster `_索引.md` or `_graphify/indexes/*` when discoverability changes.
9. Log the curation batch in `_logs/log.md`.

## Focus Areas
- orphan reduction
- stale page refresh
- confidence upgrades or downgrades
- Source / Claim / Wiki traceability
- conflict and boundary coverage
- inactive Claim cleanup from Wiki正文
- bridge indexes
- Wiki synthesis depth when the source material supports deeper explanation

## Safety Rules
- Never remove protected wikilinks, relation arrays, or claim refs unless asked.
- Prefer small, traceable edits to large rewrites.
- Keep `知识簇/*` note names and headings Chinese-first unless the note is fundamentally an English product/framework/abbreviation.
- Keep navigation notes and semantic-retrieval settings aligned: graph for explicit structure, Smart Connections for nearby reading suggestions.
- Do not force fixed template sections; use the structure that best explains the knowledge.
- Do not revive the old entity/concept/synthesis workflow.
