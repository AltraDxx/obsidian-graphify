# Graphify 引擎开发指南

本目录是 Graphify 源码仓库，不是用户 Vault。知识库操作规则由 `vault-template/AGENTS.md` 提供。

## 稳定约束

- 保持 `Raw -> Source -> Claim -> Wiki -> Index` 模型、显式关系数组、受保护链接及中文优先命名。
- `schema/note-spec.md` 是数据规范，`schema/workflows.md` 是流程规范。schema contract 变化必须同步校验器、模板、测试和文档。
- 不把真实用户知识、Source、raw 证据或个人应用状态作为 fixture；测试内容仅使用明确标识的合成材料。
- CLI 必须与源码位置解耦；所有 Vault 路径来自 `VaultContext`，保持旧脚本命令入口和已有引用行为。
- 媒体功能为可选能力，核心命令不加载 OCR 等第三方运行依赖。
- README 负责上手，docs 负责操作说明，AGENTS/skills 引用 schema，不复制完整规范。
- init 默认保留用户文件；发行包必须携带可用的 Vault 规则、模板和 skills。
- 不自动删除 develop，不强推或重写已发布历史。分支与贡献流程见 CONTRIBUTING.md。
- 长期分支仅保留 main/develop；临时分支通过 PR 交付，用户要求收尾时核实已合并并备份后清理，不丢弃未合并工作。

## 验证门槛

修改 CLI 后运行 `python -m unittest discover -s tests -v`、`python -m build` 和 `python scripts/check_wheel.py`。
使用合成 fixture 运行 lint/status/export；执行 `git diff --check`。不可只以源码可运行代替安装验证。

## 接手入口

架构、调试、验证、交付与后续迁移入口见 [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)。优化验收见 [docs/OPTIMIZATION_SUMMARY.md](docs/OPTIMIZATION_SUMMARY.md)。未完成任务的状态见根目录 CONTEXT.md（如存在，先核对相关性）。
