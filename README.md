# Obsidian Graphify

把原材料整理成可查询、可维护、能追溯证据的知识：

`Raw -> Source -> Claim -> Wiki -> Index`

Graphify 是一套**文件规范 + Agent 工作流 + 确定性维护 CLI**。它不是 Obsidian 插件、向量数据库、自动 RAG 服务或每轮聊天自动入库的记忆系统；不安装 Smart Connections 也能使用。

| 角色 | 负责什么 |
|---|---|
| Obsidian | 人工阅读、编辑、浏览知识簇与图谱 |
| Codex | 理解材料，执行 ingest、query、sync、curate，生成和维护知识笔记 |
| Graphify CLI | 扫描、路由、校验、影响分析、状态检查与图导出 |

CLI 不生成语义知识；下文的终端命令与 Codex 对话分别标明。

## 前 10 分钟

### 1. 安装

准备 Python 3.11+、Git、Obsidian 和可访问本地文件的 Codex。

**在终端中：**

```bash
git clone https://github.com/AltraDxx/obsidian-graphify.git
cd obsidian-graphify
python -m venv .venv
```

Windows PowerShell 激活：

```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS 激活：

```bash
source .venv/bin/activate
```

激活后，在同一终端运行：

```bash
python -m pip install -e .
graphify --help
graphify init ../MyGraphifyVault
cd ../MyGraphifyVault
```

`init` 创建目录、配置、AGENTS、schema、模板和 `.codex/skills`；默认保留已有文件。无需安装媒体依赖。
在 Obsidian 中选择 **Open folder as vault**，打开 `MyGraphifyVault`。日常从 `知识簇/` 阅读。

### 2. 放入第一份材料

在 Vault 中创建 `raw/inbox/rag-notes.md`：

```markdown
# RAG notes

RAG 在推理阶段检索外部知识，把相关材料加入上下文，通常不修改模型权重。
检索材料可能过时或不相关，因此回答仍需要核验证据。
```

### 3. 让 Codex 整理

在 Codex 中将 **MyGraphifyVault 文件夹**作为任务工作目录。下列文字是**在 Codex 对话框输入**的请求：

```text
请读取 AGENTS.md、schema/note-spec.md、schema/workflows.md，
以及 .codex/skills/graphify-ingest/SKILL.md，按 ingest workflow 处理：
raw/inbox/rag-notes.md

创建或更新必要的 Source，提取最小可追踪 Claim。
只有多个 Claim 足以形成稳定主题时才创建 Wiki，不要为了示例强行生成。
完成后运行 graphify lint，告诉我创建或修改了哪些文件。
若当前终端找不到 graphify，请使用引擎项目 .venv 中的可执行文件并指定 --vault。
```

这些工作流文件已由 init 写入 Vault；若 Codex 没有自动列出 skill，明确读取上述文件即可。CLI 和 Obsidian 不会自行执行 ingest。

成功后可看到类似结构（具体命名、是否生成 Wiki 由材料决定）：

```text
raw/inbox/rag-notes.md
    ↓ Codex ingest
_graphify/sources/rag-notes.md
    ↓
知识簇/AI/命题/RAG通常不修改模型权重.md
知识簇/AI/命题/检索材料需要核验.md
    ↓ 满足综合条件时
知识簇/AI/RAG.md
```

### 4. 检查并提问

**在已激活环境的终端中，位于 Vault 目录：**

```bash
graphify status
graphify lint
graphify lookup "RAG"
```

`status` 显示 Vault 路径与各类笔记数量；`lint` 无结构错误即退出 0。首次提示没有链接快照是正常的，可运行 `graphify export` 建立快照。
`lookup` 输出 `Route matches`、`Knowledge matches` 等区域，Wiki 命中包含 `section=...`；无相关知识时会报告没有命中，它不会代替 Codex 回答。

**在 Codex 中输入：**

```text
请按 .codex/skills/graphify-query/SKILL.md，基于当前 Vault 回答：
RAG 是否会修改模型权重？检索后为什么仍要核验证据？
先用 lookup 路由，再按需要读取 Wiki、Claim 和 Source，引用笔记。
证据不足时明确说明。这次不要写回知识库。
```

需要保存新结论时，再在 Codex 中输入：

```text
刚才的结论值得保留，请按同步流程更新知识库。
优先更新已有 Source、Claim、Wiki，避免重复创建，并运行 lint。
```

## 日常操作

- **新增材料**：放入 `raw/inbox/`，用 `graphify changes` 查看，再让 Codex ingest。
- **限定批次**：编辑 `处理清单.md`，用 `graphify scope 处理清单.md` 查看；不传清单参数时 CLI 维持全量范围。
- **只提问**：让 Codex query，默认不写回。
- **改动 Source 后同步**：运行 `graphify changes` 和 `graphify impact "_graphify/sources/文件.md"`，让 Codex 按 Claim → Wiki → Index 更新。
- **定期整理**：让 Codex 使用 curation skill 检查冲突、过期知识、重复内容和弱关联。

| 常用终端命令 | 用途 |
|---|---|
| `graphify scan` | 重建待处理清单 `_logs/pending.md` |
| `graphify changes` | 对比上次快照；`--save` 保存新基线 |
| `graphify scope 处理清单.md` | 展开清单与必要上下游 |
| `graphify lookup "主题"` | 查找知识入口和相关笔记 |
| `graphify impact "路径或标题"` | 分析下游影响 |
| `graphify status` | 查看数量与状态 |
| `graphify lint` | 校验结构、引用与链接保护 |
| `graphify export` | 导出 JSON、GraphML、摘要并更新快照 |

## 源码仓库与私有 Vault

本公开仓库只维护代码、规范、模板、skills 和合成测试材料。真实知识建议保存在**独立私有 Git 仓库**。
引擎安装一次即可管理多个 Vault：

```bash
graphify --vault ../MyGraphifyVault lint
```

根目录优先级：`--vault` → `GRAPHIFY_VAULT` → 从当前目录向上找到 `graphify.toml` → 当前目录。
完整目录和 Git/LFS 策略见 [Vault Git 管理](docs/vault-git-strategy.md)。

## 可选能力与参考

- [详细入门](docs/getting-started.md)：新终端、独立安装与合成样例
- [常见问题](docs/troubleshooting.md)：路径、环境、警告、媒体
- [笔记规范](schema/note-spec.md) / [工作流规范](schema/workflows.md)：唯一权威规则
- [Obsidian 配置](schema/obsidian-setup.md)：图谱与可选 Smart Connections
- [媒体编译](docs/media.md)：实验性 `compile-media`，需独立 provider
- [贡献指南](CONTRIBUTING.md) / [开发入口](docs/DEVELOPMENT_GUIDE.md)
- [变更记录](CHANGELOG.md) / [第二阶段](docs/phase-2.md)

当前为 0.x 版本；升级前检查变更记录，特别注意 Vault 定位与规则副本的兼容说明。
