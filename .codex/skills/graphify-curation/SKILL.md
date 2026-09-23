---
name: graphify-curation
description: 整理 Graphify Vault 的重复、过期、冲突与弱关联知识，保护用户显式关系。
---

# graphify-curation

- **Use when:** 用户要求维护知识结构、复查冲突或整理过期笔记。
- **Do not use when:** 普通只读问答或单纯导入新材料。
- **Inputs:** Vault、维护目标、可选处理清单。
- **Outputs:** 可追溯的 Claim/Wiki/Index 修订、日志和待复核项。
- **Required validation:** graphify lint；结构变化后 graphify export。

## 执行

1. 阅读 [workflows 的 Curate](../../../schema/workflows.md#curate) 以及 Claim conflict rules；笔记字段以 [note-spec](../../../schema/note-spec.md) 为准。
2. 在指定范围识别薄弱、过期、冲突、重复与孤立笔记，优先补全 Source → Claim → Wiki 证据链。
3. 合并前保留证据、别名、边界与冲突记录。不要将尚未裁决的冲突变成确定结论。
4. 按规范处理 inactive Claim 对 Wiki 的影响，并更新导航入口。保护用户链接，不借整理擅自删链。
5. 记录具体知识变化与待用户裁决项，验证完成后报告。

命令在 Vault 根目录运行；从其他目录运行时显式使用 `graphify --vault <路径>`。
