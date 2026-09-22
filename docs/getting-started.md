# 安装与首次使用

完整首次材料与 Codex 对话示例见 [README](../README.md#前-10-分钟)。本页补充环境、初始化和验收细节。

## 环境

核心 CLI 只依赖 Python 3.11+ 标准库，安装时需要构建工具。Obsidian 和 Codex 分别负责阅读与语义处理，CLI 不调用大模型。
在引擎项目中创建 `.venv`，激活后运行 `python -m pip install -e .`。Windows 若激活受执行策略限制，可直接使用：

```powershell
& 'C:\path\obsidian-graphify\.venv\Scripts\python.exe' -m pip install -e 'C:\path\obsidian-graphify'
& 'C:\path\obsidian-graphify\.venv\Scripts\graphify.exe' init 'C:\path\MyGraphifyVault'
```

Linux/macOS 可直接使用 `/path/obsidian-graphify/.venv/bin/graphify`。
新终端需重新激活引擎环境，或使用完整可执行文件路径；无需在每个 Vault 重复创建 Python 环境。

## 独立 Vault 与 Codex

```bash
graphify init ../MyGraphifyVault
graphify --vault ../MyGraphifyVault status
graphify --vault ../MyGraphifyVault lint
```

在目标目录中也可执行 `graphify init .`。init 的目标始终是位置参数，不受 `GRAPHIFY_VAULT` 影响。
已有文件默认逐个保留；`--force` 只覆盖脚手架中同名文件，使用前先备份用户定制。普通重跑不会更新旧规则。

init 额外复制 `schema/`、`templates/`、`.codex/skills/`，因此 wheel 安装不需要源码仓库也能使用。
将 Vault 文件夹作为 Codex 工作目录，先让它读取 AGENTS 和对应 skill。无需假设当前客户端会自动发现 `.codex/skills`。

`graphify.toml` 当前仅是根目录发现标记，没有可配置路径字段。嵌套目录使用最近的标记；相对 `--vault` 和环境变量路径相对当前工作目录解析。

## 可核验的公开样例

源码仓库的 `tests/fixtures/sample-vault` 是虚构温室实验，包含 1 份 raw、2 个 Source、3 个 Claim、2 个 Wiki、2 个 Index，以及双向冲突与跨页关系。
复制样例到临时目录后可以自由验证；它不包含真实用户知识：

```bash
graphify --vault tests/fixtures/sample-vault lint
graphify --vault tests/fixtures/sample-vault status
graphify --vault tests/fixtures/sample-vault lookup "光照实验"
graphify --vault tests/fixtures/sample-vault impact "_graphify/sources/温室记录甲.md"
graphify --vault tests/fixtures/sample-vault export
```

在引擎仓库根目录执行以上命令。`status` 应显示 raw 共 1 份、知识笔记共 9 份；export 应产生 10 个节点。
首次 lint 提示缺少保护快照可接受。export 建立 `_logs/link-manifest.json` 和 `_logs/vault-state.json`，同时生成 `exports/` 文件。
这些派生数据不提交 Git。

## 完成首次 ingest 的标准

原材料保留；Source 能追溯原材料；Claim 有证据与边界；Wiki 只在足以综合时创建；lint 没有错误。
模板中的 Templater 表达式只是编写提示：没有该插件时由 Codex 替换为实际日期，不需要安装它才能用 CLI。
