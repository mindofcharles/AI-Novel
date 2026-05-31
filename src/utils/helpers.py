import re
from typing import Dict, Optional, Any

def get_nested(obj: Optional[Dict], path: str) -> Any:
    """Safely traverse nested dictionary by a dot-separated path."""
    if not isinstance(obj, dict):
        return None
    cur = obj
    parts = path.split(".")
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur

def set_nested(obj: Dict, path: str, value: Any) -> None:
    """Set a nested dictionary value by a dot-separated path, creating dictionaries if absent."""
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value

def normalize_text(text: str) -> str:
    """Normalize text by striping, converting to lower case, and merging multiple whitespaces."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def tokenize_text(text: str) -> set:
    """Normalize and tokenize text returning a set of tokens (handles English and CJK)."""
    normalized = normalize_text(text)
    tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", normalized)
    return set(tokens)
