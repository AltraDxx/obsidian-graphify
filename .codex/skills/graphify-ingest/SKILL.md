# Graphify Ingest

Use this skill when converting `raw/inbox/*` material into the curated graph.

## Workflow
1. If the user mentions recent additions, run `python3 scripts/graphify.py changes` first.
2. If the user provides a scoped batch, read `处理清单.md` or run `python3 scripts/graphify.py scope 处理清单.md`.
3. Read the raw item and nearby Source, Claim, Wiki, and Index notes.
4. Create or update a `_graphify/sources/*` evidence page with anchors and traceability notes when durable evidence exists.
5. Extract or update atomic `知识簇/<知识簇>/命题/*` notes from the evidence.
6. Promote only cohesive claim sets into `知识簇/<知识簇>/*` Wiki notes.
7. Update the cluster `_索引.md` or `_graphify/indexes/*` when a cluster, core Wiki, or cross-cluster relation changed.
8. Ensure `source_refs` on affected notes point back to their direct support.
9. Mark raw Markdown items as `processed` when Source and Claim extraction is complete.
10. Record the batch in `_logs/log.md`.

## Quality Bar
- Source notes preserve evidence; they are not the final explanation surface.
- Raw material does not need `source_type`; classify it during ingest.
- A question alone is not a Source. Create or update Source only for user-supplied evidence, cases, observations, corrections, complete conversations preserved as material, or imported raw items.
- Claims must be short, traceable, updateable, and explicit about support state and scope.
- Wiki notes synthesize around `core_focus`; it is free text and does not have to be a question.
- Templates are reference checklists. Do not force fixed sections when another structure explains the knowledge better.
- Prefer updating an existing Claim or Wiki note over creating a duplicate.
- Add explicit links where the evidence materially supports a Claim or Wiki note.
- Keep confidence conservative until multiple sources converge.
- Use Chinese-first filenames, titles, and section headings for new `知识簇/*` notes while preserving standard English terms.
- Preserve formulas, mechanisms, trade-offs, boundaries, and failure modes when they help make the Wiki synthesis understandable.
- `快速把握` is recommended for Wiki routing; `## 摘要` is not required.
