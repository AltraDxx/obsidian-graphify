# 第二阶段候选改进（本轮不实施）

第一阶段保持现有路径/标题/alias 引用和知识语义。

后续单独设计不可变 `uid` 与 `schema_version`，比较 UUIDv7/ULID 后写 ADR；让 graph.json 节点身份与文件路径分离，保留旧引用读取兼容期。
迁移应有 `graphify migrate refs --dry-run`、可审查变更、迁移指南、回滚方案，以及 rename/move 身份稳定测试。

另行评估 Raw immutable、SHA-256 证据清单、内容哈希 changes 基线、将 `graph_role` 移出规范 frontmatter、缓存/派生产物迁到 `.graphify/`、媒体 provider/plugin 边界。
当前 changes 仍比较 mtime+size，Raw ingest 仍按既有 workflow 标记 processed；这些行为没有在本轮悄然改变。
