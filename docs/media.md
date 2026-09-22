# 可选媒体编译

`compile-media` 是实验性接口，只接受 Vault 中 `raw/inbox/video-visual/` 下的受支持视频文件。

```bash
graphify --vault /path/to/vault compile-media raw/inbox/video-visual/demo.mp4
```

CLI 调用独立 `transfer-platform compile visual` 工具，传入 Markdown、sidecar 和 assets 输出路径。
优先用 `TRANSFER_PLATFORM_BIN` 指定可执行文件，其次检查 `TRANSFER_PLATFORM_ROOT` 下的虚拟环境和 PATH。
独立工具需要的 ffmpeg、OCR、模型与安装步骤由该工具负责。Graphify 的核心安装没有这些依赖。

产物位于 `raw/compiled/visual/` 与 `raw/assets/video-visual/`，包括视觉文本、图片和 OCR 区域 JSON；之后仍需 Codex ingest 进入正式 Source/Claim/Wiki。
`--force` 允许覆盖生成结果。保留的 Python 本地视觉后端供兼容与测试使用，运行时才导入 rapidocr/scenedetect；它不是当前 CLI 的默认 provider。
