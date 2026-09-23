from __future__ import annotations

from pathlib import Path
from typing import Any
import re
from obsidian_graphify.config import current_vault
from obsidian_graphify.utils import as_string


def load_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    return parse_frontmatter(frontmatter), body


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return "", text
    frontmatter = parts[0][4:]
    body = parts[1]
    return frontmatter, body


def parse_frontmatter(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        list_match = re.match(r"^\s*-\s+(.*)$", line)
        if list_match and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(parse_scalar(list_match.group(1).strip()))
            continue
        key_match = re.match(r"^([A-Za-z0-9_-]+):(.*)$", line)
        if not key_match:
            current_key = None
            continue
        key, rest = key_match.group(1), key_match.group(2).strip()
        if not rest:
            data[key] = []
            current_key = key
            continue
        data[key] = parse_scalar(rest)
        current_key = None
    return data


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def extract_wikilinks(text: str) -> list[str]:
    links = []
    for match in re.findall(r"\[\[([^\]]+)\]\]", text):
        target = match.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            links.append(target)
    return links


def extract_section(body: str, heading: str) -> str:
    lines = body.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            in_section = stripped == f"## {heading}"
            continue
        if in_section:
            collected.append(line)
    return "\n".join(collected).strip()


def extract_top_level_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is not None:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append((current_heading, content))
            current_heading = stripped[3:].strip()
            current_lines = []
            continue
        if current_heading is not None:
            current_lines.append(line)
    if current_heading is not None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_heading, content))
    return sections


def extract_callout(body: str, title: str) -> str:
    lines = body.splitlines()
    collected: list[str] = []
    in_callout = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("> [!") and title in stripped:
            in_callout = True
            continue
        if in_callout:
            if stripped.startswith(">"):
                collected.append(stripped[1:].strip())
                continue
            if stripped:
                break
    return "\n".join(line for line in collected if line).strip()


def body_preview(body: str, limit: int = 1200) -> str:
    text = re.sub(r"^---\n.*?\n---\n", "", body, flags=re.DOTALL)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def infer_title(path: Path, frontmatter: dict[str, Any], body: str) -> str:
    for key in ("title", "statement", "core_focus", "core_question", "question"):
        value = as_string(frontmatter.get(key))
        if value:
            return value
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem


def infer_source_type(path: Path) -> str:
    try:
        relative = path.relative_to(current_vault().root)
    except ValueError:
        return "unknown"
    if not relative.parts:
        return "unknown"
    if relative.parts[0] == "raw":
        return "raw"
    if relative.parts[0] == "知识簇" and len(relative.parts) > 1:
        return relative.parts[1].rstrip("s")
    if len(relative.parts) >= 2 and relative.parts[0] == "_graphify":
        return relative.parts[1].rstrip("s")
    return relative.parts[0]


def infer_knowledge_kind(path: Path) -> str:
    try:
        relative = path.relative_to(current_vault().root)
    except ValueError:
        relative = path
    parts = relative.parts
    if not parts:
        return "unknown"
    if parts[0] == "知识簇":
        if path.name == "_索引.md":
            return "index"
        if "命题" in parts or "_claims" in parts:
            return "claim"
        return "wiki"
    if len(parts) >= 2 and parts[0] == "_graphify":
        if parts[1] == "sources":
            return "source"
        if parts[1] == "indexes":
            return "index"
    return "unknown"
