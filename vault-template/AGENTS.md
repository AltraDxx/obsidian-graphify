# Graphify Vault 操作指南

这里是用户知识库。Obsidian 用于阅读与编辑，Codex 执行语义处理，`graphify` 提供确定性维护。

## 读取入口

先读 [笔记规范](schema/note-spec.md) 与 [工作流规范](schema/workflows.md)，它们是知识语义和流程的唯一权威。
然后读 `.codex/skills/graphify-core/SKILL.md`，根据任务读取 ingest、query 或 curation skill。
若当前 Codex 界面没有列出这些 skills，直接读取对应文件执行；不要假设它们已经自动加载。

## 执行约束

- 保持 `Raw -> Source -> Claim -> Wiki -> Index` 模型，知识笔记文件名及标题中文优先。
- 在本 Vault 内运行 `graphify`；从其他目录运行时显式指定 `graphify --vault <本目录>`。
- 根据 `schema/workflows.md` 的 Processing Scope 确定范围；指定清单时运行 `graphify scope 处理清单.md`。
- 提问按 Query 执行，默认不写回；当前 Wiki 是明确上下文时从该页开始，只在核验证据时展开 Source。
- 同步用户编辑按 Sync User Edits 执行：先 `graphify changes`，Source 变化再 `graphify impact <source>`，依次处理 Claim、Wiki、Index。
- 用户手写 wikilink 与关系引用受保护，遵循 note-spec 的 Common Knowledge Contract；不得擅自删链。
- 每个已接受的修改批次写入 `_logs/log.md`，运行 `graphify lint`；结构改变后运行 `graphify export`。
- 不使用本地小模型聊天替代 Graphify 问答。Smart Connections 只辅助召回，显式结构以规范为准。

## Git 边界

真实 Vault 应使用独立私有仓库。提交前检查 diff，避免凭据、个人应用状态和缓存进入历史。
升级引擎不会自动覆盖本 Vault 的规则；重新 init 默认保留已有文件。更新规则时逐文件比较并保留用户定制。
