# Graphify Query

Use this skill when answering questions from the vault and feeding the result back into the graph.

## Workflow
1. Use `python3 scripts/graphify.py lookup "<term>"` first when the user asks about a topic, product, framework, person, or knowledge question.
2. Treat `lookup` as a two-layer router: first cluster Index/Wiki title, aliases, tags, frontmatter, `快速把握`, and body preview; then Wiki/Claim notes inside the candidate cluster.
3. Do not read raw or Source正文 unless evidence verification is needed.
4. If the user is clearly asking about the note they are currently reading, start from that note and expand to its Claim / Source chain.
5. Answer with note-level citations.
6. Do not write back after every answer by default. If the user confirms sync or the conversation creates durable knowledge, choose the smallest durable write-back:
   - durable page-local review value: update the relevant Wiki page's `## 用户提问与复盘`
   - new proposition supported by current evidence: update or create a `知识簇/<知识簇>/命题/*` note
   - several claims form reusable synthesis: update or create a `知识簇/<知识簇>/*` Wiki note
   - user supplied a new example/correction: place it in `raw/inbox/`, then create or update a Source and extract Claims
   - browsing structure changed: update cluster `_索引.md` or `_graphify/indexes/*`
7. Update `confidence`, `updated_at`, and `review_after` on every changed answer note.
8. Log the work in `_logs/log.md`.

## Closed-Loop Requirement
- A useful question can improve the graph, but only sync after user confirmation or a meaningful batch.
- Favor updating canonical Claims and Wiki notes instead of creating standalone question notes.
- Questions themselves are not Sources. Keep ordinary questions out of Claim; only preserve a Source when the user supplied evidence, a case, an observation, a correction, or asked to retain the full conversation as material.
- If the best answer is incomplete, preserve uncertainty explicitly in Claim support state or the Wiki review section.
- If a question challenges a Claim, record a short maintenance note in the Claim only when it affects `statement`, `scope`, `boundary_note`, `support_state`, or conflict state.
- When refining a page, synthesize around `core_focus`; do not recreate old concept/synthesis buckets or force template sections.
- If a user review changes a note, record the concrete knowledge delta in the note body.
