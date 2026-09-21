# Obsidian Setup

## Folder Surface
- User-facing reading starts from `知识簇/`.
- The dedicated Graphify operator entry is `_graphify/indexes/Graphify知识库索引.md`.
- Wiki pages live at `知识簇/<知识簇>/*.md`.
- Cluster indexes live at `知识簇/<知识簇>/_索引.md`.
- Cluster Claims live at `知识簇/<知识簇>/命题/*.md`.
- Source notes live at `_graphify/sources/`.
- Vault/operator indexes live at `_graphify/indexes/`.
- Internal dashboards live at `_graphify/dashboards/`.

## Retrieval And Graph
- Smart Connections should include `type:claim` and `type:wiki` when useful for nearby reading.
- Smart Connections should exclude `_logs`, `exports`, `templates`, `.codex`, `_graphify/dashboards`, `schema`, `scripts`, `raw`, `_graphify/sources`, and `_graphify/indexes` from semantic indexing.
- The global graph should focus on `path:"知识簇/" -path:"命题/" OR [graph_role:standalone_claim]`.
- `graph_role: standalone_claim` is a derived marker for Claims that are not referenced by any Wiki `claim_refs` or `summary_claim_refs`.
- Graphify does not manage Obsidian bookmarks; bookmarks are for user-owned review and uncertainty queues.

## Authoring
- Use `templates/wiki.md`, `templates/source.md`, `templates/claim.md`, and `templates/index.md` as references, not mandatory section contracts.
- Ask questions from a current Wiki page when possible; record only durable corrections, decisions, or review notes in that page's `## 用户提问与复盘`.
- Use `处理清单.md` to tell Codex which notes to process in a scoped batch.
