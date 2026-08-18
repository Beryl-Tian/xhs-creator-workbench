from xhs_agent.creator.analyzer import analyze_creator


def test_analysis_is_conservative_and_evidence_addressable() -> None:
    notes = [
        {
            "note_id": "note-1", "title": "3步搞定？", "desc": "我的方法，欢迎评论",
            "type": "normal", "published_at": "2026-01-01T00:00:00Z",
            "metrics": {"likes": 100, "collects": 20, "comments": 3, "shares": 1},
            "tags": ["收纳"], "comments": [{"content": "怎么做？"}],
        },
        {
            "note_id": "note-2", "title": "品牌合作体验", "desc": "公开体验记录",
            "type": "video", "published_at": "2026-01-05T00:00:00Z",
            "metrics": {"likes": 20, "collects": 2, "comments": 1, "shares": 0},
            "tags": ["收纳"], "comments": [],
        },
    ]
    analysis = analyze_creator(notes, {"coverage": 1.0, "listed_notes": 2})
    assert analysis["confidence_band"] == "low"
    assert analysis["segments"]["commercial_candidates"]["note_ids"] == ["note-2"]
    assert analysis["cadence"]["median_gap_days"] == 4.0
    assert analysis["title_patterns"]["数字型"]["note_ids"] == ["note-1"]
    assert analysis["cta_patterns"]["评论引导"]["note_ids"] == ["note-1"]
    assert analysis["topic_candidates"][0]["topic"] == "收纳"
    assert analysis["title_statistics"]["maximum_characters"] >= 4
    assert analysis["distillation_gate"]["eligible"] is False
    assert "需人工确认" in analysis["limitations"][0]


def test_distillation_gate_requires_eighty_percent_detail_success() -> None:
    notes = [{
        "note_id": f"note-{number}", "title": f"方法{number}", "desc": "完整正文",
        "type": "normal", "published_at": f"2026-01-{number:02d}T00:00:00Z",
        "metrics": {"likes": number, "collects": 1, "comments": 0, "shares": 0},
        "tags": ["示例"], "comments": [],
    } for number in range(1, 13)]
    blocked = analyze_creator(notes, {"listed_notes": 16})
    ready = analyze_creator(notes, {"listed_notes": 15})
    assert blocked["distillation_gate"]["detail_success_rate"] == 0.75
    assert blocked["distillation_gate"]["eligible"] is False
    assert ready["distillation_gate"]["detail_success_rate"] == 0.8
    assert ready["distillation_gate"]["eligible"] is True


def test_human_confirmed_segments_have_robust_statistics() -> None:
    notes = [{
        "note_id": f"note-{number}", "title": f"内容{number}", "desc": "完整正文",
        "type": "normal", "published_at": f"2026-01-{number:02d}T00:00:00Z",
        "metrics": {"likes": number * 10, "collects": number, "comments": 1, "shares": 0},
        "tags": [], "comments": [],
    } for number in range(1, 13)]
    analysis = analyze_creator(
        notes,
        {"listed_notes": 12},
        commercial_note_ids={"note-11", "note-12"},
    )
    assert analysis["segments"]["commercial_detection"] == "human_confirmed"
    assert analysis["segments"]["commercial_candidates"]["count"] == 2
    assert analysis["segments"]["organic"]["metrics"]["likes"]["median"] == 55.0
    assert analysis["metrics"]["likes"]["trimmed_mean_10pct"] == 65
    assert analysis["metrics"]["likes"]["p25"] == 37.5
    assert "人工确认" in analysis["limitations"][0]


def test_longitudinal_analysis_separates_current_identity_from_historical_capability() -> None:
    notes = []
    for number in range(60):
        recent = number >= 30
        notes.append({
            "note_id": f"note-{number}",
            "title": f"{'合成运动样本' if recent else '合成护理样本'} {number}",
            "desc": "虚构运动训练测试文本" if recent else "虚构护肤测试文本",
            "type": "video",
            "published_at": f"{2024 if recent else 2023}-{(number % 12) + 1:02d}-{(number % 27) + 1:02d}T00:00:00Z",
            "metrics": {"likes": 100 + number, "collects": 20, "comments": 5, "shares": 1},
            "tags": ["运动" if recent else "护肤"],
            "comments": [],
        })
    longitudinal = analyze_creator(notes, {"listed_notes": 60})["longitudinal"]
    assert longitudinal["status"] == "ready"
    assert longitudinal["current"]["domains"]["运动生活"]["count"] == 30
    assert longitudinal["historical"]["domains"]["美妆护理"]["count"] == 30
    assert "运动生活" in longitudinal["transition"]["emerging_domains"]
    assert "美妆护理" in longitudinal["transition"]["declining_domains"]
    assert longitudinal["historical_capability_candidates"][0]["count"] == 30
