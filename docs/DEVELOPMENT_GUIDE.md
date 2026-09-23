# Agent 开发与接手指南

本文件面向继续修改 Graphify 引擎的 Agent。真实知识库维护使用 Vault 自己的 AGENTS 和 skills，不在源码仓库创建用户知识。

## 接手顺序

1. 阅读根 [AGENTS](../AGENTS.md)，确认用户目标、模型边界和验收标准。
2. 若根目录存在 CONTEXT.md，先核对任务与日期；它是本地未完成任务记录，可能未提交，新 clone 不一定存在。
3. 阅读 [优化验收](OPTIMIZATION_SUMMARY.md)、[CHANGELOG](../CHANGELOG.md) 与相关模块；用 Git 状态、分支和测试确认实际基线，不把历史报告当成实时状态。
4. 语义变更先读 [note-spec](../schema/note-spec.md)；流程变更先读 [workflows](../schema/workflows.md)，明确输入输出与兼容要求后实施。
5. 保留用户未提交改动。复杂长期任务维护 CONTEXT，普通任务不机械创建计划文件。

## 架构

`cli.py` 只处理参数与分发。`config.py` 提供不可变 VaultContext 和命令作用域；ContextVar 在命令结束或异常时恢复，避免连续调用串用 Vault。直接使用 Python 函数时可用 `with use_vault(VaultContext(path))` 明确作用域。

`model.py` 保存知识数据结构和常量，`parsing.py` 解析 Markdown/frontmatter，`refs.py` 处理引用规范化与别名，`graph.py` 构造关系和保护快照，`vault.py` 收集笔记与文件状态。
`commands/` 按职责组织 scope、lookup、lint、init 和维护命令；`media/` 隔离类型、路径、可选本地视觉后端和 transfer-platform 适配器。

`scripts/graphify.py` 是兼容入口，复用 package 代码。它保留历史只读函数导入方便过渡，但直接修改旧模块的全局路径或 monkeypatch 跨模块符号不再是支持的 Python API。
CLI 命令、参数、输出语义和知识引用保持兼容；根目录发现是明确改变，详见 CHANGELOG。

## 资源与文档权威

`schema/note-spec.md`、`schema/workflows.md` 为唯一规范；Agent 指南负责执行，README/docs 负责使用解释，templates 只是编写脚手架。
编辑源文件即可；`setup.py` 构建时将 vault-template/schema/templates/.codex/skills 复制进 wheel，避免源码维护双份规则。
editable 安装直接读取源码资源，独立 wheel 通过 importlib.resources 读取打包资源。

## 调试与验证

环境、测试与发行检查命令见 CONTRIBUTING。测试分为旧语义回归、包/根目录/init/fixture 集成测试，以及 `scripts/check_wheel.py` 的隔离安装检查。
新能力先在合成 fixture 的临时副本测试，不使用真实 Vault。CLI 报错先看 status 根路径，然后检查选定的命令模块和 schema。
当前不支持完整 YAML，只保持原有轻量 frontmatter 子集；不要在包重构时混入语义迁移。

## 开发环境与完整门槛

优先复用项目 .venv，没有时才 python -m venv .venv，不改全局 Python。
Windows 可直接用 .venv/Scripts/python.exe，Linux/macOS 用 .venv/bin/python；激活后命令通用：

```bash
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m build
python scripts/check_wheel.py
graphify --vault tests/fixtures/sample-vault lint
graphify --vault tests/fixtures/sample-vault status
graphify --vault tests/fixtures/sample-vault export
git diff --check
```

当前行为基线为 46 项测试，CI 为 Python 3.11/3.13；合理新增测试后数量可以增加。
首次 lint 缺少链接保护快照的警告允许存在；结构错误、导入错误、缺资源或安装失败不能放行。
schema 或 Vault 资源改动必须重新构建和验证 wheel，editable 成功不能代替独立安装。

## 修改位置与验证选择

| 需求 | 优先检查 | 验证 |
|---|---|---|
| 参数与根目录 | cli.py、config.py | 优先级、相对路径、源码外、多 Vault |
| 字段与类型约束 | schema、model.py、commands/lint.py、模板 | 正反例、旧 fixture、规范模板同步 |
| 引用与图 | refs.py、graph.py、commands/lookup.py | alias/歧义、保护链接、冲突、impact、JSON/GraphML |
| 变更检测 | vault.py、commands/maintenance.py | 同大小同时间戳编辑、时间戳变化、旧快照 |
| init/分发 | commands/init.py、setup.py、MANIFEST.in、vault-template | 保留用户文件、force、预检、wheel 资源链接 |
| 媒体 | media/、docs/media.md | fake backend、适配器、错误路径、核心无依赖 |
| 用户文档 | README、docs | 命令可执行、终端/Codex 区分、相对链接 |

哈希快照仅在 changes/export 开启，不为查询额外计算全库二进制哈希。旧快照没有 sha256 时仍比较 mtime+size，不能无迁移说明地移除兼容路径。

## Git、网络与交付

长期分支仅保留 main/develop。从 develop 建短期 topic 分支，PR 经最新提交 CI 通过后合入 develop，再通过发布 PR 合入 main。发布 PR 使用保留祖先关系的合并方式，之后可将 develop 快进到 main，避免长期分叉。

用户要求清理交付时，确认无待处理 PR、临时分支代码已合并且已备份，再删除临时远端/本地分支。不要只关闭未合并 PR 来凑零，也不丢弃他人的未交付工作。不强推 main/develop。

本次 Windows 环境中，PATH 内的 MSYS Git 与标准 Git for Windows 认证配置不同。遇到无凭据时先用 Get-Command git -All 确认程序与 credential helper，必要时使用标准 Git for Windows 的已登录环境；不要导出、打印或提交凭据。
GitHub 网络异常先确认本地代理 7890。账号 push 权限与 GitHub App installation 授权是两层检查，连接器 403 不等于账号无权；不放宽分支保护来绕过失败。

交付记录实际提交、CI、分支与 PR 状态，不用旧提交绿灯代替最新提交检查。更新开发文档；长期规则改变时同步根 AGENTS。

## 后续任务优先级

本次工程壳层与文档优化已完成，后续迁移由用户需求驱动，不自动扩大范围。

1. 稳定 UID：大量 rename/move 需求出现时，先选 UUIDv7/ULID 并写 ADR，定义 schema_version、旧引用兼容期、导出 ID 变化，再实现 dry-run、回滚和稳定身份测试。
2. Raw immutable 与证据 manifest：与 processed 流程一起设计，明确 URI、SHA-256、captured_at 和二进制存储职责；内容哈希快照不等于完整证据 manifest。
3. 派生状态/缓存：定义可重建内容与旧 _logs/exports 兼容迁移，再评估 graph_role 规范变化。
4. 媒体 provider：确认实际接入需求后扩展，不增加无用途的通用插件抽象。

迁移先在合成 Vault 副本验证，候选边界见 [phase-2.md](phase-2.md)。
