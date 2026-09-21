# Graphify Core

Use this skill for every Graphify task in this vault.

## Responsibilities
- Treat `raw/inbox/*` as unclassified source material and `知识簇/`, `_graphify/sources/`, and `_graphify/indexes/` as the canonical explicit graph.
- Follow the active compilation chain: `Raw -> Source -> Claim -> Wiki -> Index`.
- Respect the directory contract in `raw/inbox/`, `知识簇/<知识簇>/`, `知识簇/<知识簇>/命题/`, `_graphify/sources/`, `_graphify/indexes/`, `schema/`, `templates/`, `_graphify/dashboards/`, `_logs/`, and `exports/`.
- Follow [schema/note-spec.md](../../../schema/note-spec.md) for frontmatter and write-back rules.
- Preserve all manual `[[wikilink]]` edges, relationship arrays, `claim_refs`, `summary_claim_refs`, and `conflict_refs`.

## Required Behaviors
- Update `source_refs`, `confidence`, `updated_at`, and `review_after` on any changed knowledge note.
- Keep Source notes evidence-focused, Claim notes atomic, Wiki notes synthesized around free-text `core_focus`, and Index notes focused on browsing structure.
- Use Chinese-first filenames and headings in `知识簇/*`; preserve standard English terms such as `RAG`, `Agent`, `Workflow`, `Latency`, `Streaming`, `Guardrails`, `RAGAS`, and `KV Cache`.
- When a structural change lands, run `python3 scripts/graphify.py lint` and usually `python3 scripts/graphify.py export`.
- Append a concise operator note to `_logs/log.md`.
- Keep note bodies connected and non-redundant, but do not leave important Wiki notes shallow.
- Preserve formulas, quantitative rules, and mechanism details when they help explain the synthesis.
- Treat `_graphify/indexes/Graphify知识库索引.md` as a standalone operator index, not as part of a knowledge cluster.
- Keep inactive Claims out of current Wiki正文; if a Claim is `outdated` or `disputed`, remove or rewrite the supported Wiki explanation and preserve history in Claim `## 复盘记录`.
- Treat Smart Connections as a semantic discovery aid only.

## Do Not
- Do not create new active entity, concept, or synthesis buckets.
- Do not create separate question notes by default.
- Do not treat a question alone as a Source; create Source only for supplied evidence, cases, observations, corrections, or complete conversations intentionally preserved as material.
- Do not force Wiki notes into fixed template sections; templates are reference checklists.
- Do not delete explicit user links, relation arrays, or claim refs without an explicit request.
- Do not treat Smart Connections suggestions as canonical unless they are reflected in explicit files and links.
- Do not create ad hoc frontmatter fields when an existing field fits.
