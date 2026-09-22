# 贡献指南

## 本地开发

```bash
python -m venv .venv
```

激活方式见 README，随后运行：

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

`check_wheel.py` 选择 dist 中当前版本 wheel，创建临时干净环境并从源码目录外执行 CLI、init 与合成 Vault 检查。所有命令必须成功；首次 lint 缺少快照的提示允许存在。
CI 覆盖 Python 3.11 与 3.13，并验证发行包包含 Vault 资源。

## 文档与数据

数据与工作流规则以 schema 为准；修改 contract 时同步 validator、template、tests、docs。不要在 README/AGENTS/skills 重复完整规则。
公共测试只能使用明确标识的合成数据，不允许真实用户材料、私人 Source、凭据、个人 Obsidian 状态或媒体。
根 ignore 保护真实 Vault；合成样例仅放 `tests/fixtures/`，不通过 force-add 绕过数据边界。

## 分支与提交

目前保留 `main`（稳定）与 `develop`（集成）；默认非琐碎开发从 develop 建短期分支，使用 PR，经测试后 squash merge，再通过 PR 发布至 main。
本次重构开始时两者指向同一快照，未删除或改写 develop。
少量维护者后续可采用 trunk-based：受保护 main + 短期 topic branch + PR + squash + release tag；仓库维护者确认后再切换，不能仅靠改文档声称已配置保护规则。

提交应聚焦，按需使用 `feat:`、`fix:`、`refactor:`、`docs:`、`test:`。不强推已发布历史。
变更记录采用 Keep a Changelog 分类，版本遵循 SemVer；0.x 不兼容改动必须明确记录。
