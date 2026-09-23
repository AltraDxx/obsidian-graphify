from __future__ import annotations

from pathlib import Path
from typing import Any
import re


def candidate_keys(rel_path: str, title: str, aliases: list[str]) -> list[str]:
    path_no_ext = rel_path.rsplit(".", 1)[0] if "." in rel_path else rel_path
    stem = Path(rel_path).stem
    keys = {
        normalize_ref(stem),
        normalize_ref(path_no_ext),
        normalize_ref(path_no_ext.split("/", 1)[-1]),
        normalize_ref(title),
    }
    for alias in aliases:
        keys.add(normalize_ref(alias))
    return [key for key in keys if key]


def normalize_ref(value: str) -> str:
    normalized = value.strip().strip("/")
    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"\.md$", "", normalized, flags=re.IGNORECASE)
    return normalized.lower()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def resolve_reference(
    value: str, alias_map: dict[str, str | None], node_specs: dict[str, dict[str, Any]]
) -> str | None:
    if not value:
        return None
    clean = value.split("|", 1)[0].split("#", 1)[0].strip()
    if clean in node_specs:
        return clean
    if clean.endswith(".md") and clean[:-3] in node_specs:
        return clean[:-3]
    normalized = normalize_ref(clean)
    if normalized in alias_map:
        return alias_map[normalized]
    if clean.startswith("./"):
        maybe = clean[2:]
        if maybe in node_specs:
            return maybe
    return None
