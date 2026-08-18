from xhs_agent.creator.comment_privacy import anonymize_comments


def test_comments_are_anonymized_before_storage() -> None:
    source = [{
        "user_id": "reader-private-id",
        "nickname": "private-name",
        "user_info": {"user_id": "nested-private-id", "nickname": "nested-name"},
        "avatar": "https://example.invalid/avatar.png",
        "id": "comment-private-id",
        "at_users": [{"userid": "mentioned-private-id", "nickname": "mentioned-name"}],
        "pictures": [{"url": "https://example.invalid/private-comment-media.png"}],
        "content": "这个方法怎么用？",
        "like_count": 3,
        "time": 1_700_000_000,
        "sub_comments": [{
            "user_id": "creator-private-id",
            "nickname": "creator-private-name",
            "show_tags_v2": [{"type": "is_author", "text": "Author"}],
            "content": "按正文第二步操作",
        }],
    }]
    cleaned = anonymize_comments(source)
    serialized = str(cleaned)
    assert cleaned[0]["speaker"] == "读者1"
    assert cleaned[0]["sub_comments"][0]["speaker"] == "作者"
    assert "reader-private-id" not in serialized
    assert "private-name" not in serialized
    assert "nested-private-id" not in serialized
    assert "comment-private-id" not in serialized
    assert "mentioned-private-id" not in serialized
    assert "private-comment-media" not in serialized
    assert "avatar" not in serialized
    assert set(cleaned[0]) == {"speaker", "is_author", "content", "like_count", "time", "sub_comments"}
    assert anonymize_comments(cleaned) == cleaned
