# 变更记录

采用 Keep a Changelog 分类与 SemVer。

## [Unreleased]

### Fixed
- changes 使用 SHA-256 识别同大小且时间戳未变的内容修改，并忽略仅时间戳变化；旧快照保持兼容，保存后自动升级。

## [0.2.0] - 2026-09-22

### Added
- 可安装 Python 包与 graphify CLI；独立 Vault 根目录发现。
- graphify init，分发 Vault 指南、规范、模板与 skills；默认保留已有文件。
- 公开合成 Vault、独立 wheel 安装验证和 CI 检查。
- 中文首次使用流程、双仓库 Git 策略、故障排查与开发文档。

### Changed
- 单文件实现按配置、解析、图关系、命令和媒体职责拆分。
- 根 AGENTS 指导引擎开发，Vault AGENTS 指导知识操作。
- 根目录优先级改为 --vault > GRAPHIFY_VAULT > 向上发现 graphify.toml > cwd。
  旧脚本从其他目录调用时，需显式 --vault；不再自动定位脚本所在源码仓库。
- skills 引用规范并提供明确入口条件；知识模型和路径引用保持不变。

### Deprecated
- scripts/graphify.py 保留为兼容入口，新集成推荐使用已安装 graphify。

## 0.1.0 - 2026-09-21

- Publish the portable Graphify workflow, schemas, templates, Codex skills, maintenance script, and tests.
- Establish a public repository boundary that excludes personal vault content, local application state, generated data, and media.
- Add CI and a `main` / `develop` branch workflow.
