from __future__ import annotations

from xhs_agent.creator.collector import CollectionOptions, collect_creator


class SyntheticSource:
    def get_user_info(self, account):
        return {"data": {"user": {"user_id": "synthetic-user", "nickname": "示例博主"}}}

    def get_user_posted_notes(self, account, *, cursor=""):
        page = 1 if not cursor else 2
        return {"data": {
            "notes": [{
                "note_id": f"note-{page}",
                "note_card": {"display_title": f"示例{page}", "interact_info": {"liked_count": str(page * 10)}},
            }],
            "has_more": page == 1,
            "cursor": "page-2" if page == 1 else "",
        }}

    def get_note_detail(self, note_id, *, note_type="normal"):
        number = int(note_id[-1])
        return {"data": {"note": {
            "note_id": note_id,
            "title": f"{number}个示例方法",
            "desc": "我的公开示例正文 #示例",
            "time": 1_700_000_000 + number,
            "interact_info": {"liked_count": number * 10, "comment_count": 2},
        }}}

    def get_note_comments(self, note_id, **kwargs):
        return {"data": {"comments": [{
            "user_id": f"private-{note_id}", "nickname": "不应保存", "content": "示例问题？"
        }], "has_more": False}}


def test_collection_pages_deduplicates_and_anonymizes() -> None:
    result = collect_creator(
        SyntheticSource(),
        "synthetic-user",
        CollectionOptions(sample_size=2, comment_note_limit=1, comments_per_note=1),
    )
    assert [note["note_id"] for note in result.notes] == ["note-1", "note-2"]
    assert result.quality["coverage"] == 1.0
    assert result.quality["collected_comments"] == 1
    serialized = str(result.notes)
    assert "private-note" not in serialized
    assert "不应保存" not in serialized
