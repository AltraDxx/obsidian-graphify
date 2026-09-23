---
name: graphify-query
description: 依据 Graphify Vault 回答知识问题；默认只读，需同步时转入规范的同步流程。
---

# graphify-query

- **Use when:** 用户询问 Vault 中的知识，或围绕当前 Wiki 提问。
- **Do not use when:** 用户主要要求新材料入库或全库整理。
- **Inputs:** 问题、可选当前 Wiki 与 Vault 路径。
- **Outputs:** 带笔记引用的回答和证据不足说明；获准同步时才有文件变更。
- **Required validation:** 只读查询检查引用可解析；写回后 graphify lint，结构变化后 export。

## 执行

1. 遵循 [workflows 的 Query](../../../schema/workflows.md#query) 和 [note-spec 的 Query And Update Rules](../../../schema/note-spec.md#query-and-update-rules)。
2. 对宽泛问题先 `graphify lookup "主题"`；明确当前 Wiki 时从该页开始。按需要展开 Claim 与 Source，不默认扫描全部证据。
3. 给出笔记级引用，区分已有结论、冲突和证据不足。
4. 默认不写回。用户要求同步或出现规范允许的持久材料时，按最小写回落点处理；用户明确说不写回时保持只读。
5. 同步用户编辑按 [Sync User Edits](../../../schema/workflows.md#sync-user-edits) 先 changes、必要时 impact，再依次更新下游与日志。

命令在 Vault 根目录运行；从其他目录运行时显式使用 `graphify --vault <路径>`。
