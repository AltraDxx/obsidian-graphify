# 开发与接手入口

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
