from __future__ import annotations

from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any
import json


def as_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [as_string(item) for item in value if as_string(item)]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [as_string(value)]


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (float, int)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return None


def is_stale(value: str) -> bool:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() <= date.today()
    except ValueError:
        return False


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
