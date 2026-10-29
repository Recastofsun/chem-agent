"""Configuration: optional YAML/JSON file or dict merged over defaults."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from .utils.encoding import read_text

DEFAULTS: dict = {"options": {}, "db_path": None}


def load_config(config: str | Path | dict | None) -> dict:
    if config is None:
        return {**DEFAULTS}
    if isinstance(config, dict):
        return {**DEFAULTS, **config}
    p = Path(config)
    if not p.exists():
        return {**DEFAULTS}
    text = read_text(p)
    data = json.loads(text) if p.suffix.lower() == ".json" else yaml.safe_load(text)
    return {**DEFAULTS, **(data or {})}
