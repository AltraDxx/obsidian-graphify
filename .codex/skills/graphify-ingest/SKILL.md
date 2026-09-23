---
name: graphify-ingest
description: 将用户要求入库的 raw 材料整理为可追溯 Graphify 知识；普通提问不触发。
---

# graphify-ingest

- **Use when:** raw/inbox 新增材料且用户要求处理，或用户明确要求材料入库。
- **Do not use when:** 用户只问已有知识，未要求入库。
- **Inputs:** raw 路径、Vault、可选处理清单。
- **Outputs:** 零到多个 Source、Claim、Wiki 与必要 Index 更新。
- **Required validation:** graphify lint；结构变化后 graphify export。

## 执行

1. 阅读 [workflows 的 Ingest](../../../schema/workflows.md#ingest)，遵循 [note-spec](../../../schema/note-spec.md) 各类型规范。
2. 用户提到最近新增时先 `graphify changes`；指定清单则 `graphify scope 处理清单.md`。读取 raw 和最小相关知识链。
3. 执行 Ingest 顺序，优先更新已有笔记。证据不足时保留不确定性，不为凑齐目录强行生成 Wiki。
4. 保留有用的公式、机制、边界和失败条件，避免仅复制标题或模板。raw 处理状态、日志和索引更新遵循规范。
5. 运行验证，报告材料去向和文件变更。

命令在 Vault 根目录运行；从其他目录运行时显式使用 `graphify --vault <路径>`。
