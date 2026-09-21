# Obsidian Graphify 使用说明

Graphify 的目标不是只存笔记，而是把原材料持续编译成可以查询、关联、维护和导出的知识图谱。

## 公开仓库边界

这个仓库只发布可复用的 Graphify 工作流：规则、模板、Codex skills、维护脚本和测试。实际知识库内容、Source 证据、原始材料、日志、导出、Obsidian 个人状态、Smart Connections 索引和媒体不进入公开 Git 历史。

`compile-media` 是现有的实验性接口；公开仓库不包含媒体素材、本机 OCR 模型或生成产物。

## 快速开始

```bash
git clone https://github.com/AltraDxx/obsidian-graphify.git
cd obsidian-graphify
python3 -m venv .venv
mkdir -p raw/inbox "知识簇" _graphify/sources _graphify/indexes _logs exports
```

然后将这个目录作为 Obsidian vault 打开，参考 `schema/obsidian-setup.md` 配置视图，再使用 `templates/` 创建首批笔记。核心脚本只依赖 Python 3.11 或更高版本的标准库。

验证安装：

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/graphify.py lint
.venv/bin/python scripts/graphify.py status
```

核心链路：

```text
Raw -> Source -> Claim -> Wiki -> Index / Search / Ask
```

## 目录结构
- `知识簇/<知识簇>/`：主要阅读区。每个文件夹是一个知识簇，根目录放 Wiki 和 `_索引.md`。
- `知识簇/<知识簇>/命题/`：该知识簇下的原子命题。
- `raw/inbox/`：原材料入口。网页、PDF 摘要、项目材料、外部对话、视频链接、问题和临时记录都先进入这里。
- `_graphify/sources/`：证据页。保留材料原本说了什么、证据锚点在哪里。
- `_graphify/indexes/`：全库索引和 Graphify 操作索引。
- `_graphify/dashboards/`：内部诊断视图，不作为日常入口。
- `处理清单.md`：用户指定本批次要处理的材料、Wiki、Claim 或 Source。
- `schema/`、`templates/`、`.codex/skills/`：规则、模板和 Codex workflow。
- `_logs/` 和 `exports/`：机器生成的日志、快照和图谱导出。

## Source、Claim、Wiki、Index
- Source：证据，回答“材料原本说了什么”。问题本身不是 Source，除非用户明确要把完整对话作为材料保留。
- Claim：最小可追踪命题，回答“当前证据支持什么判断”，并维护适用范围、边界、冲突和状态。
- Wiki：综合知识单元，围绕自由文本 `core_focus` 组织多个 Claim，把知识讲透；不强制问题导向、类型枚举或固定段落。
- Index：浏览结构，回答“这个知识簇或操作入口包含哪些主题，应该从哪里读起”。

Claim 不是 Wiki 的缩略版，Wiki 也不是单条 Claim 的扩写。Claim 负责证据命题化与真实性边界；Wiki 负责命题综合、解释结构、机制、边界、应用和关系。
未被任何 Wiki 吸收的 Claim 仍然合法存在，继续留在 `知识簇/<知识簇>/命题/`；只有后续形成稳定主题时，才新建 Wiki 用 `claim_refs` 或 `summary_claim_refs` 指回这些 Claim，不复制第二份正文。

## Obsidian 怎么看
- 左侧文件浏览：主要看 `知识簇/`；Graphify 操作入口从 `_graphify/indexes/Graphify知识库索引.md` 进入。
- 默认关系图谱：显示 `知识簇/` 下的 Wiki、知识簇 `_索引.md`，以及带 `graph_role: standalone_claim` 的待综合 Claim；不显示 Source 或 Graphify 操作索引。
- Smart Connections：作为相邻内容召回，优先显示 `type:claim` 和 `type:wiki`，不负责定义知识簇结构。
- 书签留给用户个人复查、稍后阅读或不确定内容；Graphify 不自动写书签。

补充定义：
- 待综合 Claim：还没有被任何 Wiki 的 `claim_refs` 或 `summary_claim_refs` 引用的 Claim。
- orphan：Obsidian 链接意义上的孤立页，即没有 `inlinks`、也没有 `outlinks`。它不等于“待综合 Claim”。

## 提问方式
普通问题可以直接问：

```text
query RAG 和微调的边界是什么？
```

更推荐在看到某个 Wiki 页时直接问：

```text
围绕 [[RAG、上下文与微调边界]]，我有个问题：……
```

回答流程：
1. 先用 `.venv/bin/python scripts/graphify.py lookup "<主题>"` 路由到知识簇索引或 Wiki；它先看标题、aliases、tags、frontmatter、`快速把握` 和正文开头，再在候选簇内查 Wiki/Claim。
2. 再顺着 Wiki 的 `claim_refs` 读 Claim；只有需要核验证据时才继续读 Source。
3. 用最小足够的证据链回答。
4. 默认不每轮自动入库。

## 什么时候入库
不用每轮对话都判断入库。以下情况才同步：
- 你明确说“请同步知识库”。
- 你在 Obsidian 里改了 Source、Claim 或 Wiki，并要求同步。
- 几轮对话后形成了可复用的新材料或新判断。
- 新内容改变了知识簇结构，需要更新 Index。

入库顺序：
1. 用户直接新建的问题或材料先放 `raw/inbox/`。
2. 新证据、案例、观察或纠错确认后进入 `_graphify/sources/`。
3. 从 Source 抽取或修正 `知识簇/<知识簇>/命题/`。
4. 多个稳定 Claim 再综合进 `知识簇/<知识簇>/` 的 Wiki。
5. 知识簇主题、核心页或跨簇关系变化时更新 `_索引.md` 或 `_graphify/indexes/`。

## 处理清单
`处理清单.md` 是用户指定处理范围的入口。

- 没有清单或清单为空：Graphify 默认全量处理。
- 有未完成条目：只处理清单条目及必要上下游。
- 支持 `[[wikilink]]`、反引号路径和普通路径。
- 处理完成后勾选条目，并在“处理记录”写简短结果。

常用命令：

```bash
.venv/bin/python scripts/graphify.py scope
.venv/bin/python scripts/graphify.py scope 处理清单.md
.venv/bin/python scripts/graphify.py scan --scope 处理清单.md
.venv/bin/python scripts/graphify.py lint --scope 处理清单.md
```

## 模板原则
模板只是参考检查清单，不是必填结构。Wiki 编译以“把知识讲透”为准，可以按需使用机制、公式、案例、对比、流程、边界、争议或其他更合适的结构。

`快速把握` 推荐保留，用来帮助快速阅读和 lookup 路由；不再强制 `## 摘要`。`用户提问与复盘` 只记录真正影响知识更新的问题、纠错、裁决或复盘。

## 常用命令
```bash
.venv/bin/python scripts/graphify.py scan
.venv/bin/python scripts/graphify.py changes
.venv/bin/python scripts/graphify.py lookup "rag"
.venv/bin/python scripts/graphify.py impact "_graphify/sources/xxx.md"
.venv/bin/python scripts/graphify.py status
.venv/bin/python scripts/graphify.py lint
.venv/bin/python scripts/graphify.py export
```
