from __future__ import annotations

import json
from typing import Any

_EXACT = 2**53


def canonical_json(value: Any) -> bytes:
    return _encode(value).encode("utf-8")


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if not -_EXACT < value < _EXACT:
            raise ValueError(f"integer {value} is outside what canonical JSON represents exactly")
        return str(value)
    if isinstance(value, float):
        raise TypeError(f"canonical JSON carries no floating-point numbers: {value!r}")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list | tuple):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical JSON object keys must be strings")
        keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
        return "{" + ",".join(f"{_encode(key)}:{_encode(value[key])}" for key in keys) + "}"
    raise TypeError(f"canonical JSON cannot encode {type(value).__name__}")
