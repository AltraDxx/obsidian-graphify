from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAPHIFY_PATH = ROOT / "scripts" / "graphify.py"


def load_graphify():
    spec = importlib.util.spec_from_file_location("graphify_sync_plan", GRAPHIFY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GraphifySyncPlanTest(unittest.TestCase):
    def make_note(
        self,
        graphify,
        rel_path: str,
        title: str,
        note_type: str,
        *,
        body: str = "",
        tags: list[str] | None = None,
        relations: dict[str, list[str]] | None = None,
        claim_refs: list[str] | None = None,
        conflict_refs: list[str] | None = None,
    ):
        return graphify.Note(
            path=ROOT / rel_path,
            rel_path=rel_path,
            title=title,
            body=body,
            frontmatter={"type": note_type, "status": "reviewed"},
            kind=note_type,
            note_type=note_type,
            status="reviewed",
            source_type="",
            aliases=[],
            tags=tags or [],
            source_refs=[],
            relations=relations or {field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=claim_refs or [],
            summary_claim_refs=[],
            conflict_refs=conflict_refs or [],
            wikilinks=[],
            confidence=0.8,
            updated_at="2026-09-21",
            review_after="2026-10-21",
        )

    def test_docs_drop_local_model_entrypoints(self) -> None:
        files = [
            ROOT / "README.md",
            ROOT / "schema" / "obsidian-setup.md",
            ROOT / "schema" / "workflows.md",
            ROOT / "schema" / "note-spec.md",
        ]
        forbidden = [
            "capture-omlx-current",
            "capture-server",
            "oMLX",
            "Ollama",
            "LM Studio",
            "Open WebUI",
            "local-model",
        ]

        for path in files:
            content = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, content, msg=f"{path.relative_to(ROOT)} still mentions {marker}")

    def test_build_lookup_units_extracts_multiple_wiki_sections(self) -> None:
        graphify = load_graphify()
        note = self.make_note(
            graphify,
            "知识簇/测试/页面.md",
            "测试页面",
            "wiki",
            body=(
                "> [!abstract] 快速把握\n"
                "> - 核心概览。\n\n"
                "## 机制\n这里解释机制。\n\n"
                "## 边界\n这里说明边界。\n"
            ),
        )

        sections = {unit.section for unit in graphify.build_lookup_units(note)}

        self.assertIn("快速把握", sections)
        self.assertIn("机制", sections)
        self.assertIn("边界", sections)
        self.assertIn("正文预览", sections)

    def test_build_lookup_units_keeps_claims_atomic(self) -> None:
        graphify = load_graphify()
        note = self.make_note(
            graphify,
            "知识簇/测试/命题/原子命题.md",
            "原子命题",
            "claim",
            body="## 当前证据如何支撑\n当前证据支持这条命题。\n",
        )

        units = graphify.build_lookup_units(note)

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].section, "claim")

    def test_lookup_forces_conflict_claims_into_related_output(self) -> None:
        graphify = load_graphify()
        index_note = self.make_note(
            graphify,
            "知识簇/测试/_索引.md",
            "Alpha 索引",
            "index",
            body="## 概览\nAlpha 主题导航。",
            tags=["alpha"],
        )
        wiki_note = self.make_note(
            graphify,
            "知识簇/测试/Alpha 页面.md",
            "Alpha 页面",
            "wiki",
            body="> [!abstract] 快速把握\n> - Alpha 页面概览。\n\n## 主线解释\nAlpha 机制总览。",
            tags=["alpha"],
            claim_refs=["知识簇/测试/命题/Alpha机制.md", "知识簇/测试/命题/共享依赖.md"],
        )
        claim_a = self.make_note(
            graphify,
            "知识簇/测试/命题/Alpha机制.md",
            "Alpha 机制",
            "claim",
            body="## 当前证据如何支撑\nAlpha mechanism\n",
            tags=["alpha"],
            relations={
                **{field: [] for field in graphify.RELATION_FIELDS},
                "supports": ["知识簇/测试/命题/共享依赖.md"],
            },
            conflict_refs=["知识簇/测试/命题/相反命题.md"],
        )
        shared = self.make_note(
            graphify,
            "知识簇/测试/命题/共享依赖.md",
            "共享依赖",
            "claim",
            body="## 当前证据如何支撑\nshared dependency\n",
        )
        conflict = self.make_note(
            graphify,
            "知识簇/测试/命题/相反命题.md",
            "相反命题",
            "claim",
            body="## 当前证据如何支撑\nconflicting alpha view\n",
            conflict_refs=["知识簇/测试/命题/Alpha机制.md"],
        )

        notes = [index_note, wiki_note, claim_a, shared, conflict]
        data = {
            "wiki_notes": notes,
            "node_specs": graphify.build_node_specs([], notes),
            "alias_map": graphify.build_alias_map([], notes),
        }

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = graphify.command_lookup(data, query="Alpha mechanism", limit=1)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("知识簇/测试/命题/共享依赖.md", output)
        self.assertIn("知识簇/测试/命题/相反命题.md", output)

    def test_wiki_template_uses_core_focus_and_reference_sections(self) -> None:
        content = (ROOT / "templates" / "wiki.md").read_text(encoding="utf-8")

        for marker in ("core_focus:", "[!abstract] 快速把握", "模板是参考", "## 用户提问与复盘"):
            self.assertIn(marker, content)
        self.assertNotIn("## 摘要", content)
        self.assertNotIn("core_question:", content)

    def test_note_spec_documents_source_sync_and_claim_boundaries(self) -> None:
        content = (ROOT / "schema" / "note-spec.md").read_text(encoding="utf-8")

        for marker in (
            "core_focus",
            "graph_role: standalone_claim",
            "知识簇/<知识簇>/命题/*.md",
            "如果 Source 新增证据",
            "claim_status: active | disputed | outdated | pending",
            "问题本身不是 Source",
        ):
            self.assertIn(marker, content)

    def test_workflow_documents_question_and_conflict_rules(self) -> None:
        content = (ROOT / "schema" / "workflows.md").read_text(encoding="utf-8")

        for marker in (
            "处理清单.md",
            "默认取消“一问一页”的 question.md",
            "两个 Claim 都写 conflict_refs 和 contradicts",
            "过期 Claim 对应的 Wiki 正文必须删除或改写",
        ):
            self.assertIn(marker, content)

    def test_source_impact_output_includes_sync_guidance(self) -> None:
        graphify = load_graphify()
        data = {
            "node_specs": {
                "_graphify/sources/source.md": {"type": "source", "title": "Source"},
                "知识簇/AI/命题/claim.md": {"type": "claim", "title": "Claim"},
                "知识簇/AI/wiki.md": {"type": "wiki", "title": "Wiki"},
                "知识簇/AI/_索引.md": {"type": "index", "title": "Index"},
            },
            "alias_map": {},
        }
        edges = [
            graphify.Edge("知识簇/AI/命题/claim.md", "_graphify/sources/source.md", "source_ref"),
            graphify.Edge("知识簇/AI/wiki.md", "知识簇/AI/命题/claim.md", "claim_ref"),
            graphify.Edge("知识簇/AI/_索引.md", "知识簇/AI/wiki.md", "wikilink"),
        ]

        original_build_edges = graphify.build_edges
        graphify.build_edges = lambda _data: edges
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exit_code = graphify.command_impact(data, "_graphify/sources/source.md")
        finally:
            graphify.build_edges = original_build_edges

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Suggested sync order", output)
        self.assertIn("2. Review impacted Claims before touching Wiki notes or Indexes.", output)
        self.assertIn("3. Mark overturned Claims as disputed/outdated instead of deleting them.", output)

    def test_processing_list_parser_accepts_wikilinks_backticks_and_paths(self) -> None:
        graphify = load_graphify()
        refs = graphify.extract_scope_refs(
            """
            - [ ] [[RAG、上下文与微调边界]]
            - [ ] `知识簇/AI/命题/RAG.md`
            - [ ] 知识簇/AI/_索引.md
            - [x] [[已完成页面]]
            """
        )

        self.assertEqual(refs, ["RAG、上下文与微调边界", "知识簇/AI/命题/RAG.md", "知识簇/AI/_索引.md"])


if __name__ == "__main__":
    unittest.main()
