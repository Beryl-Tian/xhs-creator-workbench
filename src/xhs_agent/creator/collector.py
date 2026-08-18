from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .normalizers import (
    normalize_comments_page,
    normalize_note_detail,
    normalize_notes_page,
    normalize_profile,
)


class CreatorSource(Protocol):
    def get_user_info(self, account: str) -> dict: ...

    def get_user_posted_notes(self, account: str, *, cursor: str = "") -> dict: ...

    def get_note_detail(self, note_id: str, *, note_type: str = "normal") -> dict: ...

    def get_note_comments(
        self,
        note_id: str,
        *,
        cursor: str = "",
        index: int = 0,
        page_area: str = "UNFOLDED",
        sort_strategy: str = "like_count",
    ) -> dict: ...


@dataclass(frozen=True)
class CollectionOptions:
    sample_size: int = 30
    comment_note_limit: int = 20
    comments_per_note: int = 20
    max_note_pages: int = 20
    max_comment_pages: int = 5

    def __post_init__(self) -> None:
        for name in (
            "sample_size",
            "comment_note_limit",
            "comments_per_note",
            "max_note_pages",
            "max_comment_pages",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.sample_size == 0:
            raise ValueError("sample_size must be positive")


@dataclass(frozen=True)
class CollectionResult:
    profile: dict[str, Any]
    notes: list[dict[str, Any]]
    quality: dict[str, Any]


def collect_creator(
    source: CreatorSource,
    account: str,
    options: CollectionOptions,
) -> CollectionResult:
    profile = normalize_profile(source.get_user_info(account))

    summaries: list[dict[str, Any]] = []
    seen_note_ids: set[str] = set()
    cursor = ""
    note_pages = 0
    while len(summaries) < options.sample_size and note_pages < options.max_note_pages:
        page, has_more, next_cursor = normalize_notes_page(
            source.get_user_posted_notes(account, cursor=cursor)
        )
        note_pages += 1
        for item in page:
            note_id = item["note_id"]
            if note_id not in seen_note_ids:
                seen_note_ids.add(note_id)
                summaries.append(item)
            if len(summaries) >= options.sample_size:
                break
        if not has_more or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    notes: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for summary in summaries[: options.sample_size]:
        try:
            detail = source.get_note_detail(
                summary["note_id"], note_type=summary.get("type", "normal")
            )
            notes.append(normalize_note_detail(detail, summary))
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            failures.append({"note_id": summary["note_id"], "reason": str(exc)})

    if not notes:
        raise RuntimeError("未获得任何可分析的笔记详情，无法建立 Baseline")

    ranked_notes = sorted(
        notes,
        key=lambda item: (
            item["metrics"].get("likes", 0),
            item["metrics"].get("collects", 0),
            item["metrics"].get("comments", 0),
        ),
        reverse=True,
    )[: options.comment_note_limit]
    collected_comments = 0
    comment_failures: list[dict[str, str]] = []
    for note in ranked_notes:
        cursor = ""
        index = 0
        page_area = "UNFOLDED"
        pages = 0
        while len(note["comments"]) < options.comments_per_note and pages < options.max_comment_pages:
            try:
                payload = source.get_note_comments(
                    note["note_id"], cursor=cursor, index=index, page_area=page_area
                )
                comments, pagination = normalize_comments_page(payload)
            except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                comment_failures.append({"note_id": note["note_id"], "reason": str(exc)})
                break
            remaining = options.comments_per_note - len(note["comments"])
            note["comments"].extend(comments[:remaining])
            pages += 1
            if not pagination["has_more"]:
                break
            next_cursor = pagination["cursor"]
            next_index = pagination["index"]
            if next_cursor == cursor and next_index == index:
                break
            cursor = next_cursor
            index = next_index
            page_area = pagination["page_area"]
        collected_comments += len(note["comments"])

    complete = sum(note["quality"] == "complete" for note in notes)
    partial = sum(note["quality"] == "partial" for note in notes)
    quality = {
        "requested_notes": options.sample_size,
        "listed_notes": len(summaries),
        "analyzed_notes": len(notes),
        "complete_notes": complete,
        "partial_notes": partial,
        "failed_note_details": failures,
        "commented_notes": sum(bool(note["comments"]) for note in notes),
        "collected_comments": collected_comments,
        "comment_failures": comment_failures,
        "coverage": round(len(notes) / options.sample_size, 4),
    }
    return CollectionResult(profile=profile, notes=notes, quality=quality)
