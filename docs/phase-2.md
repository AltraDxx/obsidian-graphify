# 第二阶段评估与范围

第一阶段保持现有路径/标题/alias 引用和知识语义。

后续单独设计不可变 `uid` 与 `schema_version`，比较 UUIDv7/ULID 后写 ADR；让 graph.json 节点身份与文件路径分离，保留旧引用读取兼容期。
迁移应有 `graphify migrate refs --dry-run`、可审查变更、迁移指南、回滚方案，以及 rename/move 身份稳定测试。

另行评估 Raw immutable、SHA-256 证据清单、将 `graph_role` 移出规范 frontmatter、缓存/派生产物迁到 `.graphify/`、媒体 provider/plugin 边界。
本轮追加实现 SHA-256 changes 基线：新快照比较内容哈希，旧快照回退到 mtime+size，执行 changes --save 或 export 后升级。不会改写笔记。changes/export 对跟踪文件流式计算哈希，因此包含大量视频的 Vault 在这两个命令上的开销会增加；lookup/status 等命令不额外计算哈希。

Raw ingest 仍按既有 workflow 标记 processed；UID、Raw immutable 与目录迁移需要独立设计、迁移预览和回滚，不与第一阶段重构混在同一个 PR。
