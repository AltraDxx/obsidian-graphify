# Graphify Vault Agent Guide

This vault is a Graphify knowledge base maintained with Obsidian, Codex, and `scripts/graphify.py`.

## Operating Model
- Obsidian is the authoring, browsing, and manual-linking surface.
- Codex maintains `ingest`, `query`, `sync`, and `curate`.
- `.venv/bin/python scripts/graphify.py` verifies, routes, detects changes, computes impact, lints, and exports.

## Required Read Order
1. Read [schema/note-spec.md](schema/note-spec.md).
2. Read [schema/workflows.md](schema/workflows.md).
3. Read the workflow-specific skill before changing notes:
   - `ingest`: [`.codex/skills/graphify-ingest/SKILL.md`](.codex/skills/graphify-ingest/SKILL.md)
   - `query`: [`.codex/skills/graphify-query/SKILL.md`](.codex/skills/graphify-query/SKILL.md)
   - `curate`: [`.codex/skills/graphify-curation/SKILL.md`](.codex/skills/graphify-curation/SKILL.md)

## Workflow Contract
- Active compilation chain: `Raw -> Source -> Claim -> Wiki -> Index`.
- `知识簇/<知识簇>/` contains readable Wiki notes and the cluster `_索引.md`.
- `知识簇/<知识簇>/命题/` contains source-backed propositions for that cluster.
- `_graphify/sources/` contains curated evidence.
- `_graphify/indexes/` contains vault-level and operator indexes. `map` is no longer a separate active type.
- A separate `question.md` workflow is removed. User questions and review notes belong in the relevant Wiki page's `## 用户提问与复盘`, or in a Source when the user supplied durable evidence.

## Query Rules
- Route broad questions through `.venv/bin/python scripts/graphify.py lookup "<term>"`.
- Prefer cluster Index -> Wiki -> Claim -> Source, instead of scanning the whole vault with the model.
- If the user is reading a specific Wiki page, use that page as the starting context.
- Do not update the knowledge base after every answer by default.
- Sync only after user confirmation, an explicit Obsidian edit batch, or durable new material.

## Sync Rules
- Run `.venv/bin/python scripts/graphify.py changes` before syncing user edits.
- If a Source changed, run `.venv/bin/python scripts/graphify.py impact "<source>"`.
- Update downstream Claims first, then Wiki notes, then Indexes.
- Preserve user-authored `[[wikilink]]`, relation arrays, `claim_refs`, `summary_claim_refs`, and `conflict_refs` unless explicitly asked to remove them.
- Append a concise `_logs/log.md` entry after each accepted batch.

## Processing List Rules
- `处理清单.md` is the user-facing scoped processing queue.
- No list, missing list, or empty list means full processing.
- A non-empty list means only the listed notes and necessary upstream/downstream notes should be processed.
- Supported entries are unchecked Markdown tasks with `[[wikilink]]`, backtick paths, or plain paths.

## Non-Negotiable Rules
- Valid note types are only `source`, `claim`, `wiki`, and `index`.
- Frontmatter `type` is canonical; path is used as a default inference and consistency check.
- Keep `source_refs`, `confidence`, `updated_at`, and `review_after` current when modifying knowledge notes.
- Claim notes preserve supported propositions and their truth boundaries.
- Wiki notes preserve coherent synthesis around `core_focus`; `core_focus` is free text and does not have to be a question or a fixed category.
- Templates are reference checklists, not mandatory section structures.
- `快速把握` is recommended for Wiki/Index routing; `## 摘要` is not required.
- Source notes preserve evidence; Index notes preserve browsing structure.
- Use Chinese-first filenames, visible titles, and section headings for knowledge notes. Keep established technical terms in English when natural.
- Treat Smart Connections as retrieval assistance only. Canonical structure lives in explicit files and links.
- Do not use local small-model chat flows for Graphify Q&A.

## Validation Commands
- `.venv/bin/python scripts/graphify.py scan`
- `.venv/bin/python scripts/graphify.py changes`
- `.venv/bin/python scripts/graphify.py scope`
- `.venv/bin/python scripts/graphify.py scope 处理清单.md`
- `.venv/bin/python scripts/graphify.py lookup "<term>"`
- `.venv/bin/python scripts/graphify.py impact "<path-or-title>"`
- `.venv/bin/python scripts/graphify.py status`
- `.venv/bin/python scripts/graphify.py lint`
- `.venv/bin/python scripts/graphify.py export`

## Git Workflow
- `main` is the stable public branch; `develop` integrates the next release.
- Create short-lived topic branches from `develop` for non-trivial changes.
- Before committing, run the relevant unit tests, `graphify.py lint`, and `git diff --check`.
- Never force-add files ignored by the repository. Vault contents, Sources, raw evidence, logs, exports, personal Obsidian state, Smart Connections data, credentials, and media stay local.
- Never force-push or rewrite published `main` history.
- Follow [CONTRIBUTING.md](CONTRIBUTING.md) for branch, commit, and merge rules.
