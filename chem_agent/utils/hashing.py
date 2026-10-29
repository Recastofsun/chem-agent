"""Deterministic hashing of inputs/results (sha256 over canonical JSON)."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_of(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def deterministic_uuid(input_hash: str) -> str:
    """UUID derived from the input hash: same input -> same reaction_id."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "chem-agent:" + input_hash))
