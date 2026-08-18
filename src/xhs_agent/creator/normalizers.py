from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Iterable

from .comment_privacy import anonymize_comments


def parse_count(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return max(int(value), 0)
    text = str(value).strip().replace(",", "")
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10_000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100_000_000
        text = text[:-1]
    try:
        return max(int(float(text) * multiplier), 0)
    except ValueError:
        return 0


def _pick(mapping: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", []):
            return value
    return default


def unwrap_data(payload: Any) -> Any:
    current = payload
    for _ in range(5):
        if not isinstance(current, dict) or "data" not in current:
            break
        nested = current.get("data")
        if not isinstance(nested, (dict, list)):
            break
        current = nested
    return current


def _find_dict_with_any(value: Any, keys: set[str]) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if any(key in value for key in keys):
            return value
        for child in value.values():
            found = _find_dict_with_any(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_dict_with_any(child, keys)
            if found is not None:
                return found
    return None


def _find_list(value: Any, keys: Iterable[str]) -> list[Any]:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
        for child in value.values():
            found = _find_list(child, keys)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_list(child, keys)
            if found:
                return found
    return []


def _select_note(items: list[Any], note_id: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate = _pick(item, "noteCard", "note_card", default=item)
        if isinstance(candidate, dict):
            candidates.append(candidate)
    for candidate in candidates:
        candidate_id = str(_pick(candidate, "note_id", "noteId", "id", default=""))
        if candidate_id == note_id:
            return candidate
    return candidates[0] if len(candidates) == 1 else None


def _timestamp(value: Any) -> str | None:
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, str) and not value.isdigit():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
        except ValueError:
            return None
    try:
        numeric = float(value)
        if numeric > 10_000_000_000:
            numeric /= 1000
        return datetime.fromtimestamp(numeric, tz=UTC).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OSError):
        return None


def _interaction_map(value: Any) -> dict[str, int]:
    result = {"followers": 0, "following": 0, "received_interactions": 0}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            label = str(_pick(item, "type", "name", default="")).lower()
            count = parse_count(_pick(item, "count", "value", default=0))
            if "fan" in label or "粉丝" in label:
                result["followers"] = count
            elif "follow" in label or "关注" in label:
                result["following"] = count
            elif "interaction" in label or "获赞" in label or "收藏" in label:
                result["received_interactions"] = count
    return result


def normalize_profile(payload: dict[str, Any]) -> dict[str, Any]:
    inner = unwrap_data(payload)
    container = inner if isinstance(inner, dict) else {}
    user = _pick(container, "user", "basic_info", "basicInfo")
    if not isinstance(user, dict):
        user = _find_dict_with_any(
            container,
            {"user_id", "userid", "userId", "nickname", "red_id", "redId"},
        ) or {}
    account_id = str(_pick(user, "user_id", "userid", "userId", "id", default=""))
    nickname = str(_pick(user, "nickname", "nick_name", "name", default=""))
    if not account_id:
        raise ValueError("TikHub 用户信息响应缺少稳定 user_id")
    if not nickname:
        raise ValueError("TikHub 用户信息响应缺少 nickname")

    interactions = _interaction_map(_pick(container, "interactions", "interaction", default=[]))
    direct_counts = {
        "followers": _pick(user, "fans", "fans_count", "fansCount", "follower_count"),
        "following": _pick(user, "follows", "follow_count", "follows_count", "followsCount"),
        "received_interactions": _pick(user, "liked_and_collected", "interaction", "likedCount"),
    }
    for key, value in direct_counts.items():
        if value not in (None, ""):
            interactions[key] = parse_count(value)
    return {
        "account_id": account_id,
        "nickname": nickname,
        "red_id": str(_pick(user, "red_id", "redId", default="")),
        "description": str(_pick(user, "desc", "description", default="")),
        "followers": interactions["followers"],
        "following": interactions["following"],
        "received_interactions": interactions["received_interactions"],
    }


def _metrics(value: dict[str, Any]) -> dict[str, int]:
    interaction = _pick(value, "interact_info", "interactInfo", default={})
    if not isinstance(interaction, dict):
        interaction = {}
    return {
        "likes": parse_count(_pick(interaction, "liked_count", "likedCount", "likes", default=_pick(value, "liked_count", "likedCount", "likes", default=0))),
        "collects": parse_count(_pick(interaction, "collected_count", "collectedCount", "collects", default=_pick(value, "collected_count", "collectedCount", "collects", default=0))),
        "comments": parse_count(_pick(interaction, "comment_count", "commentCount", "comments_count", default=_pick(value, "comment_count", "commentCount", "comments_count", default=0))),
        "shares": parse_count(_pick(interaction, "share_count", "shareCount", "shared_count", default=_pick(value, "share_count", "shareCount", "shared_count", default=0))),
    }


def _tags(value: dict[str, Any], description: str = "") -> list[str]:
    raw = _pick(value, "tag_list", "tagList", "tags", "hash_tag", default=[])
    tags: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                label = item
            elif isinstance(item, dict):
                label = str(_pick(item, "name", "tag_name", "title", default=""))
            else:
                continue
            if label.strip():
                tags.append(label.strip().lstrip("#"))
    if not tags and description:
        tags.extend(
            tag.strip()
            for tag in re.findall(r"#([^#\[\]\s]+?)(?:\[.*?\])?#?(?=\s|#|$)", description)
            if tag.strip()
        )
    return list(dict.fromkeys(tags))


def normalize_notes_page(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], bool, str]:
    inner = unwrap_data(payload)
    container = inner if isinstance(inner, dict) else {}
    raw_notes = _find_list(container, ("notes", "items", "feeds", "note_list"))
    notes: list[dict[str, Any]] = []
    last_cursor = ""
    for raw in raw_notes:
        if not isinstance(raw, dict):
            continue
        card = _pick(raw, "note_card", "noteCard", default=raw)
        if not isinstance(card, dict):
            card = raw
        note_id = str(_pick(raw, "note_id", "noteId", "id", default=_pick(card, "note_id", "noteId", "id", default="")))
        if not note_id:
            continue
        cursor = str(_pick(raw, "cursor", default=""))
        if cursor:
            last_cursor = cursor
        notes.append({
            "note_id": note_id,
            "title": str(_pick(card, "display_title", "displayTitle", "title", default="")),
            "type": str(_pick(card, "type", default=_pick(raw, "type", default="normal"))),
            "xsec_token": str(_pick(raw, "xsec_token", "xsecToken", default="")),
            "metrics": _metrics(card | raw),
            "cursor": cursor,
        })
    has_more = bool(_pick(container, "has_more", "hasMore", default=False))
    next_cursor = str(_pick(container, "cursor", "lastCursor", default=last_cursor))
    return notes, has_more, next_cursor


def normalize_note_detail(payload: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    inner = unwrap_data(payload)
    container = inner if isinstance(inner, dict) else {}
    raw_note = _select_note(inner, summary["note_id"]) if isinstance(inner, list) else None
    for key in ("note", "noteData"):
        if isinstance(container.get(key), dict):
            raw_note = container[key]
            break
    if raw_note is None:
        note_list = _find_list(container, ("note_list",))
        raw_note = _select_note(note_list, summary["note_id"])
    if raw_note is None:
        items = _find_list(container, ("items",))
        raw_note = _select_note(items, summary["note_id"])
    if raw_note is None and any(key in container for key in ("note_id", "noteId", "desc", "title")):
        raw_note = container
    if raw_note is None:
        raise ValueError(f"笔记 {summary['note_id']} 的详情响应为空")

    description = str(_pick(raw_note, "desc", "description", "content", default=""))
    title = str(_pick(raw_note, "title", "display_title", "displayTitle", default=summary.get("title", "")))
    metrics = _metrics(raw_note)
    if not any(metrics.values()):
        metrics = summary.get("metrics", metrics)
    note = {
        "note_id": str(_pick(raw_note, "note_id", "noteId", "id", default=summary["note_id"])),
        "title": title,
        "desc": description,
        "type": str(_pick(raw_note, "type", default=summary.get("type", "normal"))),
        "published_at": _timestamp(_pick(raw_note, "time", "create_time", "createTime", "timestamp")),
        "metrics": metrics,
        "tags": _tags(raw_note, description),
        "comments": [],
    }
    missing = []
    if not title and not description:
        missing.append("content")
    if not any(metrics.values()):
        missing.append("metrics")
    if note["published_at"] is None:
        missing.append("published_at")
    note["quality"] = "failed" if "content" in missing else ("partial" if missing else "complete")
    note["missing"] = missing
    return note


def normalize_comments_page(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inner = unwrap_data(payload)
    container = inner if isinstance(inner, dict) else {}
    raw_comments = _find_list(container, ("comments", "comment_list", "list"))
    comments = anonymize_comments([item for item in raw_comments if isinstance(item, dict)])
    pagination = {
        "has_more": bool(_pick(container, "has_more", "hasMore", default=False)),
        "cursor": str(_pick(container, "cursor", default="")),
        "index": parse_count(_pick(container, "index", default=0)),
        "page_area": str(_pick(container, "pageArea", "page_area", default="UNFOLDED")),
    }
    return comments, pagination
