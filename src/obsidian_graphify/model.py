from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


RELATION_FIELDS = ("see_also", "part_of", "depends_on", "supports", "contradicts")


CLAIM_REF_FIELDS = ("claim_refs", "summary_claim_refs", "conflict_refs")


COMMON_WIKI_FIELDS = (
    "type",
    "status",
    "aliases",
    "source_refs",
    "tags",
    "confidence",
    "updated_at",
    "review_after",
    *RELATION_FIELDS,
)


SOURCE_FIELDS = ("source_kind", "traceability_level")


CLAIM_FIELDS = (
    "statement",
    "claim_type",
    "support_state",
    "verification_state",
    "scope",
    "boundary_note",
    "claim_origin",
    "claim_status",
    "conflict_refs",
)


WIKI_FIELDS = (
    "core_focus",
    "claim_refs",
    "summary_claim_refs",
    "draft_state",
    "version_no",
    "importance",
)


VALID_TYPES = {"source", "claim", "wiki", "index"}


VALID_STATUSES = {"draft", "reviewed", "verified", "stale", "archived"}


VALID_SUPPORT_STATES = {"supported", "weak", "conflicting", "unclear"}


VALID_VERIFICATION_STATES = {"source_supported", "cross_source_supported", "disputed", "unclear"}


VALID_CLAIM_STATUSES = {"active", "disputed", "outdated", "pending"}


STANDALONE_CLAIM_GRAPH_ROLE = "standalone_claim"


MARKDOWN_EXTENSIONS = {".md", ".markdown"}


RAW_EXCLUDED_DIRS = {"assets"}


IGNORED_FILENAMES = {".DS_Store"}


@dataclass
class Note:
    path: Path
    rel_path: str
    title: str
    body: str
    frontmatter: dict[str, Any]
    kind: str
    note_type: str
    status: str
    source_type: str
    aliases: list[str]
    tags: list[str]
    source_refs: list[str]
    relations: dict[str, list[str]]
    claim_refs: list[str]
    summary_claim_refs: list[str]
    conflict_refs: list[str]
    wikilinks: list[str]
    confidence: float | None
    updated_at: str
    review_after: str


@dataclass
class RawItem:
    path: Path
    rel_path: str
    title: str
    source_type: str
    status: str
    origin: str
    captured_at: str
    tags: list[str]
    is_markdown: bool
    frontmatter: dict[str, Any]
    body: str
    wikilinks: list[str]


@dataclass
class Edge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class LookupUnit:
    note_path: str
    note_type: str
    section: str
    text: str


@dataclass(frozen=True)
class LookupMatch:
    note: Note
    score: float
    section: str


@dataclass(frozen=True)
class RelatedMatch:
    path: str
    score: int
    kinds: tuple[str, ...]
