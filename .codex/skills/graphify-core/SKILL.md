---
name: graphify-core
description: Graphify Vault 通用维护规则；处理知识笔记前使用，不用于修改引擎源码。
---

# graphify-core

- **Use when:** 维护 Vault 内容或执行知识工作流。
- **Do not use when:** 开发引擎代码，或处理与知识库无关的文件。
- **Inputs:** Vault 路径、用户任务与可选处理清单。
- **Outputs:** 确定范围、选择工作流并验证结果。
- **Required validation:** 改动后 graphify lint；结构变化后 graphify export。

## 执行

1. 阅读 [笔记规范](../../../schema/note-spec.md) 与 [工作流规范](../../../schema/workflows.md)，按任务选择 ingest、query、curation 或 Sync User Edits。
2. 从指定材料或当前 Wiki 开始，使用 `graphify lookup`、`changes`、`scope`、`impact` 缩小上下文。
3. 按 note-spec 的 Common Knowledge Contract 保护显式链接，按 Query And Update Rules 决定是否写回。
4. 规范中的 Source/Claim/Wiki/Index 各节决定修改落点；不另造类型或字段。中文优先命名，模板仅为脚手架。
5. 已接受批次写入 `_logs/log.md`，验证后报告实际修改与未解决问题。

命令在 Vault 根目录运行；从其他目录运行时显式使用 `graphify --vault <路径>`。
