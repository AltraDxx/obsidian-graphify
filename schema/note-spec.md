# Graphify Note Spec

## Directory Roles
- `raw/inbox/`: user-created or imported material waiting to be classified, compiled, or referenced.
- `知识簇/<知识簇>/*.md`: readable Wiki notes; the knowledge cluster is the user-facing browsing unit.
- `知识簇/<知识簇>/_索引.md`: cluster Index note.
- `知识簇/<知识簇>/命题/*.md`: atomic, traceable Claims whose primary home is that cluster.
- `_graphify/sources/`: curated evidence notes compiled from raw material or durable user-supplied evidence.
- `_graphify/indexes/`: vault-level and Graphify operator indexes.
- `_graphify/dashboards/`: internal diagnostics; not a user-facing knowledge entry.
- `处理清单.md`: scoped processing list.
- `_logs/` and `exports/`: generated operational snapshots.

Graphify's compilation chain is:

`Raw -> Source -> Claim -> Wiki -> Index / Search / Ask`

## Common Knowledge Contract
All Source, Claim, Wiki, and Index notes must include:

```yaml
type: source | claim | wiki | index
status: draft | reviewed | verified | stale | archived
aliases: []
source_refs: []
tags: []
confidence: 0.0
updated_at: YYYY-MM-DD
review_after: YYYY-MM-DD
see_also: []
part_of: []
depends_on: []
supports: []
contradicts: []
```

Rules:
- Frontmatter `type` is canonical; path is used as default inference and consistency check.
- `source_refs` must point to raw material or lower-layer notes that directly support the note.
- Relationship arrays are explicit human-first edges and take precedence over inferred links.
- Manual `[[wikilink]]`, relation arrays, `claim_refs`, `summary_claim_refs`, and `conflict_refs` are protected links.

## Source Notes
`_graphify/sources/*` preserve evidence: what the source says, where it says it, and which claims can safely be extracted.

Source notes must additionally include:

```yaml
source_kind: extracted | native
traceability_level: raw | anchor | span
```

Source sync decision rules:
- 如果用户直接编辑了 Source 并要求同步，先跑 `changes` 定位被改的 Source，再用 `graphify.py impact <source>` 缩小到受影响的 Claim、Wiki 和 Index。
- 如果 Source 只是改格式或错字，不改下游 Claim/Wiki。
- 如果 Source 新增证据，更新 Source 摘要与锚点；必要时新增 Claim，再更新引用它的 Wiki。
- 如果 Source 改变原有证据，更新相关 Claim 的 `statement`、`scope`、`boundary_note`、`support_state` 和 `confidence`，再同步到 Wiki。
- 如果 Source 推翻原 Claim，不硬删 Claim；将其降级为 `disputed` 或 `outdated`，并更新引用它的 Wiki 与 Index。
- 问题本身不是 Source；只有用户明确提供材料、案例、观察、纠错，或要求把完整对话作为材料保留时，才创建或更新 Source。

## Claim Notes
`知识簇/<知识簇>/命题/*.md` are the smallest traceable proposition units. They answer: "What does the current evidence support?"

Claim notes must additionally include:

```yaml
statement: A short, precise proposition
claim_type: fact | method | opinion | case | hypothesis
support_state: supported | weak | conflicting | unclear
verification_state: source_supported | cross_source_supported | disputed | unclear
scope: Where this claim applies
boundary_note: Boundary, exception, or limitation
claim_origin: extracted | edited | merged
claim_status: active | disputed | outdated | pending
conflict_refs: []
graph_role: standalone_claim
```

Rules:
- Claim 拓展真实性边界：证据强弱、适用范围、例外、冲突和状态。
- Claim 文件放在主要所属知识簇的 `命题/`；跨簇复用通过显式关系表达，不复制文件。
- Claim 可以暂时不属于任何 Wiki；这表示它仍是待综合命题，而不是需要复制成第二份 Wiki。
- `graph_role: standalone_claim` 是派生标记，只用于未被任何 Wiki `claim_refs` 或 `summary_claim_refs` 引用的 Claim；一旦被 Wiki 吸收，应移除该标记。
- 普通问题不写入 Claim；只有当问题挑战某个 Claim 的真实性、适用范围或边界时，Claim 才在 `## 可能冲突或待验证` 或 `## 复盘记录` 中保留简短维护记录。
- 冲突 Claim 必须双向记录：两个 Claim 都写 `conflict_refs` 和 `contradicts`，并在正文说明冲突点。
- 用户验证后，被采纳 Claim 删除“待验证”措辞，把原冲突点和裁决原因移入 `## 复盘记录`；被否定 Claim 标记为 `outdated` 或 `disputed`，不删除。

## Wiki Notes
`知识簇/<知识簇>/*.md` are synthesized knowledge pages. Wiki is not a long Claim and does not have to be question-oriented.

Wiki notes must additionally include:

```yaml
core_focus: Free-text organizing focus
claim_refs: []
summary_claim_refs: []
draft_state: active | degraded | needs_refresh
version_no: 1
importance: low | medium | high
```

Body rules:
- Wiki 围绕 `core_focus` 综合多个 Claim，把知识讲透。
- `core_focus` 是自由文本，可以是任何能组织知识的主轴；示例类型不构成枚举。
- `page_intent` 可以保留为自由提示，但不做固定校验。
- 模板是参考检查清单，不是必填结构。可以按需使用机制、公式、案例、对比、流程、边界、争议或其他更合适的结构。
- `快速把握` 推荐保留，用于快速阅读和 lookup 路由；`## 摘要` 不再是硬要求。
- `## 用户提问与复盘` 只记录真正影响知识更新的问题、纠错、裁决或复盘。
- 未验证问题不得写入正文主线解释。
- 过期或被否定的 Claim 不应继续支撑 Wiki 正文；如果 Wiki 的 `claim_refs` 指向 `outdated` 或 `disputed` Claim，正文必须删除或改写对应解释。

## Index Notes
Index notes are navigation surfaces:
- `知识簇/<知识簇>/_索引.md` covers one cluster.
- `_graphify/indexes/知识库索引.md` is the vault-level entry.
- `_graphify/indexes/Graphify知识库索引.md` is an operator index and belongs to no knowledge cluster.

Index notes should explain what they cover, core entry points, neighboring clusters or indexes, and what should trigger future updates. They do not need `## 摘要`.

## Query And Update Rules
When a user asks a question:
- First route to the most relevant cluster Index or Wiki using `lookup`; it reads title, aliases, tags, frontmatter, `快速把握`, and a short body preview.
- `lookup` then scores Wiki by section and Claim by atomic note: Wiki results should expose the best matching `section`, while Claim remains one proposition unit instead of being split again.
- If route-level matching misses, `lookup` falls back to searching across all Wiki/Claim notes; Source remains out of the default primary search set.
- `Related knowledge` should prefer explicit graph structure (`claim_ref`, `summary_claim_ref`, `supports`, `depends_on`, `part_of`, `see_also`, `wikilink`) and only force conflict edges into view when the matched note is a Claim.
- Then read the best Wiki note and follow its `claim_refs` to Claims and Sources only when evidence verification is needed.
- Answer from the smallest sufficient Source / Claim / Wiki chain.
- Do not update the knowledge base after every answer by default.

Write-back choice:
- existing knowledge only: answer without creating a separate question note.
- user asks while viewing a Wiki page: record only durable review value in that page's `## 用户提问与复盘`.
- new supported proposition: update or create `知识簇/<知识簇>/命题/*`.
- reusable synthesis from multiple Claims: update or create `知识簇/<知识簇>/*`.
- user-supplied example, correction, personal observation, or edited Source: preserve/update a Source first, then extract or revise Claims.
- user-created loose files belong in `raw/inbox/` first; sync decides whether they become Wiki review records, Source notes, or Claim updates.

## Graph And Smart Connections Boundary
- Obsidian graph represents explicit structure. Its default view should show `知识簇/` Wiki pages, cluster `_索引.md`, and `graph_role: standalone_claim` Claims; it should not show Sources or operator indexes.
- Smart Connections is semantic retrieval assistance only. Use it to discover nearby Wiki or Claim material, not to define canonical structure.
- When Smart Connections and explicit links disagree, explicit Graphify structure wins.
