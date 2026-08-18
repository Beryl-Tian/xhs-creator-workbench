#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urldefrag


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas" / "v1"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def walk_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                yield item
            yield from walk_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_refs(item)


def main() -> int:
    errors: list[str] = []
    ids: set[str] = set()
    paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
    if not paths:
        errors.append("no schemas found")

    for path in paths:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        if schema.get("$schema") != DRAFT:
            errors.append(f"{path.name}: unexpected JSON Schema draft")
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            errors.append(f"{path.name}: missing $id")
        elif schema_id in ids:
            errors.append(f"{path.name}: duplicate $id {schema_id}")
        else:
            ids.add(schema_id)
        if not schema.get("title"):
            errors.append(f"{path.name}: missing title")
        if path.name != "common.schema.json":
            if schema.get("type") != "object":
                errors.append(f"{path.name}: top-level type must be object")
            if schema.get("additionalProperties") is not False:
                errors.append(f"{path.name}: top-level additionalProperties must be false")

        for reference in walk_refs(schema):
            target, _fragment = urldefrag(reference)
            if not target or "://" in target:
                continue
            if not (path.parent / target).exists():
                errors.append(f"{path.name}: missing local $ref target {target}")

    if errors:
        print("Schema validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Schema validation passed ({len(paths)} schemas).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
