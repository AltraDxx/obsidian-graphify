# 公开引擎与私有 Vault 的 Git 策略

引擎仓库只公开代码、规范、模板、skills、文档和合成 fixtures。真实知识放入单独私有仓库，避免被公开源码的 ignore 规则整体排除。

## 私有 Vault 结构

```text
MyGraphifyVault/
├── graphify.toml
├── AGENTS.md
├── .gitignore
├── .codex/skills/
├── schema/
├── templates/
├── raw/inbox/
├── 知识簇/
├── _graphify/
│   ├── sources/
│   ├── indexes/
│   └── dashboards/
├── 处理清单.md
├── _logs/                 # 运行时快照、日志
└── exports/               # 导出产物
```

应跟踪 `知识簇/**/*.md`、`_graphify/sources/**/*.md`、`_graphify/indexes/**/*.md`、`graphify.toml`、`AGENTS.md`、`处理清单.md`，以及随 Vault 使用的 schema、模板、skills。
需要共享的 Obsidian 设置可以审查后跟踪；个人 workspace、缓存和凭据不跟踪。

默认忽略 `_logs/`、`exports/`、`.graphify/cache/`、`.graphify/generated/`。当前实现仍写入前两者；后两者为未来布局预留。
删除快照不会删除知识，但会失去之前的改动基线和链接保护比较基线；重新 export 建立新基线。

## 原始证据与附件

| 材料 | 建议 |
|---|---|
| 小型 Markdown、文本 | 普通 Git，便于逐行审查 |
| 需要版本化的 PDF、图片或较大二进制 | 可选择 Git LFS；所有协作者需具备相应 LFS 访问能力 |
| 大量音视频、体积很大的附件 | 外部对象存储，维护 URI、SHA-256、captured_at 清单和访问说明 |

模板不会全局忽略 PDF、视频或 raw，避免证据在备份中悄然缺失。根据实际存储策略设置 `.gitattributes` 或定向 ignore。
LFS 与对象存储需要单独验证取回文件；Git 提交本身不代表已备份全部二进制证据。SHA-256 清单尚未由 CLI 自动生成。

## 建立仓库与备份

在 Vault 中 `git init`，先审查待跟踪文件，再提交并添加由用户创建的私有远端。
定期备份 Git 历史和未跟踪原始证据；不要把真实 Vault 复制到引擎仓库的 fixture 目录。
引擎升级前也备份 Vault 的 AGENTS/schema/skills 定制；init 默认不覆盖这些文件。
