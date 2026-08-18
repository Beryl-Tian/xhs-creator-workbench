from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def new_id(prefix: str) -> str:
    """Return a non-guessable, schema-compatible object identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def next_object_version(directory: Path, field: str = "version") -> int:
    versions: list[int] = []
    for path in directory.glob("*.json"):
        value = read_json(path, {})
        if isinstance(value, dict):
            try:
                versions.append(int(value.get(field, 0)))
            except (TypeError, ValueError):
                continue
    return max(versions, default=0) + 1


def file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def next_baseline_version(creator_root: Path) -> int:
    versions = []
    for path in (creator_root / "baselines").glob("baseline_*_v*.json"):
        try:
            versions.append(int(path.stem.rsplit("_v", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(versions, default=0) + 1


def register_creator(state: Path, creator: dict[str, Any], *, updated_at: str) -> None:
    path = state / "registry.json"
    registry = read_json(path, {"schema_version": 1, "creators": []})
    previous = next(
        (item for item in registry.get("creators", []) if item.get("creator_id") == creator["creator_id"]),
        {},
    )
    creators = [
        item for item in registry.get("creators", [])
        if item.get("creator_id") != creator["creator_id"]
    ]
    creators.append({**previous,
        "creator_id": creator["creator_id"],
        "display_name": creator["display_name"],
        "updated_at": updated_at,
    })
    registry["creators"] = sorted(creators, key=lambda item: item["creator_id"])
    write_json_atomic(path, registry)


def update_registry_with_baseline(state: Path, creator: dict[str, Any], baseline: dict[str, Any]) -> None:
    register_creator(state, creator, updated_at=baseline["created_at"])
    path = state / "registry.json"
    registry = read_json(path, {"schema_version": 1, "creators": []})
    for item in registry["creators"]:
        if item.get("creator_id") == creator["creator_id"]:
            item["latest_candidate_baseline_id"] = baseline["baseline_id"]
            item["latest_candidate_baseline_version"] = baseline["version"]
            break
    write_json_atomic(path, registry)
