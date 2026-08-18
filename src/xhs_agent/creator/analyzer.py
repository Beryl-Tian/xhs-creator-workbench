from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from statistics import mean, median, quantiles
from typing import Any


COMMERCIAL_MARKERS = ("广告", "合作", "赞助", "品牌", "体验官", "推广", "报备")
TITLE_PATTERNS = {
    "数字型": r"\d+",
    "疑问型": r"[？?]|怎么|如何|为什么|什么",
    "感叹型": r"[！!]|绝了|太|真的|居然|竟然",
    "教程型": r"教程|手把手|保姆级|步骤|方法|攻略",
    "列表型": r"合集|盘点|推荐|必备|top|榜",
    "对比型": r"vs|对比|区别|差异|还是",
    "故事型": r"我|亲身|经历|踩坑|分享|心得",
    "悬念型": r"\.\.\.|…|竟然|没想到|万万|千万",
}
CTA_PATTERNS = {
    "关注引导": r"关注|点个关注|记得关注",
    "收藏引导": r"收藏|先收藏|码住|mark",
    "点赞引导": r"点赞|双击|给个赞",
    "评论引导": r"评论|留言|告诉我|你们觉得|欢迎讨论",
    "转发引导": r"转发|分享给",
    "私信引导": r"私信|私我|后台回复|滴滴",
}
OPENING_PATTERNS = {
    "故事开头": ("那天", "记得", "有一次", "上周", "上个月", "去年", "小时候"),
    "反问开头": ("你有没有", "你是不是", "为什么", "凭什么", "难道", "真的吗", "？"),
    "数据开头": ("%", "万", "个", "次", "元", "块", "倍", "调查", "数据"),
    "自嘲开头": ("我这个", "作为一个", "承认", "说实话", "坦白"),
    "观点直抛": ("我觉得", "我认为", "其实", "本质上", "说白了"),
}
ENDING_PATTERNS = {
    "金句收尾": ("就是", "才是", "而已", "罢了", "本质", "归根"),
    "行动号召": ("关注", "收藏", "点赞", "试试", "去做", "行动"),
    "开放提问": ("你呢", "你觉得", "评论区", "留言", "告诉我", "你们"),
    "总结回顾": ("总结", "所以", "因此", "最后", "希望"),
}
OPINION_PATTERNS = {
    "判断词": ("我觉得", "我认为", "其实", "本质上", "说白了", "归根结底", "核心是", "关键在于", "真正的", "最重要的"),
    "转折": ("但其实", "然而", "不是…而是", "不是...而是", "与其", "看起来", "实际上", "大家都说", "表面上"),
    "总结": ("所以", "因此", "这说明", "这意味着", "一句话概括", "总结一下", "换句话说"),
}
CONTENT_ARCHETYPES = {
    "教程/实操": r"教程|怎么|如何|方法|步骤|实操|手把手|保姆级|攻略",
    "测评/推荐": r"测评|推荐|安利|种草|合集|必备|宝藏",
    "经验/复盘": r"经验|心得|感悟|踩坑|总结|复盘|分享|干货",
    "作品/成果": r"做了一个|搞了一个|上线|成果|作品|完成了",
    "日常/Vlog": r"日常|vlog|一天|记录|打卡",
}
DOMAIN_PATTERNS = {
    "运动生活": r"网球|健身|运动|训练|跑步|夜跑|普拉提|瑜伽|滑雪|潜水|球场|徒步",
    "旅行户外": r"旅行|川西|三亚|重庆|普吉|马尔代夫|海岛|度假|露营|酒店|city\s*walk|自驾|雪山|海边",
    "美妆护理": r"妆|口红|唇釉|眼影|遮瑕|护肤|洗护|香水|首饰|保养|紧致|皮肤管理",
    "好物推荐": r"推荐|合集|爱用|好物|分享|试色|测评|种草|购物",
    "城市日常": r"成都|周末|日常|生活|咖啡|山姆|演唱会|看展|音乐节|小猫|做饭|手作",
}
EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]"
)


def _distribution(values: list[int]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0, "total": 0, "average": 0, "median": 0,
            "trimmed_mean_10pct": None, "p25": None, "p75": None,
            "minimum": 0, "maximum": 0,
        }
    ordered = sorted(values)
    trim_count = int(len(ordered) * 0.1)
    trimmed = ordered[trim_count:-trim_count] if trim_count else []
    quartiles = quantiles(ordered, n=4, method="inclusive") if len(ordered) >= 2 else [ordered[0]] * 3
    return {
        "count": len(ordered),
        "total": sum(ordered),
        "average": round(mean(ordered), 2),
        "median": median(ordered),
        "trimmed_mean_10pct": round(mean(trimmed), 2) if trimmed else None,
        "p25": quartiles[0],
        "p75": quartiles[2],
        "minimum": ordered[0],
        "maximum": ordered[-1],
    }


def _metric_summary(notes: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for metric in ("likes", "collects", "comments", "shares"):
        values = [int(note["metrics"].get(metric, 0)) for note in notes]
        output[metric] = _distribution(values)
    return output


def _cadence(notes: list[dict[str, Any]]) -> dict[str, Any]:
    parsed = []
    for note in notes:
        value = note.get("published_at")
        if value:
            try:
                parsed.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
            except ValueError:
                continue
    parsed.sort()
    gaps = [
        (right - left).total_seconds() / 86400
        for left, right in zip(parsed, parsed[1:])
        if 0 < (right - left).total_seconds() / 86400 < 365
    ]
    average_gap = round(mean(gaps), 2) if gaps else None
    return {
        "dated_notes": len(parsed),
        "average_gap_days": average_gap,
        "median_gap_days": round(float(median(gaps)), 2) if gaps else None,
        "oldest_published_at": parsed[0].isoformat().replace("+00:00", "Z") if parsed else None,
        "newest_published_at": parsed[-1].isoformat().replace("+00:00", "Z") if parsed else None,
    }


def _pattern_stats(notes: list[dict[str, Any]], patterns: dict[str, str], field: str) -> dict[str, Any]:
    results = {}
    for name, expression in patterns.items():
        def text_for(note: dict[str, Any]) -> str:
            if field == "combined":
                return f"{note.get('title', '')} {note.get('desc', '')}"
            return str(note.get(field, ""))

        matched = [note for note in notes if re.search(expression, text_for(note), re.IGNORECASE)]
        if matched:
            results[name] = {
                "count": len(matched),
                "rate": round(len(matched) / len(notes), 4),
                "note_ids": [note["note_id"] for note in matched[:5]],
                "examples": [text_for(note)[:120] for note in matched[:3]],
            }
    return results


def _edge_stats(notes: list[dict[str, Any]], patterns: dict[str, tuple[str, ...]], *, opening: bool) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    for name, markers in patterns.items():
        matched = []
        examples = []
        for note in notes:
            text = str(note.get("desc", ""))
            excerpt = text[:80] if opening else text[-80:]
            if any(marker in excerpt for marker in markers):
                matched.append(note["note_id"])
                examples.append(excerpt)
        if matched:
            results[name] = {
                "count": len(matched),
                "rate": round(len(matched) / len(notes), 4),
                "note_ids": matched[:5],
                "examples": examples[:3],
            }
    return results


def _content_structure(notes: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(str(note.get("desc", ""))) for note in notes if note.get("desc")]
    list_ids = [
        note["note_id"] for note in notes
        if re.search(r"^[\s]*[-•●]\s", str(note.get("desc", "")), re.MULTILINE)
    ]
    heading_ids = [
        note["note_id"] for note in notes
        if re.search(r"[①②③④⑤⑥⑦⑧⑨⑩]|[1-9][.、]", str(note.get("desc", "")))
    ]
    return {
        "average_characters": round(mean(lengths), 1) if lengths else 0,
        "median_characters": median(lengths) if lengths else 0,
        "length_buckets": {
            "short_under_200": sum(value < 200 for value in lengths),
            "medium_200_499": sum(200 <= value < 500 for value in lengths),
            "long_500_plus": sum(value >= 500 for value in lengths),
        },
        "list_usage": {"count": len(list_ids), "rate": round(len(list_ids) / len(notes), 4), "note_ids": list_ids[:5]},
        "heading_usage": {"count": len(heading_ids), "rate": round(len(heading_ids) / len(notes), 4), "note_ids": heading_ids[:5]},
    }


def _opinion_candidates(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for note in notes:
        for sentence in re.split(r"[。！？\n]", str(note.get("desc", ""))):
            sentence = sentence.strip()
            if len(sentence) < 8:
                continue
            for match_type, markers in OPINION_PATTERNS.items():
                if any(marker in sentence for marker in markers):
                    candidates.append({
                        "text": sentence[:240],
                        "note_id": note["note_id"],
                        "title": note.get("title", ""),
                        "likes": note["metrics"].get("likes", 0),
                        "match_type": match_type,
                    })
                    break
    return candidates


def _distinctive_terms(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stop = {"时候", "自己", "觉得", "一个", "一些", "一下", "一样", "可以", "没有", "什么", "这个", "那个", "这样", "因为", "所以", "但是", "然后", "真的", "感觉", "现在", "内容", "大家", "我们", "你们"}
    counts: Counter[str] = Counter()
    sources: dict[str, set[str]] = {}
    for note in notes:
        text = re.sub(r"#[^#\s]+?(?:\[.*?\])?#?", "", str(note.get("desc", "")))
        for token in re.split(r"[\s，。！？、；：‘’“”【】《》（）\[\]…—/|]+", text):
            token = token.strip()
            if 2 <= len(token) <= 6 and re.fullmatch(r"[\u4e00-\u9fff]+", token) and token not in stop:
                counts[token] += 1
                sources.setdefault(token, set()).add(note["note_id"])
    return [
        {"term": term, "count": count, "note_ids": sorted(sources[term])[:5]}
        for term, count in counts.most_common(20)
    ]


def _emoji_stats(notes: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    note_ids = []
    for note in notes:
        found = EMOJI_RE.findall(str(note.get("desc", "")))
        if found:
            note_ids.append(note["note_id"])
            counter.update(found)
    return {
        "notes_with_emoji": len(note_ids),
        "usage_rate": round(len(note_ids) / len(notes), 4),
        "top_emojis": [{"emoji": emoji, "count": count} for emoji, count in counter.most_common(10)],
        "note_ids": note_ids[:5],
    }


def _segment_summary(notes: list[dict[str, Any]]) -> dict[str, Any]:
    if not notes:
        return {"count": 0, "average_likes": None, "average_collects": None, "metrics": _metric_summary([]), "note_ids": []}
    return {
        "count": len(notes),
        "average_likes": round(mean(note["metrics"].get("likes", 0) for note in notes), 2),
        "average_collects": round(mean(note["metrics"].get("collects", 0) for note in notes), 2),
        "metrics": _metric_summary(notes),
        "note_ids": [note["note_id"] for note in notes],
    }


def _topic_candidates(notes: list[dict[str, Any]], tags: Counter[str]) -> list[dict[str, Any]]:
    results = []
    for tag, count in tags.most_common(12):
        matched = [note for note in notes if tag in note.get("tags", [])]
        results.append({
            "topic": tag,
            "count": count,
            "share": round(count / len(notes), 4),
            "average_likes": round(mean(note["metrics"].get("likes", 0) for note in matched), 2),
            "average_collects": round(mean(note["metrics"].get("collects", 0) for note in matched), 2),
            "note_ids": [note["note_id"] for note in matched[:8]],
        })
    return results


def _development_trend(notes: list[dict[str, Any]]) -> dict[str, Any] | None:
    dated = [note for note in notes if note.get("published_at")]
    if len(dated) < 6:
        return None
    dated.sort(key=lambda note: note["published_at"])
    midpoint = len(dated) // 2

    def period(items: list[dict[str, Any]]) -> dict[str, Any]:
        period_tags = Counter(tag for note in items for tag in note.get("tags", []))
        return {
            "count": len(items),
            "average_likes": round(mean(note["metrics"].get("likes", 0) for note in items), 2),
            "top_tags": [tag for tag, _count in period_tags.most_common(5)],
            "content_types": dict(Counter(str(note.get("type", "unknown")) for note in items)),
            "note_ids": [note["note_id"] for note in items],
        }

    return {"early": period(dated[:midpoint]), "recent": period(dated[midpoint:])}


def _time_window_summary(notes: list[dict[str, Any]]) -> dict[str, Any]:
    domain_stats = {}
    for domain, expression in DOMAIN_PATTERNS.items():
        matched = [
            note for note in notes
            if re.search(expression, f"{note.get('title', '')} {note.get('desc', '')}", re.IGNORECASE)
        ]
        domain_stats[domain] = {
            "count": len(matched),
            "share": round(len(matched) / len(notes), 4) if notes else 0,
            "note_ids": [note["note_id"] for note in matched[:8]],
        }
    tags = Counter(tag for note in notes for tag in note.get("tags", []))
    dates = sorted(note["published_at"] for note in notes if note.get("published_at"))
    return {
        "count": len(notes),
        "oldest_published_at": dates[0] if dates else None,
        "newest_published_at": dates[-1] if dates else None,
        "metrics": _metric_summary(notes),
        "domains": domain_stats,
        "top_tags": [{"tag": tag, "count": count} for tag, count in tags.most_common(10)],
        "note_ids": [note["note_id"] for note in notes],
    }


def _longitudinal_analysis(notes: list[dict[str, Any]], window_size: int = 30) -> dict[str, Any]:
    dated = sorted(
        (note for note in notes if note.get("published_at")),
        key=lambda note: note["published_at"],
        reverse=True,
    )
    current = dated[:window_size]
    prior = dated[window_size:window_size * 2]
    historical = dated[window_size:]
    current_summary = _time_window_summary(current)
    prior_summary = _time_window_summary(prior)
    historical_summary = _time_window_summary(historical)
    shifts = []
    for domain in DOMAIN_PATTERNS:
        current_item = current_summary["domains"][domain]
        prior_item = prior_summary["domains"][domain]
        delta = round(current_item["share"] - prior_item["share"], 4)
        direction = "stable"
        if delta >= 0.15 and current_item["count"] >= 3:
            direction = "emerging"
        elif delta <= -0.15 and prior_item["count"] >= 3:
            direction = "declining"
        shifts.append({
            "domain": domain,
            "current_count": current_item["count"],
            "current_share": current_item["share"],
            "prior_count": prior_item["count"],
            "prior_share": prior_item["share"],
            "share_delta": delta,
            "direction": direction,
        })
    capabilities = [
        {
            "domain": domain,
            "count": item["count"],
            "share": item["share"],
            "note_ids": item["note_ids"],
        }
        for domain, item in historical_summary["domains"].items()
        if item["count"] >= 3 and item["share"] >= 0.1
    ]
    capabilities.sort(key=lambda item: (item["count"], item["share"]), reverse=True)
    ready = len(current) >= 20 and len(prior) >= 10
    return {
        "status": "ready" if ready else "insufficient_history",
        "method": "chronological_profile_posts_only",
        "window_size": window_size,
        "dated_note_count": len(dated),
        "undated_note_count": len(notes) - len(dated),
        "current": current_summary,
        "historical": historical_summary,
        "prior_comparison_window": prior_summary,
        "transition": {
            "shifts": shifts,
            "emerging_domains": [item["domain"] for item in shifts if item["direction"] == "emerging"],
            "declining_domains": [item["domain"] for item in shifts if item["direction"] == "declining"],
        },
        "historical_capability_candidates": capabilities,
        "limitations": [
            "时间层只使用主页按时间采集并成功解析发布日期的笔记，不使用关键词搜索结果补样本。",
            "历史能力表示曾经稳定创作过，不自动等于当前主定位或未来应恢复的方向。",
            "时间画像描述全部公开内容组合，可能同时包含自然与商业内容，不替代自然内容定义的本人基线。",
            "领域采用多标签文本规则，同一篇内容可以同时属于多个领域，因此占比之和可能超过100%。",
        ],
    }


def analyze_creator(
    notes: list[dict[str, Any]],
    quality: dict[str, Any],
    *,
    commercial_note_ids: set[str] | None = None,
) -> dict[str, Any]:
    if not notes:
        raise ValueError("notes cannot be empty")
    metrics = _metric_summary(notes)
    tags = Counter(tag for note in notes for tag in note.get("tags", []))
    types = Counter(str(note.get("type", "unknown")) for note in notes)
    known_ids = {note["note_id"] for note in notes}
    if commercial_note_ids is None:
        commercial = [
            note for note in notes
            if any(marker in f"{note.get('title', '')} {note.get('desc', '')}" for marker in COMMERCIAL_MARKERS)
        ]
        commercial_ids = {note["note_id"] for note in commercial}
        commercial_detection = "public_text_markers_only_requires_human_confirmation"
        commercial_limitation = "商业内容仅由公开文本标记识别，需人工确认。"
    else:
        unknown_ids = set(commercial_note_ids) - known_ids
        if unknown_ids:
            raise ValueError(f"商业标签包含不在样本内的笔记：{sorted(unknown_ids)[0]}")
        commercial_ids = set(commercial_note_ids)
        commercial = [note for note in notes if note["note_id"] in commercial_ids]
        commercial_detection = "human_confirmed"
        commercial_limitation = "商业内容属性由人工确认；未标为商业的样本按自然内容分析。"
    organic = [note for note in notes if note["note_id"] not in commercial_ids]
    ranked = sorted(
        notes,
        key=lambda note: (note["metrics"].get("likes", 0), note["metrics"].get("collects", 0), note["metrics"].get("comments", 0)),
        reverse=True,
    )
    median_likes = float(metrics["likes"]["median"] or 0)
    relative_outliers = [
        note["note_id"] for note in notes
        if median_likes > 0 and note["metrics"].get("likes", 0) >= median_likes * 3
    ]
    total_likes = metrics["likes"]["total"]
    total_collects = metrics["collects"]["total"]
    content_notes = sum(bool(note.get("title") or note.get("desc")) for note in notes)
    detail_denominator = max(int(quality.get("listed_notes", len(notes))), 1)
    detail_success_rate = round(len(notes) / detail_denominator, 4)
    content_completeness = round(content_notes / len(notes), 4)
    eligible = detail_success_rate >= 0.8 and content_completeness >= 0.8 and len(notes) >= 10
    warnings = []
    if len(notes) < 10:
        warnings.append("有效笔记少于10篇，只能生成探索性画像。")
    if detail_success_rate < 0.8:
        warnings.append("详情获取成功率低于80%。")
    if content_completeness < 0.8:
        warnings.append("正文或标题完整率低于80%。")

    sample_count = len(notes)
    title_lengths = [len(str(note.get("title", ""))) for note in notes if note.get("title")]
    confidence = "high" if sample_count >= 50 else "medium" if sample_count >= 20 else "low"
    return {
        "sample_count": sample_count,
        "quality": quality,
        "distillation_gate": {
            "eligible": eligible,
            "minimum_note_count": 10,
            "detail_success_rate": detail_success_rate,
            "content_completeness": content_completeness,
            "warnings": warnings,
        },
        "confidence_band": confidence,
        "metrics": metrics,
        "performance": {
            "collect_like_ratio": round(total_collects / total_likes, 4) if total_likes else None,
            "relative_outlier_note_ids": relative_outliers,
            "relative_outlier_rate": round(len(relative_outliers) / sample_count, 4),
        },
        "content_types": dict(types),
        "cadence": _cadence(notes),
        "top_tags": [{"tag": tag, "count": count} for tag, count in tags.most_common(20)],
        "topic_candidates": _topic_candidates(notes, tags),
        "content_archetypes": _pattern_stats(notes, CONTENT_ARCHETYPES, "combined"),
        "development_trend": _development_trend(notes),
        "longitudinal": _longitudinal_analysis(notes),
        "top_notes": [
            {
                "note_id": note["note_id"],
                "title": note.get("title", ""),
                "metrics": note["metrics"],
                "like_vs_median": round(note["metrics"].get("likes", 0) / median_likes, 2) if median_likes else None,
            }
            for note in ranked[:10]
        ],
        "segments": {
            "organic": _segment_summary(organic),
            "commercial_candidates": _segment_summary(commercial),
            "commercial_detection": commercial_detection,
        },
        "title_patterns": _pattern_stats(notes, TITLE_PATTERNS, "title"),
        "title_statistics": {
            "average_characters": round(mean(title_lengths), 1) if title_lengths else 0,
            "median_characters": median(title_lengths) if title_lengths else 0,
            "minimum_characters": min(title_lengths, default=0),
            "maximum_characters": max(title_lengths, default=0),
        },
        "opening_patterns": _edge_stats(notes, OPENING_PATTERNS, opening=True),
        "ending_patterns": _edge_stats(notes, ENDING_PATTERNS, opening=False),
        "cta_patterns": _pattern_stats(notes, CTA_PATTERNS, "desc"),
        "content_structure": _content_structure(notes),
        "emoji_text_layout": _emoji_stats(notes),
        "opinion_candidates": _opinion_candidates(notes),
        "distinctive_term_candidates": _distinctive_terms(notes),
        "audience_signals": {
            "question_comment_count": sum(
                bool(re.search(r"[？?]|怎么|如何|为什么|吗", str(comment.get("content", ""))))
                for note in notes for comment in note.get("comments", [])
            ),
            "sampled_comment_count": sum(len(note.get("comments", [])) for note in notes),
        },
        "limitations": [
            commercial_limitation,
            "当前版本不分析图片构图、镜头语言或视频口播转写。",
            "互动量受发布时间和平台分发影响，不能直接解释因果。",
            "高频短语和观点句只是 AI 蒸馏原材料，不自动等于博主信念。",
        ],
    }
