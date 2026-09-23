# 本次优化说明与验收记录

本次优化把 Graphify 从“源码目录同时充当个人 Vault”的工作流，改造成可安装、可管理多个独立 Vault 的引擎。知识模型保持 `Raw -> Source -> Claim -> Wiki -> Index`，没有引入数据库或改变语义写回原则。

原始基线：`de67dc4bc612dfb1697ba06f411763fe60a95d27`。完整实现和审查记录见 [PR #1](https://github.com/AltraDxx/obsidian-graphify/pull/1)。本文说明实现范围；分支及 CI 实时状态以 GitHub 为准。

## 改动前的问题

- 约 2,660 行的脚本混合参数、路径、解析、图关系、命令与媒体逻辑。
- 按脚本位置定位 Vault，安装后不能自然管理独立知识库。
- 包配置缺少可用 CLI，没有初始化入口。
- README 重规则、轻操作，终端命令与 Codex 对话区分不充分。
- 一个 AGENTS 混用源码开发和知识维护，规则重复；CI 缺少完整合成知识链与安装验证。

## 原规范逐项核对

以下对应原优化规范 A–R。所有本轮必须实施项均已完成；明确要求独立设计的迁移不属于遗漏。

| 原规范 | 实施结果 | 验证或入口 |
|---|---|---|
| A：保留知识模型 | 保留四种笔记、显式关系、路径/标题/alias、受保护链接与写回原则 | 原有 29 项回归测试；[笔记规范](../schema/note-spec.md) |
| B–C：角色与上手 | 三层职责、安装、init、raw、Codex ingest、预期结果、lint、query、同步 | [README](../README.md)、[入门](getting-started.md) |
| D–E：文档分层 | schema 为规范；根 AGENTS 指导引擎开发；Vault AGENTS 指导知识维护 | [根指南](../AGENTS.md)、[Vault 指南](../vault-template/AGENTS.md) |
| F：Vault 解耦 | VaultContext；--vault → GRAPHIFY_VAULT → 向上发现 graphify.toml → cwd | 优先级、源码外、多 Vault 隔离测试 |
| G–H：包与入口 | src 包按职责拆分；graphify、模块与旧脚本入口 | [包配置](../pyproject.toml)、[安装检查](../scripts/check_wheel.py) |
| I：init | 初始化独立 Vault 并提供规则、模板、skills；默认保留文件 | 幂等、force、冲突预检、wheel 资源检查 |
| J：公开 fixture | 1 raw、2 Source、3 Claim、2 Wiki、簇/全库两个 Index；双向冲突与跨页关系 | [合成 Vault](../tests/fixtures/sample-vault) |
| K–L：测试与 CI | 根发现、安装、init、lookup/impact、引用、无媒体依赖、lint/status/export | [CI](../.github/workflows/ci.yml)，Python 3.11/3.13 |
| M–N：Git 与贡献 | 公开引擎/私有 Vault 分离，Git/LFS/外部存储、开发安装、完整验证 | [Git 策略](vault-git-strategy.md)、[贡献](../CONTRIBUTING.md) |
| O：skills | 四个 skill 有触发、排除、输入输出和验证要求，引用规范 | [.codex/skills](../.codex/skills)，格式及安装后链接检查 |
| P：UID 迁移 | 按要求不与本次重构混合，保留原引用契约 | [后续范围](phase-2.md) |
| Q：候选改进 | 已记录 Raw immutable、manifest、派生 graph_role、provider；内容哈希检测已提前实现 | [后续范围](phase-2.md) |
| R：验收 | 核心能力、包、兼容入口、独立 Vault、init、fixture、文档与隐私边界均有证据 | 下方验证记录 |

## 代码与目录变化

```text
src/obsidian_graphify/
├── cli.py                    参数与分发
├── config.py                 Vault 发现、路径、作用域
├── model.py                  模型与常量
├── parsing.py / refs.py       Markdown、frontmatter、引用
├── graph.py / vault.py        图关系、快照、文件收集
├── utils.py                  辅助函数
├── commands/                 init、scope、lookup、lint、维护命令
└── media/                    可选媒体类型、路径、后端、适配器
vault-template/               独立 Vault 脚手架
schema/                      数据与工作流规范
templates/                   编写参考模板
.codex/skills/               任务执行指南
tests/fixtures/sample-vault/  合成知识库
scripts/graphify.py           兼容入口
scripts/check_wheel.py        独立安装验收
docs/                        用户说明与开发交接
```

wheel 从权威源文件复制 Vault 资源，不要求用户保留源码；editable 直接读取源资源，无需人工维护两份规则。

## 追加的内容哈希改进

旧版 changes 仅比较 mtime 与大小：单纯时间戳变化可能误报，同大小且时间戳未变的真实编辑可能漏报。
现在 changes/export 流式计算 SHA-256，新基线按内容比较；旧基线继续可读，changes --save 或 export 后升级。
lookup/status 等普通命令不额外计算哈希。大量媒体会增加 changes/export 的读取耗时，本轮没有引入哈希缓存或监控器。

## 验证证据与边界

- 原有 29 项回归测试保留；新增根发现、安装、初始化、图谱和哈希测试后，本地共 46 项通过。
- 包重构阶段对比旧新版本 8 个核心命令，归一化 Vault 路径后输出一致；JSON 图数据和 GraphML 一致。哈希变化另有专项测试。
- python -m build 构建 sdist，并从 sdist 构建 wheel。
- check_wheel.py 在源码外的新虚拟环境安装 wheel，验证安装位置、资源字节、Agent 文档链接、保留用户定制与样例命令。
- CI 在 Ubuntu 的 Python 3.11/3.13 上测试、构建、隔离安装和验证 fixture；历史通过记录见 [CI 35709211621](https://github.com/AltraDxx/obsidian-graphify/actions/runs/35709211621)，合并还需检查最新提交。
- 阻止媒体模块与第三方 OCR 导入时，核心命令仍正常运行。
- 只使用虚构温室材料，无真实用户知识、凭据或媒体；运行时、虚拟环境和构建产物不提交。

未把 Codex 语义生成质量或 Obsidian GUI 操作声称为自动化验证结果；真实 OCR/transfer-platform 联调也不属于本轮验证。

## 升级与兼容

旧脚本保留，但 Vault 不再按脚本位置定位；从其他目录调用时须显式 --vault，或使用环境变量/发现标记。
graphify.toml 当前只是发现标记，没有自定义目录布局配置。
已有 Vault 的规则不会随引擎升级自动覆盖；重新 init 默认保留。更新时先比较用户定制，不把 --force 当作迁移方案。
旧模块全局路径 monkeypatch 不再作为集成契约，Python 集成使用 VaultContext/use_vault。

运行时仍使用 _logs/ 和 exports/，Raw ingest 仍按原工作流标记 processed，节点身份仍依赖路径；这些边界没有暗中改变。
升级前备份 Git 历史和未跟踪原始证据；回退引擎不能代替恢复用户内容。本次已保留原始历史与优化提交 bundle，机器路径仅记录于本地交付报告。

## 后续开发

继续开发请读 [Agent 开发与接手指南](DEVELOPMENT_GUIDE.md)。UID、Raw immutable、派生状态迁移必须先对齐数据契约，再提供 dry-run、测试与回滚，不能作为顺手重构混入。
