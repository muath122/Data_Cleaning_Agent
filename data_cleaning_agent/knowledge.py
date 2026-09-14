"""Deterministic canonical mappings loaded from the project's reviewed knowledge base."""

import json
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KNOWLEDGE_BASE = ROOT / "knowledge_base" / "knowledge_base_v0.3.json"
SECTIONS = {
    "University": ("universities",),
    "Major": ("majors",),
    "Committee": ("main_committees", "sub_committees"),
}


def normalized_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=4)
def load_knowledge(path: str | None = None) -> dict:
    selected = Path(path or os.getenv("DATA_CLEANING_KNOWLEDGE_BASE", DEFAULT_KNOWLEDGE_BASE))
    return json.loads(selected.read_text(encoding="utf-8"))


@lru_cache(maxsize=16)
def alias_map(category: str, path: str | None = None) -> dict[str, str]:
    mappings: dict[str, str] = {}
    collisions = set()
    data = load_knowledge(path)
    for section in SECTIONS.get(category, ()):
        for item in data.get(section, []):
            canonical = item.get("canonical_en") or item.get("canonical_ar")
            values = [canonical, item.get("canonical_en"), item.get("canonical_ar")]
            values.extend(item.get("aliases", []))
            for value in filter(None, values):
                key = normalized_key(value)
                if key in mappings and mappings[key] != canonical:
                    collisions.add(key)
                else:
                    mappings[key] = canonical
    for key in collisions:
        mappings.pop(key, None)
    return mappings


def canonical_value(value: str, category: str) -> str | None:
    """Return a reviewed canonical value, or None when the knowledge base is unsure."""
    return alias_map(category).get(normalized_key(value))
