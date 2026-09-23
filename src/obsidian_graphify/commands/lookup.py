from __future__ import annotations

from collections import Counter
from collections import defaultdict
from pathlib import Path
from typing import Any
import re
from obsidian_graphify.graph import adjacency, build_edges
from obsidian_graphify.model import Edge, LookupMatch, LookupUnit, Note, RELATION_FIELDS, RelatedMatch
from obsidian_graphify.parsing import body_preview, extract_callout, extract_section, extract_top_level_sections
from obsidian_graphify.refs import normalize_ref
from obsidian_graphify.utils import as_string, listify


def command_lookup(data: dict[str, Any], query: str, limit: int = 5) -> int:
    wiki_notes: list[Note] = data["wiki_notes"]
    node_specs: dict[str, dict[str, Any]] = data["node_specs"]
    edges = build_edges(data)

    route_candidates: list[tuple[float, Note]] = []
    for note in wiki_notes:
        if note.note_type not in {"index", "wiki"}:
            continue
        score = score_match(query, title=note.title, rel_path=note.rel_path, aliases=note.aliases, tags=note.tags, body=route_text(note))
        if score > 0:
            route_candidates.append((score, note))

    route_candidates.sort(key=lambda item: (-item[0], item[1].rel_path))
    routes = route_candidates[:limit]
    route_clusters = infer_route_clusters([note for _score, note in routes])
    knowledge_candidates: list[LookupMatch] = []
    for note in wiki_notes:
        if note.note_type not in {"wiki", "claim"}:
            continue
        if route_clusters and not note_in_clusters(note, route_clusters):
            continue
        best_match = best_lookup_match(query, note)
        if best_match:
            knowledge_candidates.append(best_match)
    knowledge_candidates.sort(key=lambda item: (-item.score, item.note.rel_path, item.section))
    knowledge_matches = knowledge_candidates[:limit]
    if not routes and not knowledge_matches:
        print(f"No matches found for: {query}")
        return 1

    print(f"Lookup: {query}")
    print("")
    print("Route matches")
    matched_paths = []
    if routes:
        for score, note in routes:
            matched_paths.append(note.rel_path)
            tags = ", ".join(note.tags) if note.tags else "-"
            print(
                f"- {note.title} | path={note.rel_path} | type={note.note_type or '-'} | status={note.status or '-'} | score={score:.1f} | tags={tags}"
            )
    else:
        print("- No route matches; searched across all wiki and claim notes.")

    if knowledge_matches:
        print("")
        print("Knowledge matches")
        for match in knowledge_matches:
            matched_paths.append(match.note.rel_path)
            tags = ", ".join(match.note.tags) if match.note.tags else "-"
            print(
                f"- {match.note.title} | path={match.note.rel_path} | type={match.note.note_type or '-'} | status={match.note.status or '-'} | score={match.score:.1f} | section={match.section} | tags={tags}"
            )

    related_matches = build_related_matches(
        matched_paths=matched_paths,
        knowledge_matches=knowledge_matches,
        edges=edges,
        node_specs=node_specs,
        limit=limit,
    )

    if related_matches:
        print("")
        print("Related knowledge")
        for match in related_matches:
            node = node_specs.get(match.path, {"title": match.path, "type": "unknown", "status": ""})
            kinds = ", ".join(match.kinds)
            print(
                f"- {node.get('title', match.path)} | path={match.path} | type={node.get('type', 'unknown')} | status={node.get('status', '-') or '-'} | via={kinds} | score={match.score}"
            )

    print("")
    print("Suggested next step")
    if knowledge_matches:
        primary = knowledge_matches[0].note
        print(f"- Start from `{primary.rel_path}` and follow its Claim/Source chain only when evidence verification is needed.")
    else:
        primary = routes[0][1]
        print(f"- Start from `{primary.rel_path}` and then inspect the matching Wiki/Claim notes in that cluster.")
    return 0


def route_text(note: Note) -> str:
    fields = [
        extract_callout(note.body, "快速把握"),
        extract_section(note.body, "摘要"),
        as_string(note.frontmatter.get("core_focus")),
        as_string(note.frontmatter.get("core_question")),
        as_string(note.frontmatter.get("page_intent")),
        as_string(note.frontmatter.get("statement")),
        body_preview(note.body, limit=600),
    ]
    fields.extend(as_string(value) for value in listify(note.frontmatter.get("aliases")))
    fields.extend(as_string(value) for value in listify(note.frontmatter.get("tags")))
    return "\n".join(value for value in fields if value)


def knowledge_lookup_text(note: Note) -> str:
    fields = [
        route_text(note),
        as_string(note.frontmatter.get("scope")),
        as_string(note.frontmatter.get("boundary_note")),
        extract_section(note.body, "当前证据如何支撑"),
        extract_section(note.body, "适用边界"),
        extract_section(note.body, "主线解释"),
    ]
    return "\n".join(value for value in fields if value)


def claim_lookup_text(note: Note) -> str:
    fields = [
        route_text(note),
        as_string(note.frontmatter.get("support_state")),
        as_string(note.frontmatter.get("verification_state")),
        as_string(note.frontmatter.get("scope")),
        as_string(note.frontmatter.get("boundary_note")),
        extract_section(note.body, "当前证据如何支撑"),
        extract_section(note.body, "适用边界"),
        extract_section(note.body, "可能冲突或待验证"),
    ]
    return "\n".join(value for value in fields if value)


def build_lookup_units(note: Note) -> list[LookupUnit]:
    if note.note_type == "claim":
        text = claim_lookup_text(note)
        return [LookupUnit(note_path=note.rel_path, note_type="claim", section="claim", text=text)] if text else []
    if note.note_type != "wiki":
        return []

    units: list[LookupUnit] = []
    seen_sections: set[str] = set()
    quick_take = extract_callout(note.body, "快速把握")
    if quick_take:
        units.append(LookupUnit(note_path=note.rel_path, note_type="wiki", section="快速把握", text=quick_take))
        seen_sections.add("快速把握")

    for heading, content in extract_top_level_sections(note.body):
        if heading in {"用户提问与复盘"} or heading in seen_sections:
            continue
        units.append(LookupUnit(note_path=note.rel_path, note_type="wiki", section=heading, text=content))
        seen_sections.add(heading)

    preview = body_preview(note.body, limit=900)
    if preview:
        units.append(LookupUnit(note_path=note.rel_path, note_type="wiki", section="正文预览", text=preview))
    return units


def lookup_section_priority(note_type: str, section: str) -> int:
    if note_type == "claim":
        return 0
    priorities = {
        "快速把握": 0,
        "主线解释": 1,
        "先把这三个东西分开": 2,
        "为什么这条边界决定你会不会走错路": 3,
        "检索到底是怎么发生的": 4,
        "Chunking 为什么会直接决定上限": 5,
        "什么时候该用 RAG，什么时候不该": 6,
        "最容易混淆的几个地方": 7,
        "它和哪些知识要一起看": 8,
        "当前证据如何支撑": 9,
        "适用边界": 10,
        "证据来源": 20,
        "正文预览": 30,
    }
    return priorities.get(section, 15)


def best_lookup_match(query: str, note: Note) -> LookupMatch | None:
    best: LookupMatch | None = None
    for unit in build_lookup_units(note):
        score = score_match(
            query,
            title=note.title,
            rel_path=note.rel_path,
            aliases=note.aliases,
            tags=note.tags,
            body=unit.text,
        )
        if score <= 0:
            continue
        candidate = LookupMatch(note=note, score=score, section=unit.section)
        if best is None:
            best = candidate
            continue
        candidate_key = (candidate.score, -lookup_section_priority(note.note_type or "", candidate.section), candidate.section)
        best_key = (best.score, -lookup_section_priority(note.note_type or "", best.section), best.section)
        if candidate_key > best_key:
            best = candidate
    return best


def build_related_matches(
    matched_paths: list[str],
    knowledge_matches: list[LookupMatch],
    edges: list[Edge],
    node_specs: dict[str, dict[str, Any]],
    limit: int,
) -> list[RelatedMatch]:
    incoming, outgoing = adjacency(edges)
    matched_set = set(matched_paths)
    conflict_kinds = {"conflict_ref", "contradicts"}
    related_scores: Counter[str] = Counter()
    related_kinds: defaultdict[str, set[str]] = defaultdict(set)
    forced_conflicts: set[str] = set()
    matched_claim_paths = {match.note.rel_path for match in knowledge_matches if match.note.note_type == "claim"}

    for path in matched_paths:
        for edge in outgoing.get(path, []):
            if edge.kind in conflict_kinds:
                if path in matched_claim_paths and edge.target not in matched_set:
                    forced_conflicts.add(edge.target)
                continue
            if edge.target not in matched_set:
                related_scores[edge.target] += edge_weight(edge.kind)
                related_kinds[edge.target].add(edge.kind)
        for edge in incoming.get(path, []):
            if edge.kind in conflict_kinds:
                if path in matched_claim_paths and edge.source not in matched_set:
                    forced_conflicts.add(edge.source)
                continue
            if edge.source not in matched_set:
                related_scores[edge.source] += edge_weight(edge.kind)
                related_kinds[edge.source].add(edge.kind)

    ordered = sorted(
        (
            RelatedMatch(path=path, score=score, kinds=tuple(sorted(related_kinds[path])))
            for path, score in related_scores.items()
            if node_specs.get(path, {}).get("type") not in {"raw", "source"}
        ),
        key=lambda item: (-item.score, item.path),
    )

    selected: list[RelatedMatch] = ordered[:limit]
    selected_paths = {item.path for item in selected}
    for path in sorted(forced_conflicts):
        if path in selected_paths:
            continue
        if node_specs.get(path, {}).get("type") in {"raw", "source"}:
            continue
        selected.append(
            RelatedMatch(
                path=path,
                score=sum(
                    edge_weight(edge.kind)
                    for edge in [*incoming.get(path, []), *outgoing.get(path, [])]
                    if edge.kind in conflict_kinds and (edge.source in matched_claim_paths or edge.target in matched_claim_paths)
                ),
                kinds=tuple(sorted(conflict_kinds & ({edge.kind for edge in incoming.get(path, [])} | {edge.kind for edge in outgoing.get(path, [])}))),
            )
        )
        selected_paths.add(path)
    return selected


def infer_route_clusters(notes: list[Note]) -> set[str]:
    clusters: set[str] = set()
    for note in notes:
        parts = Path(note.rel_path).parts
        if len(parts) >= 2 and parts[0] == "知识簇":
            clusters.add(parts[1])
    return clusters


def note_in_clusters(note: Note, clusters: set[str]) -> bool:
    parts = Path(note.rel_path).parts
    if len(parts) >= 2 and parts[0] == "知识簇":
        return parts[1] in clusters
    if note.note_type != "claim":
        return False
    related_refs: list[str] = []
    for field in RELATION_FIELDS:
        related_refs.extend(note.relations.get(field, []))
    related_refs.extend(note.claim_refs)
    related_refs.extend(note.summary_claim_refs)
    related_refs.extend(note.conflict_refs)
    for ref in related_refs:
        ref_parts = Path(ref).parts
        if len(ref_parts) >= 2 and ref_parts[0] == "知识簇" and ref_parts[1] in clusters:
            return True
    return False


def tokenize_query(value: str) -> list[str]:
    tokens = re.split(r"[\s/,_\-]+", value.lower())
    stopwords = {
        "a",
        "an",
        "and",
        "for",
        "from",
        "have",
        "in",
        "into",
        "is",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "with",
    }
    return [token for token in tokens if token and token not in stopwords]


def score_match(query: str, title: str, rel_path: str, aliases: list[str], tags: list[str], body: str) -> float:
    normalized_query = normalize_ref(query)
    query_tokens = tokenize_query(query)
    haystacks = [
        normalize_ref(title),
        normalize_ref(rel_path),
        *(normalize_ref(alias) for alias in aliases),
        *(normalize_ref(tag) for tag in tags),
    ]
    body_text = body.lower()
    score = 0.0
    if not normalized_query and not query_tokens:
        return score
    if normalized_query:
        if any(text == normalized_query for text in haystacks):
            score += 100
        elif any(normalized_query in text for text in haystacks):
            score += 45
        elif normalized_query in body_text:
            score += 15
    for token in query_tokens:
        if len(token) < 2:
            continue
        if any(text == token for text in haystacks):
            score += 20
        elif any(token in text for text in haystacks):
            score += 10
        elif token in body_text:
            score += 3
    return score


def edge_weight(kind: str) -> int:
    if kind in {"supports", "depends_on", "contradicts", "part_of"}:
        return 4
    if kind in {"summary_claim_ref", "conflict_ref"}:
        return 4
    if kind == "claim_ref":
        return 3
    if kind == "see_also":
        return 3
    if kind in {"wikilink", "source_ref"}:
        return 2
    return 1
