from xhs_agent.creator.normalizers import (
    normalize_comments_page,
    normalize_note_detail,
    normalize_notes_page,
    normalize_profile,
    parse_count,
)


def test_parse_chinese_counts() -> None:
    assert parse_count("1.2万") == 12_000
    assert parse_count("3,210") == 3_210
    assert parse_count(None) == 0


def test_normalize_synthetic_profile_and_notes() -> None:
    profile = normalize_profile({"code": 200, "data": {
        "user": {"user_id": "user-synthetic", "nickname": "示例博主", "fans": "1.2万"}
    }})
    assert profile["account_id"] == "user-synthetic"
    assert profile["followers"] == 12_000

    notes, has_more, cursor = normalize_notes_page({"data": {
        "notes": [{
            "note_id": "note-1",
            "note_card": {"display_title": "3步收纳", "type": "normal", "interact_info": {"liked_count": "88"}},
        }],
        "has_more": True,
        "cursor": "cursor-2",
    }})
    assert notes[0]["metrics"]["likes"] == 88
    assert has_more is True
    assert cursor == "cursor-2"


def test_normalize_detail_and_comments() -> None:
    summary = {"note_id": "note-1", "title": "摘要", "type": "normal", "metrics": {}}
    detail = normalize_note_detail({"data": {"note": {
        "note_id": "note-1",
        "title": "3步收纳",
        "desc": "我的整理方法 #收纳",
        "time": 1_700_000_000_000,
        "interact_info": {"liked_count": "100", "collected_count": "20"},
    }}}, summary)
    assert detail["quality"] == "complete"
    assert detail["tags"] == ["收纳"]

    comments, page = normalize_comments_page({"data": {
        "comments": [{"user_id": "private", "nickname": "匿名前", "content": "好用吗？"}],
        "has_more": False,
    }})
    assert comments[0]["speaker"] == "读者1"
    assert "user_id" not in comments[0]
    assert page["has_more"] is False


def test_normalize_detail_selects_requested_note_from_app_v2_list() -> None:
    summary = {"note_id": "target-note", "title": "摘要", "type": "video", "metrics": {}}
    payload = {"code": 200, "data": {"code": 0, "success": True, "data": [
        {"id": "related-note", "title": "相关推荐", "desc": "不是目标内容", "liked_count": 999},
        {
            "id": "target-note",
            "title": "目标标题",
            "desc": "目标正文 #真实样本",
            "time": 1_700_000_000,
            "liked_count": 120,
            "collected_count": 30,
            "comments_count": 8,
            "shared_count": 2,
        },
    ]}}

    detail = normalize_note_detail(payload, summary)

    assert detail["note_id"] == "target-note"
    assert detail["title"] == "目标标题"
    assert detail["metrics"] == {"likes": 120, "collects": 30, "comments": 8, "shares": 2}
