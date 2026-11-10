"""A small JSON Schema subset validator (standard library only).

Supports: type, required, properties, additionalProperties (false), enum,
items, minLength, minimum, pattern and format (date, date-time).
That is all the bundled schemas use.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from . import store

_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _type_ok(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def _format_ok(value: str, fmt: str) -> bool:
    try:
        if fmt == "date":
            dt.date.fromisoformat(value)
        elif fmt == "date-time":
            store.parse_iso(value)
    except (ValueError, store.CosError):
        return False
    return True


def check(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    errors: List[str] = []
    wanted = schema.get("type")
    if wanted is not None:
        names = wanted if isinstance(wanted, list) else [wanted]
        if not any(_type_ok(value, name) for name in names):
            return ["%s: expected %s" % (path, " or ".join(names))]
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r is not one of %s" % (path, value, ", ".join(map(str, schema["enum"]))))
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            errors.append("%s: must not be empty" % path)
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append("%s: does not match %s" % (path, schema["pattern"]))
        if "format" in schema and not _format_ok(value, schema["format"]):
            errors.append("%s: not a valid %s" % (path, schema["format"]))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: must be at least %s" % (path, schema["minimum"]))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append("%s: missing required field %s" % (path, key))
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                errors.extend(check(item, props[key], "%s.%s" % (path, key)))
            elif schema.get("additionalProperties") is False:
                errors.append("%s: unexpected field %s" % (path, key))
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(check(item, schema["items"], "%s[%d]" % (path, index)))
    return errors


def load_schema(name: str) -> Dict[str, Any]:
    path = Path(store.root()) / "schemas" / ("%s.schema.json" % name)
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def require(value: Any, schema_name: str) -> None:
    errors = check(value, load_schema(schema_name))
    if errors:
        raise store.CosError(
            "Record failed %s validation: %s" % (schema_name, "; ".join(errors)),
            store.EXIT_VALIDATION,
            {"errors": errors},
        )
