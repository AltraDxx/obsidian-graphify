# Graphify Workflows

Graphify's active compilation chain is:

`Raw -> Source -> Claim -> Wiki -> Index / Search / Ask`

## Processing Scope
- `处理清单.md` is the user-facing scoped queue.
- 没有清单或清单为空时，默认全量处理。
- 有未完成条目时，只处理清单条目及必要上下游。
- 清单支持 `[[wikilink]]`、反引号路径和普通路径。
- 完成处理后勾选条目，并在“处理记录”追加简短结果。

## Ingest
1. Start from one or more `raw/inbox/*` items or scoped entries from `处理清单.md`.
2. Identify the smallest related context from existing cluster Index, Wiki, Claim, and Source notes.
3. Create or update a `_graphify/sources/*` evidence page when the user supplied durable evidence.
4. Extract or update atomic `知识簇/<知识簇>/命题/*` notes from the evidence.
5. Promote only cohesive, reusable claim sets into `知识簇/<知识簇>/*` Wiki notes.
6. 未被任何 Wiki 引用的 Claim 可以暂时保留在 `命题/` 作为待综合命题；不要为它复制第二份 Wiki。
7. Update the relevant cluster `_索引.md` or `_graphify/indexes/*` if browsing structure changed.
8. Mark Markdown raw items as `processed` after Source and Claim extraction is complete.
9. Append a short note to `_logs/log.md`.
10. Run `.venv/bin/python scripts/graphify.py lint`.

## Query
1. Use `.venv/bin/python scripts/graphify.py lookup "<term>"` to route the question to a cluster or candidate Wiki note.
2. `lookup` first checks Index/Wiki titles, aliases, tags, frontmatter, `快速把握`, and body preview; then it searches Wiki/Claim notes inside the candidate cluster.
3. Wiki 检索按 section 进行：优先 `快速把握` 和各个 `##` 小节命中，并在结果里返回最佳 `section`；Claim 保持原子命题，不切成更小片段。
4. 如果路由层没有命中，`lookup` 会回退到全量 Wiki/Claim 检索；Source 仍默认不进入主检索。
5. `lookup` 的 `Related knowledge` 主要由显式边重排：`claim_ref`、`summary_claim_ref`、`supports`、`depends_on`、`part_of`、`see_also`、`wikilink`；冲突边只在命中 Claim 时强制带出冲突链。
6. Prefer the cluster Index first when the topic is broad; prefer the current Wiki note first when the user is asking while reading a page.
7. Follow Wiki `claim_refs` to Claims, then Claims' `source_refs` to Sources only when evidence verification is needed.
8. Answer with the smallest sufficient citation chain.
9. Do not write back by default after every answer.
10. If the user confirms a sync or the conversation clearly produces durable knowledge, choose the smallest write-back:
   - page-local review note for durable review value
   - `_graphify/sources/*` when the user supplied evidence or edited a Source
   - `知识簇/<知识簇>/命题/*` for a new supported proposition
   - `知识簇/<知识簇>/*` for reusable synthesis from multiple Claims
   - cluster `_索引.md` or `_graphify/indexes/*` when browsing structure changed
11. Run `lint`, then `export` if graph structure changed.

Question recording rules:
- 默认取消“一问一页”的 question.md。
- 如果用户正在读某个 Wiki，只记录真正影响知识更新的问题、纠错、裁决或复盘。
- 只有跨多个 Wiki、无法归属当前页、或本身值得作为完整材料保留的长对话，才创建 Source。
- 如果页内记录产生新命题，再抽到 `知识簇/<知识簇>/命题/*`；如果只是解释已有知识，不新增 Claim。
- 问题本身不是 Source；只有用户提供新材料、案例、观察、纠错，或明确要求把完整对话作为材料保留时，才创建 Source。
- 如果用户直接新建文件记录问题或材料，先放入 `raw/inbox/`；同步时再判断它是 Wiki 复盘、Source，还是 Claim 更新触发器。

## Sync User Edits
1. Run `.venv/bin/python scripts/graphify.py changes` to detect changed tracked files.
2. For a changed Source, run `.venv/bin/python scripts/graphify.py impact "<source>"`.
3. Update downstream Claims first, then Wiki notes, then Indexes.
4. For a changed Wiki note, compare edited main/review content against existing Claims and Sources before rewriting Claims.
5. Append `_logs/log.md` with the actual knowledge delta.

Source sync decision rules:
- 如果 Source 只是改格式/错字，不改 Claim/Wiki。
- 如果 Source 新增证据，先更新 Source 摘要与锚点；必要时新增 Claim，再更新引用它的 Wiki。
- 如果 Source 改变原有证据，更新 Claim 的 `statement`、`scope`、`boundary_note`、`support_state`、`confidence`。
- 如果 Source 推翻原 Claim，不硬删 Claim；标记为 `disputed` / `outdated`，并更新引用它的 Wiki。
- 过期 Claim 对应的 Wiki 正文必须删除或改写，不能继续作为当前解释；如需保留历史分歧，只在边界/冲突段落简短提及。
- 完成后再统一更新相关 Wiki 正文、`claim_refs` 和索引，然后运行 `lint`、`export`。

Claim conflict rules:
- 冲突发生时，两个 Claim 都写 conflict_refs 和 contradicts，并在 `## 可能冲突或待验证` 说明冲突点。
- 用户验证后，被采纳 Claim 保持 `active`，删除“待验证”措辞，把原冲突点和裁决原因移到 `## 复盘记录`。
- 被否定 Claim 标记为 `outdated` 或 `disputed`，保留 Source、冲突关系和复盘记录，不删除。
- Wiki 只吸收用户验证后的稳定解释；引用过期或被否定 Claim 的正文必须同步删除或改写。

## Curate
1. Look for weak, stale, conflicting, duplicate, or poorly connected Claims and Wiki notes.
2. Strengthen Source -> Claim -> Wiki traceability.
3. Merge overlapping Claims only after preserving all source refs, useful aliases, and conflict notes.
4. Refresh Wiki notes whose `claim_refs` no longer support the `core_focus`.
5. Refresh cluster `_索引.md` or `_graphify/indexes/*` when discoverability changes.
6. Append a short note to `_logs/log.md`.

## Lint And Export
Run `.venv/bin/python scripts/graphify.py lint` to check frontmatter, broken links, relation targets, claim refs, stale notes, orphans, and protected links.

Run `.venv/bin/python scripts/graphify.py export` to regenerate:
- `exports/graph.json`
- `exports/graph.graphml`
- `exports/graph-summary.md`
- `_logs/link-manifest.json`
- `_logs/vault-state.json`

## Obsidian Surface Rules
- The left file browser should expose knowledge clusters under `知识簇/`.
- `_graphify/indexes/Graphify知识库索引.md` is the single explicit Graphify operator entry in Obsidian.
- `命题/` is visible inside each cluster for traceability, but Wiki pages remain the main reading surface.
- The default Obsidian graph should show `知识簇/` Wiki pages, cluster `_索引.md`, and standalone Claims marked with `graph_role: standalone_claim`.
- orphan means a note with no `inlinks` and no `outlinks`; it is a link-isolation diagnostic, not the same thing as a pending Claim.
- Smart Connections is a nearby-reading aid, not the canonical structure.
- `_graphify/dashboards/` is internal diagnostics, not a user entry point.
