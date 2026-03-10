# services/utils.py
from __future__ import annotations
import json
from typing import Any, Dict

def pretty_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

def parse_json(text: str) -> Dict[str, Any]:
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("Expected JSON object (dict).")
    return obj