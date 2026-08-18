from __future__ import annotations

from typing import Any


SAFE_CONTENT_FIELDS = ("content", "like_count", "time")


def _is_author(comment: dict[str, Any]) -> bool:
    if comment.get("is_author") is True:
        return True
    tags = (
        comment.get("show_tags")
        or comment.get("showTags")
        or comment.get("show_tags_v2")
        or comment.get("showTagsV2")
        or ""
    )
    return "is_author" in str(tags)


def _user_id(comment: dict[str, Any]) -> str | None:
    for key in ("userid", "user_id", "userId"):
        if comment.get(key):
            return str(comment[key])
    for container_key in ("user", "userInfo", "user_info", "author"):
        container = comment.get(container_key)
        if isinstance(container, dict):
            for key in ("userid", "user_id", "userId", "id"):
                if container.get(key):
                    return str(container[key])
    return None


def anonymize_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reader_names: dict[str, str] = {}
    reader_number = 0

    def speaker_for(comment: dict[str, Any]) -> tuple[str, bool]:
        nonlocal reader_number
        author = _is_author(comment)
        if author:
            return "作者", True
        identity = _user_id(comment)
        if identity and identity in reader_names:
            return reader_names[identity], False
        reader_number += 1
        speaker = f"读者{reader_number}"
        if identity:
            reader_names[identity] = speaker
        return speaker, False

    def clean_one(comment: dict[str, Any]) -> dict[str, Any]:
        if comment.get("speaker"):
            clean = {key: comment[key] for key in SAFE_CONTENT_FIELDS if key in comment}
            clean["speaker"] = str(comment["speaker"])
            clean["is_author"] = bool(comment.get("is_author"))
            if isinstance(comment.get("reply_to"), str):
                clean["reply_to"] = comment["reply_to"]
            subcomments = comment.get("sub_comments") or comment.get("subComments") or []
            if isinstance(subcomments, list):
                clean["sub_comments"] = [
                    clean_one(item) for item in subcomments if isinstance(item, dict)
                ]
            return clean
        speaker, is_author = speaker_for(comment)
        clean: dict[str, Any] = {
            key: comment[key] for key in SAFE_CONTENT_FIELDS if key in comment
        }
        clean["speaker"] = speaker
        clean["is_author"] = is_author
        subcomments = comment.get("sub_comments") or comment.get("subComments") or []
        if isinstance(subcomments, list):
            clean["sub_comments"] = [clean_one(item) for item in subcomments if isinstance(item, dict)]
        target = comment.get("target_comment") or comment.get("targetComment")
        if isinstance(target, dict):
            clean["reply_to"] = speaker_for(target)[0]
        return clean

    return [clean_one(comment) for comment in comments if isinstance(comment, dict)]
