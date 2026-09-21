from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
GRAPHIFY_PATH = ROOT / "scripts" / "graphify.py"
CLUSTER_ROOT = ROOT / "知识簇"


def load_graphify():
    spec = importlib.util.spec_from_file_location("graphify", GRAPHIFY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GraphifyClaimModelTest(unittest.TestCase):
    def test_valid_types_are_source_claim_wiki_and_index_only(self) -> None:
        graphify = load_graphify()

        self.assertEqual(graphify.VALID_TYPES, {"source", "claim", "wiki", "index"})

    def test_note_model_tracks_claim_references_for_wiki_notes(self) -> None:
        graphify = load_graphify()

        note_field_names = {field.name for field in fields(graphify.Note)}

        self.assertLessEqual({"claim_refs", "summary_claim_refs", "conflict_refs"}, note_field_names)

    def test_cluster_claim_and_index_paths_infer_expected_note_types(self) -> None:
        graphify = load_graphify()

        self.assertEqual(
            graphify.infer_knowledge_kind(CLUSTER_ROOT / "AI产品经理学习" / "命题" / "RAG命题.md"),
            "claim",
        )
        self.assertEqual(
            graphify.infer_knowledge_kind(CLUSTER_ROOT / "AI产品经理学习" / "_claims" / "旧命题.md"),
            "claim",
        )
        self.assertEqual(
            graphify.infer_knowledge_kind(CLUSTER_ROOT / "AI产品经理学习" / "_索引.md"),
            "index",
        )
        self.assertEqual(
            graphify.infer_knowledge_kind(CLUSTER_ROOT / "AI产品经理学习" / "RAG边界.md"),
            "wiki",
        )

    def test_source_impact_traverses_source_to_claim_to_wiki(self) -> None:
        graphify = load_graphify()
        edges = [
            graphify.Edge("知识簇/AI/命题/rag.md", "_graphify/sources/rag-source.md", "source_ref"),
            graphify.Edge("知识簇/AI/RAG.md", "知识簇/AI/命题/rag.md", "claim_ref"),
            graphify.Edge("知识簇/AI/_索引.md", "知识簇/AI/RAG.md", "wikilink"),
        ]
        node_specs = {
            "_graphify/sources/rag-source.md": {"type": "source", "title": "RAG Source"},
            "知识簇/AI/命题/rag.md": {"type": "claim", "title": "RAG Claim"},
            "知识簇/AI/RAG.md": {"type": "wiki", "title": "RAG"},
            "知识簇/AI/_索引.md": {"type": "index", "title": "AI Index"},
        }

        impact = graphify.find_impacted_notes("_graphify/sources/rag-source.md", edges, node_specs)

        self.assertEqual(impact["claims"], ["知识簇/AI/命题/rag.md"])
        self.assertEqual(impact["wiki"], ["知识簇/AI/RAG.md"])
        self.assertEqual(impact["indexes"], ["知识簇/AI/_索引.md"])

    def test_cli_help_removes_local_model_capture_commands(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GRAPHIFY_PATH), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertNotIn("capture-omlx-current", result.stdout)
        self.assertNotIn("capture-server", result.stdout)
        self.assertNotIn("capture-chat", result.stdout)
        self.assertNotIn("oMLX", result.stdout)
        self.assertNotIn("local-model", result.stdout)

    def test_raw_inbox_defaults_to_raw_source_type(self) -> None:
        graphify = load_graphify()

        self.assertEqual(graphify.infer_source_type(ROOT / "raw" / "inbox" / "new-note.md"), "raw")

    def test_lint_rejects_active_wiki_referencing_inactive_claim(self) -> None:
        graphify = load_graphify()
        inactive_claim = SimpleNamespace(
            rel_path="知识簇/AI/命题/old.md",
            title="Old claim",
            body="## 当前证据如何支撑\n旧证据。\n",
            frontmatter={
                "type": "claim",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.4,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": [],
                "statement": "Old claim",
                "claim_type": "fact",
                "support_state": "conflicting",
                "verification_state": "disputed",
                "scope": "test",
                "boundary_note": "test",
                "claim_origin": "edited",
                "claim_status": "outdated",
                "conflict_refs": [],
            },
            kind="claim",
            note_type="claim",
            status="reviewed",
            source_refs=[],
            relations={field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=[],
            summary_claim_refs=[],
            conflict_refs=[],
            wikilinks=[],
            confidence=0.4,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )
        wiki = SimpleNamespace(
            rel_path="知识簇/AI/RAG.md",
            title="RAG",
            body="> [!abstract] 快速把握\nRAG 组织主轴。\n\n## 主线解释\n解释。\n",
            frontmatter={
                "type": "wiki",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.7,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": [],
                "page_intent": "any useful synthesis shape",
                "core_focus": "围绕 RAG 的知识边界组织解释",
                "claim_refs": ["知识簇/AI/命题/old.md"],
                "summary_claim_refs": [],
                "draft_state": "active",
                "version_no": 1,
                "importance": "medium",
            },
            kind="wiki",
            note_type="wiki",
            status="reviewed",
            source_refs=[],
            relations={field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=["知识簇/AI/命题/old.md"],
            summary_claim_refs=[],
            conflict_refs=[],
            wikilinks=[],
            confidence=0.7,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )

        errors, _warnings = graphify.validate_notes(
            [inactive_claim, wiki],
            {
                "知识簇/AI/命题/old.md": {"type": "claim", "title": "Old claim"},
                "知识簇/AI/RAG.md": {"type": "wiki", "title": "RAG"},
            },
            {
                "知识簇/ai/命题/old": "知识簇/AI/命题/old.md",
                "知识簇/ai/rag": "知识簇/AI/RAG.md",
            },
        )

        self.assertIn(
            "知识簇/AI/RAG.md: active wiki claim_refs cannot point to inactive claim: 知识簇/AI/命题/old.md",
            errors,
        )

    def test_wiki_core_focus_is_free_text_and_template_sections_are_optional(self) -> None:
        graphify = load_graphify()
        wiki = SimpleNamespace(
            rel_path="知识簇/AI/RAG.md",
            title="RAG",
            body="> [!abstract] 快速把握\n围绕 RAG、上下文和微调组织知识。\n\n## 主线解释\n正文。",
            frontmatter={
                "type": "wiki",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.7,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": [],
                "page_intent": "把知识讲透的任意组织方式",
                "core_focus": "RAG 和微调在产品决策里的边界",
                "claim_refs": [],
                "summary_claim_refs": [],
                "draft_state": "active",
                "version_no": 1,
                "importance": "medium",
            },
            kind="wiki",
            note_type="wiki",
            status="reviewed",
            source_refs=[],
            relations={field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=[],
            summary_claim_refs=[],
            conflict_refs=[],
            wikilinks=[],
            confidence=0.7,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )

        errors, _warnings = graphify.validate_notes(
            [wiki],
            {"知识簇/AI/RAG.md": {"type": "wiki", "title": "RAG"}},
            {"知识簇/ai/rag": "知识簇/AI/RAG.md"},
        )

        self.assertEqual(errors, [])

    def test_lint_requires_bidirectional_claim_conflicts(self) -> None:
        graphify = load_graphify()
        claim_a = SimpleNamespace(
            rel_path="claims/a.md",
            title="A",
            body="## 当前证据如何支撑\nA。\n\n## 可能冲突或待验证\n与 B 冲突。\n",
            frontmatter={
                "type": "claim",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.5,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": ["claims/b.md"],
                "statement": "A",
                "claim_type": "fact",
                "support_state": "conflicting",
                "verification_state": "disputed",
                "scope": "test",
                "boundary_note": "test",
                "claim_origin": "edited",
                "claim_status": "disputed",
                "conflict_refs": ["claims/b.md"],
            },
            kind="claim",
            note_type="claim",
            status="reviewed",
            source_refs=[],
            relations={**{field: [] for field in graphify.RELATION_FIELDS}, "contradicts": ["claims/b.md"]},
            claim_refs=[],
            summary_claim_refs=[],
            conflict_refs=["claims/b.md"],
            wikilinks=[],
            confidence=0.5,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )
        claim_b = SimpleNamespace(
            rel_path="claims/b.md",
            title="B",
            body="## 当前证据如何支撑\nB。\n",
            frontmatter={
                "type": "claim",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.5,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": [],
                "statement": "B",
                "claim_type": "fact",
                "support_state": "conflicting",
                "verification_state": "disputed",
                "scope": "test",
                "boundary_note": "test",
                "claim_origin": "edited",
                "claim_status": "disputed",
                "conflict_refs": [],
            },
            kind="claim",
            note_type="claim",
            status="reviewed",
            source_refs=[],
            relations={field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=[],
            summary_claim_refs=[],
            conflict_refs=[],
            wikilinks=[],
            confidence=0.5,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )

        errors, _warnings = graphify.validate_notes(
            [claim_a, claim_b],
            {
                "claims/a.md": {"type": "claim", "title": "A"},
                "claims/b.md": {"type": "claim", "title": "B"},
            },
            {"claims/a": "claims/a.md", "claims/b": "claims/b.md"},
        )

        self.assertIn("claims/a.md: conflict_refs must be bidirectional with claims/b.md", errors)
        self.assertIn("claims/a.md: contradicts must be bidirectional with claims/b.md", errors)

    def test_lint_requires_graph_role_for_standalone_claim(self) -> None:
        graphify = load_graphify()
        claim = SimpleNamespace(
            rel_path="知识簇/AI/命题/standalone.md",
            title="Standalone",
            body="## 当前证据如何支撑\n独立命题。\n",
            frontmatter={
                "type": "claim",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.6,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": [],
                "statement": "Standalone",
                "claim_type": "fact",
                "support_state": "supported",
                "verification_state": "source_supported",
                "scope": "test",
                "boundary_note": "test",
                "claim_origin": "edited",
                "claim_status": "active",
                "conflict_refs": [],
            },
            kind="claim",
            note_type="claim",
            status="reviewed",
            source_refs=[],
            relations={field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=[],
            summary_claim_refs=[],
            conflict_refs=[],
            wikilinks=[],
            confidence=0.6,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )

        errors, _warnings = graphify.validate_notes(
            [claim],
            {"知识簇/AI/命题/standalone.md": {"type": "claim", "title": "Standalone"}},
            {"知识簇/ai/命题/standalone": "知识簇/AI/命题/standalone.md"},
        )

        self.assertIn(
            "知识簇/AI/命题/standalone.md: standalone claim must set graph_role to standalone_claim",
            errors,
        )

    def test_lint_rejects_graph_role_on_claim_absorbed_by_wiki(self) -> None:
        graphify = load_graphify()
        claim = SimpleNamespace(
            rel_path="知识簇/AI/命题/absorbed.md",
            title="Absorbed",
            body="## 当前证据如何支撑\n已被吸收。\n",
            frontmatter={
                "type": "claim",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.6,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": [],
                "statement": "Absorbed",
                "claim_type": "fact",
                "support_state": "supported",
                "verification_state": "source_supported",
                "scope": "test",
                "boundary_note": "test",
                "claim_origin": "edited",
                "claim_status": "active",
                "conflict_refs": [],
                "graph_role": "standalone_claim",
            },
            kind="claim",
            note_type="claim",
            status="reviewed",
            source_refs=[],
            relations={field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=[],
            summary_claim_refs=[],
            conflict_refs=[],
            wikilinks=[],
            confidence=0.6,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )
        wiki = SimpleNamespace(
            rel_path="知识簇/AI/RAG.md",
            title="RAG",
            body="> [!abstract] 快速把握\n吸收命题。\n",
            frontmatter={
                "type": "wiki",
                "status": "reviewed",
                "aliases": [],
                "source_refs": [],
                "tags": [],
                "confidence": 0.7,
                "updated_at": "2026-05-12",
                "review_after": "2026-06-09",
                "see_also": [],
                "part_of": [],
                "depends_on": [],
                "supports": [],
                "contradicts": [],
                "page_intent": "把知识讲透的任意组织方式",
                "core_focus": "围绕 RAG 的知识边界组织解释",
                "claim_refs": ["知识簇/AI/命题/absorbed.md"],
                "summary_claim_refs": [],
                "draft_state": "active",
                "version_no": 1,
                "importance": "medium",
            },
            kind="wiki",
            note_type="wiki",
            status="reviewed",
            source_refs=[],
            relations={field: [] for field in graphify.RELATION_FIELDS},
            claim_refs=["知识簇/AI/命题/absorbed.md"],
            summary_claim_refs=[],
            conflict_refs=[],
            wikilinks=[],
            confidence=0.7,
            updated_at="2026-05-12",
            review_after="2026-06-09",
        )

        errors, _warnings = graphify.validate_notes(
            [claim, wiki],
            {
                "知识簇/AI/命题/absorbed.md": {"type": "claim", "title": "Absorbed"},
                "知识簇/AI/RAG.md": {"type": "wiki", "title": "RAG"},
            },
            {
                "知识簇/ai/命题/absorbed": "知识簇/AI/命题/absorbed.md",
                "知识簇/ai/rag": "知识簇/AI/RAG.md",
            },
        )

        self.assertIn(
            "知识簇/AI/命题/absorbed.md: claim absorbed by a wiki must not keep graph_role standalone_claim",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
