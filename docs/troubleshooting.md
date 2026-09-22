# 常见问题

## graphify 找不到

激活引擎 `.venv`，用 `python -m pip install -e .` 安装。新终端再次激活，或直接运行该环境的 graphify 可执行文件；详见 [安装](getting-started.md)。

## 数量为零或选错 Vault

查看 `graphify status` 首行路径。根目录优先级为 `--vault`、`GRAPHIFY_VAULT`、向上发现 `graphify.toml`、cwd。
显式运行 `graphify --vault <实际目录> status`。旧脚本也遵循新优先级，从其他目录调用时需指定 Vault。
不存在的路径会报错，不会默默创建；先运行 `graphify init <目录>`。

## lint 提示没有快照

新 Vault 尚无 `_logs/link-manifest.json`，此警告不表示结构错误。确认知识内容后运行 `graphify export`。
引用损坏或必填字段缺失属于错误，修复后再导出；不要用新快照掩盖用户链接丢失。

## raw 放进去后没有 Source / Wiki

CLI 只提供维护，不执行语义 ingest。把 Vault 作为 Codex 工作目录，并复制 README 的 ingest 请求。
Source / Claim 由 Codex 依据证据创建；材料不足时不强制产生 Wiki。

## Codex 没显示 Graphify skills

检查 init 是否生成 `.codex/skills/*/SKILL.md`。直接要求 Codex 阅读这些文件与 AGENTS；不要依赖客户端自动发现。
在引擎目录工作时，根 AGENTS 指导源码开发；知识整理应在 Vault 目录进行。

## compile-media 失败

此功能当前只支持 `raw/inbox/video-visual/` 下的视频。配置 `TRANSFER_PLATFORM_BIN` 为独立工具的完整路径；核心命令不需要它。
运行依赖与产物见 [媒体编译](media.md)。
