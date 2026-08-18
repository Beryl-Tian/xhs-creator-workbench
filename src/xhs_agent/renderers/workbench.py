from __future__ import annotations

import html
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from ..creator.baseline import utc_now
from ..storage import read_json, write_json_atomic


SECTION_LABELS = {
    "positioning": "定位",
    "audience": "受众",
    "cognition": "认知层",
    "strategy": "策略层",
    "organic": "自然内容基因",
    "commercial": "商业内容基因",
    "voice": "语言与互动",
    "visual": "视觉与缺失",
    "guardrail": "创作护栏",
}
SECTION_ORDER = tuple(SECTION_LABELS)
SUMMARY_LABELS = {
    "one_line_positioning": "一句话定位",
    "audience": "核心受众",
    "content_identity": "自然内容身份",
    "commercial_identity": "商业内容身份",
}
FINDING_LABELS = {
    "positioning": "账号定位",
    "audience_need": "受众需求",
    "content_pillar": "内容支柱",
    "core_belief": "核心信念",
    "viewpoint_tension": "观点张力",
    "mental_model": "思维框架",
    "value_stance": "价值立场",
    "content_series": "内容系列",
    "topical_strategy": "热点策略",
    "operating_hypothesis": "运营假设",
    "title_formula": "标题公式",
    "opening_pattern": "开头模式",
    "body_structure": "正文结构",
    "emotional_arc": "情感节奏",
    "language_dna": "语言 DNA",
    "cta_pattern": "CTA",
    "tag_strategy": "标签策略",
    "publishing_cadence": "发布节奏",
    "commercial_integration": "商业植入",
    "commercial_difference": "自然/商业差异",
    "must_keep": "必须保留",
    "avoid": "避免出戏",
    "unknown_visual": "视觉缺失",
}
STATUS_LABELS = {
    "pending_confirmation": "待确认",
    "confirmed": "已确认",
    "rejected": "已拒绝",
    "superseded": "已取代",
}
HUMAN_CONTEXT_LABELS = {
    "desired_positioning": "团队目标定位",
    "target_audience": "希望吸引的人群",
    "commercial_guardrail": "商业例外护栏",
}
EPISTEMIC_STATUS_LABELS = {
    "observed": "直接观察",
    "inferred": "分析推断",
    "human_confirmed": "人工确认",
}


@dataclass(frozen=True)
class BuildResult:
    output: Path
    index_path: Path
    creator_count: int
    baseline_count: int
    project_count: int
    page_count: int
    warnings: list[str]


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _date(value: Any) -> str:
    if not value:
        return "未知"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%Y.%m.%d")
    except ValueError:
        return str(value)


def _number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number >= 100_000_000:
        return f"{number / 100_000_000:.1f}亿"
    if number >= 10_000:
        return f"{number / 10_000:.1f}万"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def _page(*, title: str, asset_prefix: str, body: str, home_href: str) -> str:
    accessible_body = body.replace("<main", '<main id="main-content"', 1)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{_e(title)} · 小红书创作工作台</title>
  <link rel="stylesheet" href="{_e(asset_prefix)}/workbench.css">
</head>
<body>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <header class="topbar">
    <div class="shell topbar-inner">
      <a class="brand" href="{_e(home_href)}"><strong>小红书创作工作台</strong><span>Local / Private / Read-only</span></a>
      <div class="top-actions">
        <a class="button" href="{_e(home_href)}">返回首页</a>
        <button class="button" type="button" data-action="print">打印 / 保存 PDF</button>
      </div>
    </div>
  </header>
  {accessible_body}
  <script src="{_e(asset_prefix)}/workbench.js"></script>
</body>
</html>
"""


def _evidence_card(item: dict[str, Any]) -> str:
    metrics = item.get("metrics") or {}
    metric_text = " · ".join(
        f"{label} {_number(metrics.get(key))}"
        for key, label in (("likes", "赞"), ("collects", "藏"), ("comments", "评"), ("shares", "转"))
        if key in metrics
    )
    return f"""
<article class="evidence">
  <div class="evidence-id">{_e(item.get('kind', 'evidence'))} / {_e(item.get('evidence_id'))}</div>
  <p class="evidence-copy">{_e(item.get('content_excerpt') or '该证据没有文本摘录。')}</p>
  <div class="evidence-metrics">{_e(metric_text or ('采集于 ' + _date(item.get('captured_at'))))}</div>
</article>"""


def _evidence_details(
    refs: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    label: str = "查看支持证据",
) -> str:
    items = [evidence_by_id.get(str(ref.get("evidence_id"))) for ref in refs]
    items = [item for item in items if item]
    if not items:
        return ""
    cards = "".join(_evidence_card(item) for item in items)
    return f"<details><summary>{_e(label)}（{len(items)}）</summary><div class=\"evidence-list\">{cards}</div></details>"


def _summary_grid(baseline: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    cards = []
    for key, label in SUMMARY_LABELS.items():
        item = baseline.get("summary", {}).get(key, {})
        refs = item.get("evidence_refs", []) if isinstance(item, dict) else []
        limitations = item.get("limitations", []) if isinstance(item, dict) else []
        foot = f"{len(refs)} 条证据"
        if limitations:
            foot += " · " + "；".join(str(value) for value in limitations)
        cards.append(f"""
<article class="summary-card">
  <div class="summary-label">{_e(label)}</div>
  <p class="summary-statement">{_e(item.get('statement', '待补充') if isinstance(item, dict) else item)}</p>
  <div class="summary-foot">{_e(foot)}</div>
  {_evidence_details(refs, evidence_by_id)}
</article>""")
    return f"<div class=\"summary-grid\">{''.join(cards)}</div>"


def _claim_card(claim: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    status = claim.get("epistemic_status", "inferred")
    limitations = claim.get("limitations") or []
    applicable = claim.get("applicable_to") or []
    search = " ".join([
        str(claim.get("statement", "")),
        str(claim.get("finding_type", "")),
        str(claim.get("category", "")),
        *[str(value) for value in applicable],
    ])
    meta_parts = []
    if applicable:
        meta_parts.append("适用于：" + " / ".join(applicable))
    if limitations:
        meta_parts.append("限制：" + "；".join(str(value) for value in limitations))
    support = _evidence_details(claim.get("evidence_refs", []), evidence_by_id)
    counter = _evidence_details(
        claim.get("counter_evidence_refs", []), evidence_by_id, label="查看反证"
    )
    return f"""
<article class="claim" data-claim data-search="{_e(search)}">
  <div class="claim-head">
    <div class="claim-type">{_e(FINDING_LABELS.get(claim.get('finding_type'), claim.get('finding_type', '结论')))} · {_e(EPISTEMIC_STATUS_LABELS.get(status, status))}</div>
    <div class="confidence">置信度 {_e(round(float(claim.get('confidence', 0)) * 100))}%</div>
  </div>
  <p class="claim-statement">{_e(claim.get('statement'))}</p>
  <div class="claim-meta">{_e(' · '.join(meta_parts) or '当前未标注额外限制')}</div>
  {support}{counter}
</article>"""


def _claim_sections(baseline: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    claims_by_id = {claim["claim_id"]: claim for claim in baseline.get("claims", [])}
    groups = []
    for category in SECTION_ORDER:
        ids = baseline.get("sections", {}).get(category, [])
        claims = [claims_by_id[claim_id] for claim_id in ids if claim_id in claims_by_id]
        if not claims:
            continue
        groups.append(f"""
<section class="claim-group" data-claim-group>
  <div class="claim-group-heading"><h3>{_e(SECTION_LABELS[category])}</h3><span class="claim-count">{len(claims)} 条结论</span></div>
  <div class="claim-list">{''.join(_claim_card(claim, evidence_by_id) for claim in claims)}</div>
</section>""")
    return "".join(groups) or '<div class="empty">当前 Baseline 没有可展示的 Claims。</div>'


def _comparison(baseline: dict[str, Any]) -> str:
    claims_by_id = {claim["claim_id"]: claim for claim in baseline.get("claims", [])}

    def statements(category: str) -> list[str]:
        return [
            str(claims_by_id[claim_id].get("statement"))
            for claim_id in baseline.get("sections", {}).get(category, [])
            if claim_id in claims_by_id
        ]

    organic = statements("organic")
    commercial = statements("commercial")

    def items(values: list[str], empty: str) -> str:
        if not values:
            return f"<li>{_e(empty)}</li>"
        return "".join(f"<li>{_e(value)}</li>" for value in values)

    return f"""
<div class="two-column">
  <article class="panel"><h3>自然内容基因</h3><ul>{items(organic, '尚无足够证据形成稳定自然内容规律。')}</ul></article>
  <article class="panel commercial"><h3>商业内容基因</h3><ul>{items(commercial, '商业笔记属性或样本仍待确认。')}</ul></article>
</div>"""


def _notice_grid(title: str, values: list[str]) -> str:
    if not values:
        return '<div class="notice"><strong>暂无</strong>当前没有记录。</div>'
    return "".join(
        f'<article class="notice"><strong>{_e(title)} {index:02d}</strong>{_e(value)}</article>'
        for index, value in enumerate(values, start=1)
    )


def _human_context(baseline: dict[str, Any]) -> str:
    items = baseline.get("human_context", [])
    if not items:
        return ""
    cards = "".join(f"""
<article class="summary-card">
  <div class="summary-label">{_e(HUMAN_CONTEXT_LABELS.get(item.get('context_type'), item.get('context_type')))}</div>
  <p class="summary-statement">{_e(item.get('statement'))}</p>
  <div class="summary-foot">团队人工确认 · 用于后续选题、商业路线与大纲</div>
</article>""" for item in items)
    return f"""
<section class="section" id="intent">
  <p class="eyebrow">Human Calibration</p>
  <h2>团队目标校准</h2>
  <p class="section-intro">这是博主团队明确希望塑造的方向，不等同于公开数据已经证明的现有受众。下游创作应同时满足该目标，并接受 Evidence 画像的真实性约束。</p>
  <div class="summary-grid">{cards}</div>
</section>"""


def _data_snapshot(analysis: dict[str, Any]) -> str:
    metrics = analysis.get("metrics", {})
    gate = analysis.get("distillation_gate", {})
    segments = analysis.get("segments", {})
    organic_count = segments.get("organic", {}).get("count", 0)
    commercial_count = segments.get("commercial_candidates", {}).get("count", 0)
    detection = segments.get("commercial_detection")
    commercial_note = "商业属性已人工确认" if detection == "human_confirmed" else "商业属性仍需人工确认"
    metric_rows = []
    metric_labels = {"likes": "点赞", "collects": "收藏", "comments": "评论", "shares": "分享"}
    for key, label in metric_labels.items():
        item = metrics.get(key, {})
        metric_rows.append(f"""
<tr><td>{_e(label)}</td><td class="numeric">{_e(_number(item.get('median')))}</td><td class="numeric">{_e(_number(item.get('trimmed_mean_10pct')))}</td><td class="numeric">{_e(_number(item.get('p25')))}–{_e(_number(item.get('p75')))}</td><td class="numeric">{_e(_number(item.get('average')))}</td><td class="numeric">{_e(_number(item.get('maximum')))}</td></tr>""")
    segment_rows = []
    for segment_key, segment_label in (("organic", "自然内容"), ("commercial_candidates", "商业内容")):
        segment = segments.get(segment_key, {})
        for metric_key, metric_label in metric_labels.items():
            item = segment.get("metrics", {}).get(metric_key, {})
            segment_rows.append(f"""
<tr><td>{_e(segment_label)}</td><td>{_e(metric_label)}</td><td class="numeric">{_e(segment.get('count', 0))}</td><td class="numeric">{_e(_number(item.get('median')))}</td><td class="numeric">{_e(_number(item.get('trimmed_mean_10pct')))}</td><td class="numeric">{_e(_number(item.get('p25')))}–{_e(_number(item.get('p75')))}</td></tr>""")
    tags = analysis.get("top_tags", [])[:12]
    tag_html = "".join(
        f'<span class="tag-item">#{_e(item.get("tag"))} · {_e(item.get("count"))}</span>'
        for item in tags
    ) or '<span class="tag-item">没有提取到公开标签</span>'
    patterns = analysis.get("title_patterns", {})
    pattern_html = "".join(
        f'<span class="tag-item">{_e(name)} · {_e(round(float(item.get("rate", 0)) * 100))}%</span>'
        for name, item in sorted(patterns.items(), key=lambda pair: pair[1].get("count", 0), reverse=True)
    ) or '<span class="tag-item">标题模式样本不足</span>'
    top_rows = []
    for position, note in enumerate(analysis.get("top_notes", []), start=1):
        item = note.get("metrics", {})
        relative = note.get("like_vs_median")
        top_rows.append(f"""
<tr><td class="numeric">{position:02d}</td><td>{_e(note.get('title') or '无标题')}</td><td class="numeric">{_e(_number(item.get('likes')))}</td><td class="numeric">{_e(_number(item.get('collects')))}</td><td class="numeric">{_e(str(relative) + '×' if relative is not None else '—')}</td></tr>""")
    warning_text = "；".join(str(value) for value in gate.get("warnings", [])) or "质量闸门已通过"
    return f"""
<div class="data-grid">
  <article class="data-card"><span class="data-card-label">有效样本</span><span class="data-card-value">{_e(analysis.get('sample_count', 0))} 篇</span><span class="data-card-note">内容完整率 {_e(round(float(gate.get('content_completeness', 0)) * 100))}%</span></article>
  <article class="data-card"><span class="data-card-label">自然 / 商业</span><span class="data-card-value">{_e(organic_count)} / {_e(commercial_count)}</span><span class="data-card-note">{_e(commercial_note)}</span></article>
  <article class="data-card"><span class="data-card-label">质量状态</span><span class="data-card-value">{'通过' if gate.get('eligible') else '受限'}</span><span class="data-card-note">{_e(warning_text)}</span></article>
</div>
<h3>互动统计</h3>
<p class="muted">以中位数为主，10% 截尾均值为辅；最高值保留作异常内容观察，不用于代表日常水平。</p>
<div class="table-wrap"><table class="data-table"><thead><tr><th>指标</th><th class="numeric">中位数</th><th class="numeric">10% 截尾均值</th><th class="numeric">P25–P75</th><th class="numeric">普通均值</th><th class="numeric">最高</th></tr></thead><tbody>{''.join(metric_rows)}</tbody></table></div>
<h3>自然 / 商业表现拆分</h3>
<div class="table-wrap"><table class="data-table"><thead><tr><th>内容层</th><th>指标</th><th class="numeric">样本</th><th class="numeric">中位数</th><th class="numeric">10% 截尾均值</th><th class="numeric">P25–P75</th></tr></thead><tbody>{''.join(segment_rows)}</tbody></table></div>
<div class="two-column" style="margin-top:22px">
  <article class="panel"><h3>高频话题</h3><div class="tag-cloud">{tag_html}</div></article>
  <article class="panel commercial"><h3>标题模式</h3><div class="tag-cloud">{pattern_html}</div></article>
</div>
<details><summary>查看 TOP10 笔记数据</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>#</th><th>标题</th><th class="numeric">赞</th><th class="numeric">藏</th><th class="numeric">相对中位数</th></tr></thead><tbody>{''.join(top_rows) or '<tr><td colspan="5">暂无 TOP 笔记数据</td></tr>'}</tbody></table></div></details>"""


def _longitudinal_snapshot(analysis: dict[str, Any]) -> str:
    longitudinal = analysis.get("longitudinal")
    if not isinstance(longitudinal, dict):
        return ""
    current = longitudinal.get("current", {})
    historical = longitudinal.get("historical", {})
    prior = longitudinal.get("prior_comparison_window", {})
    capabilities = longitudinal.get("historical_capability_candidates", [])
    shifts = longitudinal.get("transition", {}).get("shifts", [])

    def domain_chips(window: dict[str, Any]) -> str:
        domains = [
            (name, item) for name, item in window.get("domains", {}).items()
            if item.get("count", 0)
        ]
        domains.sort(key=lambda pair: pair[1].get("share", 0), reverse=True)
        return "".join(
            f'<span class="tag-item">{_e(name)} · {_e(round(float(item.get("share", 0)) * 100))}%</span>'
            for name, item in domains
        ) or '<span class="tag-item">样本不足</span>'

    capability_html = "".join(
        f'<span class="tag-item">{_e(item.get("domain"))} · {_e(item.get("count"))}篇</span>'
        for item in capabilities
    ) or '<span class="tag-item">历史样本不足，暂不形成能力候选</span>'
    direction_labels = {"emerging": "上升", "declining": "回落", "stable": "稳定"}
    shift_rows = "".join(f"""
<tr><td>{_e(item.get('domain'))}</td><td class="numeric">{_e(round(float(item.get('prior_share', 0)) * 100))}%</td><td class="numeric">{_e(round(float(item.get('current_share', 0)) * 100))}%</td><td class="numeric">{_e(('+' if float(item.get('share_delta', 0)) > 0 else '') + str(round(float(item.get('share_delta', 0)) * 100)) + 'pp')}</td><td>{_e(direction_labels.get(item.get('direction'), item.get('direction')))}</td></tr>""" for item in shifts)
    ready = longitudinal.get("status") == "ready"
    status_text = "可用于判断转型" if ready else "历史样本不足，暂不判断转型"
    return f"""
<section class="section" id="longitudinal">
  <p class="eyebrow">Longitudinal View</p>
  <h2>近期基线、历史能力与转型趋势</h2>
  <p class="section-intro">只使用主页时间序列，不用“教程/推荐”等关键词搜索补样本；{_e(longitudinal.get('dated_note_count', 0))} 篇有日期、{_e(longitudinal.get('undated_note_count', 0))} 篇因日期缺失未进入时间窗口。该视图描述全部公开内容组合，包含自然与商业内容，不替代自然内容定义的本人基线。当前状态：{_e(status_text)}。</p>
  <div class="data-grid">
    <article class="data-card"><span class="data-card-label">近期基线</span><span class="data-card-value">{_e(current.get('count', 0))} 篇</span><span class="data-card-note">{_e(_date(current.get('oldest_published_at')))}—{_e(_date(current.get('newest_published_at')))}</span></article>
    <article class="data-card"><span class="data-card-label">较早主页样本</span><span class="data-card-value">{_e(historical.get('count', 0))} 篇</span><span class="data-card-note">{_e(_date(historical.get('oldest_published_at')))}—{_e(_date(historical.get('newest_published_at')))}</span></article>
    <article class="data-card"><span class="data-card-label">相邻对比窗口</span><span class="data-card-value">{_e(prior.get('count', 0))} 篇</span><span class="data-card-note">与最新窗口比较领域占比</span></article>
  </div>
  <div class="two-column" style="margin-top:22px">
    <article class="panel"><h3>近期内容构成</h3><div class="tag-cloud">{domain_chips(current)}</div></article>
    <article class="panel commercial"><h3>较早窗口能力候选</h3><div class="tag-cloud">{capability_html}</div></article>
  </div>
  <h3>相邻窗口变化</h3>
  <div class="table-wrap"><table class="data-table"><thead><tr><th>领域</th><th class="numeric">上一窗口</th><th class="numeric">近期窗口</th><th class="numeric">变化</th><th>判断</th></tr></thead><tbody>{shift_rows or '<tr><td colspan="5">历史样本不足</td></tr>'}</tbody></table></div>
  <div class="notice-list">{_notice_grid('边界', longitudinal.get('limitations', []))}</div>
</section>"""


def _baseline_page(
    creator: dict[str, Any],
    baseline: dict[str, Any],
    analysis: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> str:
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    metrics = analysis.get("metrics", {})
    cadence = analysis.get("cadence", {})
    performance = analysis.get("performance", {})
    status = baseline.get("review_status", "pending_confirmation")
    status_class = "confirmed" if status == "confirmed" else "pending"
    positioning = baseline.get("summary", {}).get("one_line_positioning", {})
    positioning_text = positioning.get("statement", "待补充") if isinstance(positioning, dict) else positioning
    questions = baseline.get("human_review_questions", [])
    review = f"""
<section class="section" id="review">
  <div class="review-banner">
    <p class="eyebrow">Human Review Gate</p>
    <h2>{'请确认这版画像' if status == 'pending_confirmation' else '画像确认状态：' + STATUS_LABELS.get(status, status)}</h2>
    <p>这是一份基于公开样本的版本化画像。页面只负责阅读；请在 Codex 对话中反馈确认、否定或修订。</p>
    <ol class="review-list">{''.join(f'<li>{_e(question)}</li>' for question in questions) or '<li>当前没有额外确认问题。</li>'}</ol>
  </div>
</section>"""
    body = f"""
<main>
  <section class="hero">
    <div class="shell">
      <p class="eyebrow">Creator Baseline / V{_e(baseline.get('version'))}</p>
      <h1>{_e(creator.get('display_name'))}</h1>
      <p class="hero-copy">{_e(positioning_text)}</p>
      <div class="hero-meta">
        <span class="chip {status_class}">{_e(STATUS_LABELS.get(status, status))}</span>
        <span class="chip">样本 {_e(baseline.get('sample_window', {}).get('sample_count'))} 篇</span>
        <span class="chip">采集 {_e(_date(baseline.get('sample_window', {}).get('captured_at')))}</span>
        <span class="chip">版本 ID {_e(baseline.get('baseline_id'))}</span>
      </div>
    </div>
  </section>
  <div class="shell metric-strip">
    <div class="metric"><span class="metric-label">点赞中位数</span><span class="metric-value">{_e(_number(metrics.get('likes', {}).get('median')))}</span><span class="metric-note">比均值更抗爆款干扰</span></div>
    <div class="metric"><span class="metric-label">收藏 / 点赞</span><span class="metric-value">{_e(f"{float(performance.get('collect_like_ratio')) * 100:.1f}%" if performance.get('collect_like_ratio') is not None else '—')}</span><span class="metric-note">当前采样窗口</span></div>
    <div class="metric"><span class="metric-label">发布间隔</span><span class="metric-value">{_e(str(cadence.get('median_gap_days')) + '天' if cadence.get('median_gap_days') is not None else '—')}</span><span class="metric-note">相邻内容中位数</span></div>
    <div class="metric"><span class="metric-label">Evidence</span><span class="metric-value">{len(evidence)}</span><span class="metric-note">笔记、评论与采集质量</span></div>
  </div>
  <div class="shell layout">
    <nav class="toc" aria-label="页面目录">
      <div class="toc-title">本页目录</div>
      <a href="#review">待确认</a>{'<a href="#intent">团队目标</a>' if baseline.get('human_context') else ''}<a href="#summary">画像摘要</a><a href="#data">数据快照</a>{'<a href="#longitudinal">时间画像</a>' if analysis.get('longitudinal') else ''}<a href="#comparison">自然 / 商业</a><a href="#claims">完整结论</a><a href="#gaps">缺失与限制</a>
    </nav>
    <div class="content">
      {review}
      {_human_context(baseline)}
      <section class="section" id="summary"><p class="eyebrow">01 / Portrait</p><h2>画像摘要</h2><p class="section-intro">四个最常用的决策入口。每项摘要都能展开查看支持证据。</p>{_summary_grid(baseline, evidence_by_id)}</section>
      <section class="section" id="data"><p class="eyebrow">02 / Data Substrate</p><h2>数据快照</h2><p class="section-intro">画像背后的确定性底稿。均值用于看整体，中位数用于减少单篇爆款对判断的干扰。</p>{_data_snapshot(analysis)}</section>
      {_longitudinal_snapshot(analysis)}
      <section class="section" id="comparison"><p class="eyebrow">03 / Commercial Fit</p><h2>自然表达与商业表达</h2><p class="section-intro">后续写品牌路线和大纲时，先保留自然内容基因，再判断产品如何进入。</p>{_comparison(baseline)}</section>
      <section class="section" id="claims"><p class="eyebrow">04 / Evidence-backed Claims</p><h2>完整画像</h2><p class="section-intro">搜索定位、信念、标题、语言、商业植入或护栏。Observed 是直接观察，Inferred 是待确认推断。</p><input class="filter" type="search" placeholder="搜索结论，例如：标题、核心信念、商业植入…" aria-label="搜索画像结论" data-claim-filter>{_claim_sections(baseline, evidence_by_id)}</section>
      <section class="section" id="gaps"><p class="eyebrow">05 / Boundaries</p><h2>缺失维度与限制</h2><p class="section-intro">这些内容不会被系统偷偷补全；后续只有新增 Evidence 或人工确认才能改变。</p><h3>缺失维度</h3><div class="notice-list">{_notice_grid('缺失', baseline.get('missing_dimensions', []))}</div><h3 style="margin-top:32px">分析限制</h3><div class="notice-list">{_notice_grid('限制', baseline.get('limitations', []))}</div></section>
    </div>
  </div>
</main>
<footer class="footer"><div class="shell">本地只读投影 · 数据源位于 .xhs-agent · 页面生成于 {_e(_date(utc_now()))}</div></footer>"""
    return _page(
        title=f"{creator.get('display_name')} Baseline v{baseline.get('version')}",
        asset_prefix="../../../assets",
        body=body,
        home_href="../../../index.html",
    )


def _playbook_page(creator: dict[str, Any], playbook: dict[str, Any]) -> str:
    status = str(playbook.get("review_status", "pending_confirmation"))
    status_class = "confirmed" if status == "confirmed" else "pending"
    axes = "".join(
        f'''<article class="summary-card"><div class="summary-label">当前主轴</div><h3>{_e(item.get("name"))}</h3><p class="summary-statement">{_e(item.get("role"))}</p><p><strong>适用：</strong>{_e(item.get("use_when"))}</p></article>'''
        for item in playbook.get("current_content_axes", [])
    )
    routes = "".join(
        f'''<article class="claim"><div class="claim-head"><div class="claim-type">路线模板</div></div><h3>{_e(item.get("name"))}</h3><p class="claim-statement">{_e(item.get("premise"))}</p><p><strong>适用：</strong>{_e(item.get("use_when"))}</p><ol class="review-list">{"".join(f"<li>{_e(step)}</li>" for step in item.get("structure", []))}</ol><p><strong>产品进入：</strong>{_e(item.get("product_entry"))}</p></article>'''
        for item in playbook.get("route_patterns", [])
    )
    titles = "".join(
        f'''<article class="claim"><h3>{_e(item.get("formula"))}</h3><p>{_e(item.get("use_when"))}</p><div class="notice-list">{"".join(f'<div class="notice"><span>原笔记</span><p>{_e(example.get("text"))}</p><small>{_e(example.get("evidence_id"))}</small></div>' for example in item.get("examples", []))}</div></article>'''
        for item in playbook.get("title_formulas", [])
    )
    templates = "".join(
        f'''<article class="claim"><h3>{_e(item.get("name"))}</h3><p>{_e(item.get("use_when"))}</p><ol class="review-list">{"".join(f"<li>{_e(step)}</li>" for step in item.get("steps", []))}</ol></article>'''
        for item in playbook.get("body_templates", [])
    )
    legacy = "".join(
        f'''<article class="summary-card"><div class="summary-label">历史能力</div><h3>{_e(item.get("name"))}</h3><p>{_e(item.get("current_role"))}</p></article>'''
        for item in playbook.get("legacy_capabilities", [])
    ) or '<div class="empty">当前没有需要单列的历史能力。</div>'
    language = playbook.get("language_kit", {})
    commercial = playbook.get("commercial_rules", {})
    audience = playbook.get("audience_translation", {})
    thesis = playbook.get("core_thesis", {}).get("statement", "")
    review_banner = f'''<div class="review-banner"><p class="eyebrow">Human Review Gate</p><h2>{"请确认这份执行指南" if status == "pending_confirmation" else "执行指南已确认"}</h2><p>请重点检查：路线是否像本人、商业植入是否足够自然、历史能力是否被放在正确位置。页面只读，反馈在 Codex 对话中完成。</p></div>'''
    body = f'''
<main><section class="hero"><div class="shell"><p class="eyebrow">Creator Playbook / V{_e(playbook.get("version"))}</p><h1>{_e(creator.get("display_name"))} · 创作执行指南</h1><p class="hero-copy">{_e(thesis)}</p><div class="hero-meta"><span class="chip {status_class}">{_e(STATUS_LABELS.get(status, status))}</span><span class="chip">绑定 Baseline {_e(playbook.get("baseline_id"))}</span></div></div></section>
<div class="shell layout"><nav class="toc"><div class="toc-title">本页目录</div><a href="#review">待确认</a><a href="#axes">当前主轴</a><a href="#audience">受众翻译</a><a href="#routes">路线模板</a><a href="#titles">标题公式</a><a href="#body">正文结构</a><a href="#language">语言工具箱</a><a href="#commercial">商业规则</a><a href="#legacy">历史能力</a><a href="#check">出稿检查</a></nav><div class="content">
<section class="section" id="review">{review_banner}</section>
<section class="section" id="axes"><p class="eyebrow">01 / Current Identity</p><h2>当前内容主轴</h2><div class="summary-grid">{axes}</div></section>
<section class="section" id="audience"><p class="eyebrow">02 / Audience</p><h2>从现有受众到目标人群</h2><div class="two-column"><article class="panel"><h3>样本观察</h3><p>{_e(audience.get("observed_audience"))}</p></article><article class="panel commercial"><h3>团队目标</h3><p>{_e(audience.get("desired_audience"))}</p></article></div><h3>内容中应出现的信号</h3>{_items(audience.get("content_signals", []))}</section>
<section class="section" id="routes"><p class="eyebrow">03 / Routes</p><h2>可复用路线模板</h2><p class="section-intro">用于选题和大纲，不是最终逐字稿。</p><div class="claim-list">{routes}</div></section>
<section class="section" id="titles"><p class="eyebrow">04 / Titles</p><h2>标题公式与原笔记例子</h2><div class="claim-list">{titles}</div></section>
<section class="section" id="body"><p class="eyebrow">05 / Structure</p><h2>正文 / 口播结构</h2><div class="claim-list">{templates}</div></section>
<section class="section" id="language"><p class="eyebrow">06 / Language</p><h2>语言工具箱</h2><div class="two-column"><article class="panel"><h3>保留</h3>{_items(language.get("keep", []))}<h3>CTA</h3>{_items(language.get("cta", []))}</article><article class="panel commercial"><h3>避免</h3>{_items(language.get("avoid", []))}</article></div></section>
<section class="section" id="commercial"><p class="eyebrow">07 / Commercial</p><h2>商业合作规则</h2><h3>默认自然植入</h3>{_items(commercial.get("default_path", []))}<h3>品牌强约束时的例外</h3>{_items(commercial.get("exception_path", []))}<h3>提交前检查</h3>{_items(commercial.get("checklist", []))}</section>
<section class="section" id="legacy"><p class="eyebrow">08 / Legacy</p><h2>历史能力，不等于当前主轴</h2><div class="summary-grid">{legacy}</div></section>
<section class="section" id="check"><p class="eyebrow">09 / QA</p><h2>助理出稿检查</h2>{_items(playbook.get("review_checklist", []))}<h3>边界</h3>{_items(playbook.get("limitations", []))}</section>
</div></div></main><footer class="footer"><div class="shell">Creator Playbook · 本地只读 · 修改会创建新版本</div></footer>'''
    return _page(title=f"{creator.get('display_name')} Playbook v{playbook.get('version')}", asset_prefix="../../../assets", body=body, home_href="../../../index.html")


def _creator_page(creator: dict[str, Any], baselines: list[dict[str, Any]], playbooks: list[dict[str, Any]]) -> str:
    latest = baselines[-1] if baselines else None
    positioning = "尚未生成 Baseline。"
    if latest:
        item = latest.get("summary", {}).get("one_line_positioning", {})
        positioning = item.get("statement", "待补充") if isinstance(item, dict) else str(item)
    versions = "".join(
        f"""<a class="version-link" href="baselines/{_e(item['baseline_id'])}.html"><span><strong>Baseline v{_e(item['version'])}</strong> · {_e(STATUS_LABELS.get(item.get('review_status'), item.get('review_status')))}</span><span>{_e(_date(item.get('created_at')))} →</span></a>"""
        for item in reversed(baselines)
    ) or '<div class="empty">这个 Creator 还没有可展示的 Baseline。</div>'
    playbook_versions = "".join(
        f'''<a class="version-link" href="playbooks/{_e(item['playbook_id'])}.html"><span><strong>Playbook v{_e(item['version'])}</strong> · {_e(STATUS_LABELS.get(item.get('review_status'), item.get('review_status')))}</span><span>{_e(_date(item.get('created_at')))} →</span></a>'''
        for item in reversed(playbooks)
    ) or '<div class="empty">确认 Baseline 后可生成执行指南。</div>'
    body = f"""
<main class="shell">
  <section class="hero"><p class="eyebrow">Creator Archive</p><h1>{_e(creator.get('display_name'))}</h1><p class="hero-copy">{_e(positioning)}</p><div class="hero-meta"><span class="chip">{len(baselines)} 个历史版本</span><span class="chip">{_e(creator.get('creator_id'))}</span></div></section>
  <section class="section" style="padding-top:44px"><h2>Baseline 版本</h2><p class="section-intro">每次蒸馏都会新增版本，不覆盖历史。项目未来绑定具体版本，而不是隐式读取最新值。</p><div class="version-list">{versions}</div></section>
  <section class="section"><h2>Creator Playbook</h2><p class="section-intro">把已确认画像翻译成助理可直接使用的选题、路线、标题、正文结构和商业护栏。</p><div class="version-list">{playbook_versions}</div></section>
</main>
<footer class="footer"><div class="shell">Creator 本地档案 · 只读</div></footer>"""
    return _page(
        title=str(creator.get("display_name")),
        asset_prefix="../../assets",
        body=body,
        home_href="../../index.html",
    )


def _items(values: list[Any], empty: str = "暂无") -> str:
    return "<ul class=\"review-list\">" + ("".join(f"<li>{_e(value)}</li>" for value in values) or f"<li>{_e(empty)}</li>") + "</ul>"


def _project_page(project: dict[str, Any], brief: dict[str, Any] | None, routes: list[dict[str, Any]], outlines: list[dict[str, Any]], copies: list[dict[str, Any]], bundle: dict[str, Any] | None, backtests: list[dict[str, Any]]) -> str:
    project_id = project["project_id"]
    states = project.get("workflow_state", {})
    route_link = '<a class="version-link" href="routes.html"><span><strong>内容路线</strong></span><span>查看 →</span></a>' if routes else ""
    brief_link = '<a class="version-link" href="brief.html"><span><strong>结构化 Brief</strong></span><span>查看 →</span></a>' if brief else ""
    outlines_html = "".join(f'<a class="version-link" href="outlines/{_e(item["outline_id"])}.html"><span><strong>大纲 V{_e(item["version"])}</strong></span><span>{_e(_date(item["created_at"]))} →</span></a>' for item in reversed(outlines))
    copies_html = "".join(f'<a class="version-link" href="copy/{_e(item["copy_id"])}.html"><span><strong>发布文案 V{_e(item["version"])}</strong></span><span>{_e(_date(item["created_at"]))} →</span></a>' for item in reversed(copies))
    backtests_html = "".join(f'<a class="version-link" href="backtests/{_e(item["backtest_id"])}.html"><span><strong>大纲盲测复盘</strong> · {_e(item.get("verdict"))}</span><span>{_e(_date(item.get("created_at")))} →</span></a>' for item in reversed(backtests))
    archive_link = f'<a class="version-link" href="archive.html"><span><strong>最终发布归档</strong> · {_e(bundle.get("completeness"))}</span><span>查看差异 →</span></a>' if bundle else ""
    body = f"""<main class="shell"><section class="hero"><p class="eyebrow">Brand Project</p><h1>{_e(project['title'])}</h1><p class="hero-copy">{_e(project['brand'])} · {_e(project['product'])}</p><div class="hero-meta"><span class="chip">大纲 {_e(states.get('outline'))}</span><span class="chip">发布文案 {_e(states.get('publication_copy'))}</span><span class="chip">归档 {_e(states.get('archive'))}</span><span class="chip">Baseline {_e(project['baseline_id'])}</span></div></section><section class="section"><h2>项目材料</h2><div class="version-list">{brief_link}{route_link}{outlines_html}{backtests_html}{copies_html or '<div class="empty">发布文案将在大纲品牌确认后生成。</div>'}{archive_link}</div></section></main><footer class="footer"><div class="shell">项目 ID {_e(project_id)} · 本地只读</div></footer>"""
    return _page(title=project["title"], asset_prefix="../../assets", body=body, home_href="../../index.html")


def _brief_page(project: dict[str, Any], brief: dict[str, Any]) -> str:
    fact_cards = _items(brief.get("facts", [])); inference_cards = _items([f"{item.get('statement')}（{round(float(item.get('confidence', 0))*100)}%）" for item in brief.get("inferences", [])]); questions = _items(brief.get("open_questions", []), "没有阻断性问题")
    body = f"""<main class="shell"><section class="hero"><p class="eyebrow">Structured Brief</p><h1>{_e(project['brand'])} · {_e(project['product'])}</h1><p class="hero-copy">事实、推断和待确认项分栏保存；原件始终留在私有目录。</p></section><div class="two-column"><section class="panel"><h2>交付与场景</h2><p>交付物：{_e(brief.get('deliverable'))}</p><p>场景：{_e(brief.get('scene') or '未明确')}</p><h3>卖点</h3>{_items(brief.get('selling_points', []))}<h3>必须包含</h3>{_items(brief.get('must_include', []))}<h3>禁用</h3>{_items(brief.get('forbidden', []))}</section><section class="panel"><h2>原文事实</h2>{fact_cards}<h2>系统推断</h2>{inference_cards}<h2>待确认</h2>{questions}</section></div></main>"""
    return _page(title="结构化 Brief", asset_prefix="../../assets", body=body, home_href="index.html")


def _routes_page(project: dict[str, Any], routes: list[dict[str, Any]], selection: dict[str, Any] | None) -> str:
    cards = []
    for index, route in enumerate(routes, start=1):
        selected = selection and selection.get("route_id") == route.get("route_id")
        cards.append(f"""<article class="summary-card"><div class="summary-label">路线 {index} {'· 已选择' if selected else '· 推荐' if route.get('recommended') else ''}</div><p class="summary-statement">{_e(route.get('premise'))}</p><p><strong>张力</strong> {_e(route.get('conflict'))}</p><p><strong>场景</strong> {_e(route.get('scene'))}</p><p><strong>产品角色</strong> {_e(route.get('product_role'))}</p><p><strong>适配</strong> {_e(route.get('creator_fit', {}).get('reason'))}</p><h3>风险</h3>{_items(route.get('risks', []))}</article>""")
    body = f"""<main class="shell"><section class="hero"><p class="eyebrow">Content Routes</p><h1>{_e(project['title'])} · 路线</h1><p class="hero-copy">路线解决“为什么这样讲”。页面只供比较，选择通过 Codex 对话登记。</p></section><div class="summary-grid">{''.join(cards)}</div></main>"""
    return _page(title="内容路线", asset_prefix="../../assets", body=body, home_href="index.html")


def _outline_page(project: dict[str, Any], outline: dict[str, Any], route: dict[str, Any] | None) -> str:
    rows = []
    for item in outline.get("sections", []):
        duration = item.get("duration_seconds", {})
        minimum, maximum = duration.get("min", "—"), duration.get("max", "—")
        seconds = f"{minimum} 秒" if minimum == maximum else f"{minimum}–{maximum} 秒"
        label = item.get("label") or f"段落 {item.get('order')}"
        shots = "<br>".join(f"• {_e(value)}" for value in item.get("shots", [])) or "—"
        voiceover = "<br>".join(f"• {_e(value)}" for value in item.get("rough_voiceover", [])) or "—"
        on_screen = "<br>".join(f"• {_e(value)}" for value in item.get("on_screen_text", [])) or "—"
        rows.append(f"""<tr><td><strong>{_e(item.get('order'))}. {_e(label)}</strong><br><span class="muted">{_e(item.get('goal'))}</span></td><td>{_e(seconds)}</td><td>{shots}</td><td>{voiceover}</td><td>{on_screen}</td><td>{_e(item.get('brand_presence') or '无')}</td></tr>""")
    duration = outline.get("estimated_duration_seconds", {})
    target = outline.get("target_duration_seconds")
    total = f"目标 {target} 秒" if target else f"约 {duration.get('min', '—')}–{duration.get('max', '—')} 秒"
    sections = f"""<div class="table-wrap"><table class="data-table"><thead><tr><th>段落</th><th>秒数</th><th>镜头摘要</th><th>大致口播</th><th>花字</th><th>品牌露出</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""
    labels = {item.get("order"): item.get("label") for item in outline.get("sections", [])}
    shot_rows = []
    for shot in outline.get("shot_rows", []):
        on_screen = "<br>".join(f"• {_e(value)}" for value in shot.get("on_screen_text", [])) or "—"
        notes = list(shot.get("audio_or_notes", []))
        if shot.get("brand_presence"):
            notes.append(f"品牌露出：{shot['brand_presence']}")
        note_html = "<br>".join(f"• {_e(value)}" for value in notes) or "—"
        group = f"{shot.get('section_order')}. {labels.get(shot.get('section_order'), '—')}"
        shot_rows.append(f"""<tr><td><strong>镜 {_e(shot.get('shot_no'))}</strong><br><span class="muted">{_e(group)}</span></td><td>{_e(shot.get('duration_seconds'))} 秒</td><td>{_e(shot.get('scene'))}</td><td>{_e(shot.get('framing'))}</td><td>{_e(shot.get('rough_voiceover'))}</td><td>{on_screen}</td><td>{note_html}</td></tr>""")
    storyboard = f"""<div class="table-wrap"><table class="data-table"><thead><tr><th>镜号 / 分组</th><th>秒数</th><th>拍摄场景 / 画面内容</th><th>景别 / 机位</th><th>大致口播 / VO</th><th>花字</th><th>音效 / 品牌露出 / 拍摄要点</th></tr></thead><tbody>{''.join(shot_rows)}</tbody></table></div>""" if shot_rows else '<div class="empty">该历史版本尚未生成逐镜头表。</div>'
    range_text = f"预计范围 {duration.get('min', '—')}–{duration.get('max', '—')} 秒"
    body = f"""<main><section class="hero"><div class="shell"><p class="eyebrow">Outline Preview / V{_e(outline['version'])}</p><h1>{_e(project['title'])}</h1><p class="hero-copy">{_e(route.get('premise') if route else '')}</p><div class="hero-meta"><span class="chip">品牌审核大纲</span><span class="chip">{_e(total)}</span><span class="chip">Baseline {_e(project['baseline_id'])}</span></div></div></section><div class="shell layout"><nav class="toc"><div class="toc-title">本页目录</div><a href="#titles">标题与 Hook</a><a href="#strategy">7 段策略骨架</a><a href="#shots">逐镜头品牌模板</a><a href="#checks">覆盖检查</a></nav><div class="content"><section class="section" id="titles"><h2>选题与暂定标题</h2>{_items(outline.get('working_titles', []))}<h3>Hook</h3>{_items(outline.get('hooks', []))}</section><section class="section" id="strategy"><h2>第一层：7 段叙事骨架</h2><p class="section-intro">{_e(range_text)}。这一层用于判断路线、节奏和品牌进入方式。</p>{sections}</section><section class="section" id="shots"><h2>第二层：逐镜头 Shot Rows</h2><p class="section-intro">{_e(total)}，共 {_e(len(shot_rows))} 镜。每行是可拍摄、可计时、可复制进品牌模板的执行单元；大致口播不是博主最终逐字稿。</p>{storyboard}</section><section class="section" id="checks"><h2>交付检查</h2><h3>Brief 覆盖</h3>{_items(outline.get('brief_coverage', []))}<h3>博主适配</h3>{_items(outline.get('creator_fit_checks', []))}<h3>风险与待确认</h3>{_items(outline.get('risks', []) + outline.get('open_questions', []))}</section></div></div></main>"""
    return _page(title=f"大纲 V{outline['version']}", asset_prefix="../../../assets", body=body, home_href="../index.html")


def _copy_page(project: dict[str, Any], copy: dict[str, Any]) -> str:
    tags = " ".join("#" + str(value).lstrip("#") for value in copy.get("tags", []))
    title_options = "".join(
        f'<li><span>{_e(value)}</span> <span class="muted">· {_e(len(str(value)))} 字符</span></li>'
        for value in copy.get("title_options", [])
    )
    titles = f'<ul class="review-list">{title_options}</ul>' if title_options else '<div class="empty">暂无标题候选。</div>'
    body_text = str(copy.get("body") or "")
    body = f"""<main class="shell"><section class="hero"><p class="eyebrow">Publication Copy / V{_e(copy['version'])}</p><h1>{_e(project['title'])}</h1><p class="hero-copy">大纲确认后的标题、正文和 Tags 独立审核链。</p><div class="hero-meta"><span class="chip">正文 {_e(len(body_text))} 字符</span><span class="chip">{_e(len(copy.get('tags', [])))} 个 Tags</span><span class="chip">Approved Outline {_e(copy.get('approved_outline_id'))}</span></div></section><section class="section"><h2>标题候选</h2><p class="section-intro">字符数用于发布前人工检查；平台规则以实际发布端提示为准。</p>{titles}<h2>小红书正文</h2><article class="claim"><p class="claim-statement" style="white-space:pre-wrap">{_e(body_text)}</p></article><h2>Tags</h2><p>{_e(tags)}</p><h2>Brief 覆盖</h2>{_items(copy.get('brief_coverage', []))}<h2>风险与发布前确认</h2>{_items(copy.get('risks', []), '没有待确认风险')}</section></main>"""
    return _page(title=f"发布文案 V{copy['version']}", asset_prefix="../../../assets", body=body, home_href="../index.html")


def _backtest_page(project: dict[str, Any], report: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><td><strong>{_e(item.get('dimension'))}</strong></td><td>{_e(item.get('generated'))}</td><td>{_e(item.get('historical'))}</td><td>{_e(item.get('assessment'))}</td></tr>"
        for item in report.get("scorecard", [])
    )
    gaps = "".join(
        f"""<article class="claim"><div class="claim-head"><div class="claim-type">{_e(item.get('priority'))} priority</div></div><p class="claim-statement">{_e(item.get('gap'))}</p><p><strong>证据</strong> {_e(item.get('evidence'))}</p><p><strong>建议</strong> {_e(item.get('recommendation'))}</p></article>"""
        for item in report.get("material_gaps", [])
    ) or '<div class="empty">没有发现实质缺口。</div>'
    metrics = report.get("performance_context", {})
    metric_text = " · ".join(f"{key} {_e(value)}" for key, value in metrics.get("metrics", {}).items())
    sources = "".join(
        f"<li><strong>{_e(item.get('label'))}</strong>：{_e(item.get('reference'))}{' · ' + _e(item.get('note')) if item.get('note') else ''}</li>"
        for item in report.get("sources", [])
    )
    learning = report.get("learning_candidates", {})
    body = f"""<main><section class="hero"><div class="shell"><p class="eyebrow">Blind Backtest / {_e(report.get('review_status'))}</p><h1>{_e(project['title'])} · 大纲盲测复盘</h1><p class="hero-copy">{_e(report.get('summary'))}</p><div class="hero-meta"><span class="chip">{_e(report.get('verdict'))}</span><span class="chip">Outline {_e(report.get('outline_id'))}</span><span class="chip">发布后约 {_e(metrics.get('captured_after_hours'))} 小时采集</span></div></div></section><div class="shell layout"><nav class="toc"><div class="toc-title">本页目录</div><a href="#verdict">结论</a><a href="#scorecard">逐项对比</a><a href="#gaps">关键缺口</a><a href="#performance">数据边界</a><a href="#learning">学习建议</a></nav><div class="content"><section class="section" id="verdict"><h2>回测结论</h2><article class="claim"><p class="claim-statement">{_e(report.get('verdict'))}</p><p>{_e(report.get('summary'))}</p></article><h3>独立命中的核心结构</h3>{_items(report.get('key_matches', []))}<h3>有意保留的差异</h3>{_items(report.get('deliberate_differences', []))}</section><section class="section" id="scorecard"><h2>生成大纲 vs 历史定稿</h2><div class="table-wrap"><table class="data-table"><thead><tr><th>维度</th><th>生成大纲 V1</th><th>历史定稿</th><th>判断</th></tr></thead><tbody>{rows}</tbody></table></div></section><section class="section" id="gaps"><h2>关键缺口</h2><div class="claim-list">{gaps}</div></section><section class="section" id="performance"><h2>发布数据只作早期事实</h2><article class="claim"><p class="claim-statement">{_e(metric_text)}</p><p>{_e(metrics.get('interpretation'))}</p></article><h3>参考基线</h3>{_items(metrics.get('reference_benchmark', []))}</section><section class="section" id="learning"><h2>候选学习，不自动回写</h2><div class="two-column"><article class="panel"><h3>保留</h3>{_items(learning.get('keep', []))}<h3>应修改</h3>{_items(learning.get('change', []))}</article><article class="panel commercial"><h3>不要学习</h3>{_items(learning.get('do_not_learn', []))}<h3>下一步</h3><p>{_e(report.get('next_step'))}</p></article></div><h3>对比来源</h3><ul class="review-list">{sources}</ul></section></div></div></main>"""
    return _page(title="大纲盲测复盘", asset_prefix="../../../assets", body=body, home_href="../index.html")


def _diff_cards(diff: dict[str, Any] | None) -> str:
    if not diff: return '<div class="empty">等待两类最终文件齐全后生成差异。</div>'
    cards = "".join(f"""<article class="claim"><div class="claim-head"><div class="claim-type">{_e(item.get('type'))}</div><div class="confidence">{_e(item.get('likely_source'))} · {_e(round(float(item.get('confidence', 0))*100))}%</div></div><p class="claim-statement">{_e(item.get('description'))}</p><div class="claim-meta">原确认稿：{_e(item.get('approved_ref') or '—')} · 最终稿：{_e(item.get('final_ref') or '—')}</div></article>""" for item in diff.get("changes", []))
    return f'<p class="section-intro">{_e(diff.get("summary"))}</p><div class="claim-list">{cards or "<div class=empty>没有记录到实质变化。</div>"}</div>'


def _archive_page(project: dict[str, Any], bundle: dict[str, Any], learning: list[dict[str, Any]]) -> str:
    tags = " ".join("#" + str(value).lstrip("#") for value in bundle.get("published_tags", []))
    learning_html = "".join(f"""<article class="summary-card"><div class="summary-label">{_e(item.get('scope'))} · {_e(item.get('status'))}</div><p class="summary-statement">{_e(item.get('statement'))}</p><p>{_e(item.get('reason'))}</p><div class="summary-foot">置信度 {_e(round(float(item.get('confidence', 0))*100))}% · {_e(item.get('candidate_id'))}</div></article>""" for item in learning) or '<div class="empty">当前没有候选经验。</div>'
    oral_ref = bundle.get("oral_script_source") or {}
    copy_ref = bundle.get("published_copy_source") or {}
    screenshot_ref = bundle.get("published_copy_screenshot_source") or {}
    published_url = bundle.get("published_url")
    source_links = f"""<ul class="review-list"><li>最终口播原件：{_e(oral_ref.get('original_name') or '未上传')} · SHA {_e(str(oral_ref.get('sha256') or '—')[:12])}</li><li>发布配文转写：{_e(copy_ref.get('original_name') or '未上传')} · SHA {_e(str(copy_ref.get('sha256') or '—')[:12])}</li><li>发布截图原件：{_e(screenshot_ref.get('original_name') or '未上传')} · SHA {_e(str(screenshot_ref.get('sha256') or '—')[:12])}</li>{f'<li><a href="{_e(published_url)}">打开实际发布链接 ↗</a></li>' if published_url else ''}</ul>"""
    body = f"""<main><section class="hero"><div class="shell"><p class="eyebrow">Final Publication Archive</p><h1>{_e(project['title'])}</h1><p class="hero-copy">确认稿与最终发布事实的双轨对照。候选经验必须经过人工 Review。</p><div class="hero-meta"><span class="chip">{_e(bundle.get('completeness'))}</span><span class="chip">发布 {_e(_date(bundle.get('published_at')))}</span><span class="chip">截图原件 {'已保留' if screenshot_ref else '未上传'}</span></div></div></section><div class="shell layout"><nav class="toc"><div class="toc-title">本页目录</div><a href="#final">最终内容</a><a href="#outline-diff">口播差异</a><a href="#copy-diff">配文差异</a><a href="#learning">候选经验</a></nav><div class="content"><section class="section" id="final"><h2>最终发布事实</h2><h3>{_e(bundle.get('published_title') or '实际标题待结构化')}</h3><article class="claim"><p class="claim-statement" style="white-space:pre-wrap">{_e(bundle.get('published_body') or bundle.get('published_copy_extracted_text') or '实际发布配文尚未上传')}</p><p>{_e(tags)}</p></article><h3>归档原件</h3>{source_links}<h3>最终口播脚本</h3><article class="claim"><p class="claim-statement" style="white-space:pre-wrap">{_e(bundle.get('oral_script') or '最终口播脚本尚未上传')}</p></article></section><section class="section" id="outline-diff"><h2>Approved Outline → 最终口播</h2>{_diff_cards(bundle.get('approved_outline_diff'))}</section><section class="section" id="copy-diff"><h2>Approved Copy → 实际发布配文</h2>{_diff_cards(bundle.get('approved_copy_diff'))}</section><section class="section" id="learning"><h2>候选经验</h2><p class="section-intro">接受只表示值得复用，不会自动修改 Creator Baseline。</p><div class="summary-grid">{learning_html}</div></section></div></div></main>"""
    return _page(title="最终发布归档", asset_prefix="../../assets", body=body, home_href="index.html")


def _index_page(creators: list[tuple[dict[str, Any], list[dict[str, Any]]]], projects: list[dict[str, Any]], warnings: list[str]) -> str:
    cards = []
    total_baselines = 0
    for creator, baselines in creators:
        total_baselines += len(baselines)
        latest = baselines[-1] if baselines else None
        summary = "尚未生成 Baseline。"
        if latest:
            item = latest.get("summary", {}).get("one_line_positioning", {})
            summary = item.get("statement", "待补充") if isinstance(item, dict) else str(item)
        cards.append(f"""
<a class="creator-card home-card" href="creators/{_e(creator['creator_id'])}/index.html">
  <div class="card-meta"><span>CREATOR</span><span>{'V' + str(latest.get('version')) if latest else 'NO BASELINE'}</span></div>
  <h2>{_e(creator.get('display_name'))}</h2>
  <p>{_e(summary)}</p>
</a>""")
    content = f'<div class="creator-grid home-grid">{"".join(cards)}</div>' if cards else """
<div class="empty">
  <h2>还没有博主画像</h2>
  <p>完成本人账号分析和 Baseline finalize 后，再运行 Workbench build，这里会出现可阅读的本地档案。</p>
  <code>xhs-agent creator analyze …</code>
</div>"""
    project_cards = "".join(f"""<a class="creator-card home-card" href="projects/{_e(item['project_id'])}/index.html"><div class="card-meta"><span>PROJECT</span><span>{_e(item.get('workflow_state', {}).get('outline'))}</span></div><h2>{_e(item.get('title'))}</h2><p>{_e(item.get('brand'))} · {_e(item.get('product'))}</p></a>""" for item in projects)
    projects_html = f'<section class="home-section"><p class="eyebrow">Active & Archived</p><h2>合作项目</h2><div class="creator-grid home-grid">{project_cards}</div></section>' if project_cards else ""
    warning_html = "" if not warnings else f'<div class="review-banner" style="margin-top:28px"><strong>构建时跳过了 {len(warnings)} 个无效对象。</strong></div>'
    body = f"""
<main class="shell">
  <section class="hero"><p class="eyebrow">Private Creator Intelligence</p><h1>创作工作台</h1><p class="hero-copy">把博主画像、品牌项目和历史版本放在一个非技术用户也能直接阅读的本地入口。</p><div class="hero-meta"><span class="chip">{len(creators)} 位博主</span><span class="chip">{len(projects)} 个项目</span><span class="chip">只读 · 本机</span></div></section>
  {warning_html}
  <div class="home-sections">
    <section class="home-section"><p class="eyebrow">Creator Profiles</p><h2>博主档案</h2>{content}</section>
    {projects_html}
  </div>
</main>
<footer class="footer"><div class="shell">HTML 可以删除并随时重建；结构化事实仍在 .xhs-agent。</div></footer>"""
    return _page(title="首页", asset_prefix="assets", body=body, home_href="index.html")


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _baseline_version(value: dict[str, Any]) -> int:
    try:
        return int(value.get("version", 0))
    except (TypeError, ValueError):
        return 0


def build_workbench(state: Path, output: Path) -> BuildResult:
    state = state.resolve()
    output = output.resolve()
    warnings: list[str] = []
    creator_records: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    project_records: list[dict[str, Any]] = []
    pages: dict[Path, str] = {}
    creator_root = state / "creators"
    if creator_root.is_dir():
        for directory in sorted(path for path in creator_root.iterdir() if path.is_dir()):
            try:
                creator = read_json(directory / "creator.json")
                if not isinstance(creator, dict) or not creator.get("creator_id"):
                    raise ValueError("creator.json 无效")
                baselines = []
                for baseline_path in sorted((directory / "baselines").glob("*.json")):
                    value = read_json(baseline_path)
                    if isinstance(value, dict) and value.get("baseline_id"):
                        baselines.append(value)
                    else:
                        warnings.append(f"跳过无效 Baseline：{baseline_path.name}")
                baselines.sort(key=_baseline_version)
                playbooks = []
                for playbook_path in sorted((directory / "playbooks").glob("*.json")):
                    value = read_json(playbook_path)
                    if isinstance(value, dict) and value.get("playbook_id"):
                        playbooks.append(value)
                    else:
                        warnings.append(f"跳过无效 Playbook：{playbook_path.name}")
                playbooks.sort(key=_baseline_version)
                creator_records.append((creator, baselines))
                creator_id = creator["creator_id"]
                pages[Path("creators") / creator_id / "index.html"] = _creator_page(creator, baselines, playbooks)
                for playbook in playbooks:
                    relative = Path("creators") / creator_id / "playbooks" / f"{playbook['playbook_id']}.html"
                    pages[relative] = _playbook_page(creator, playbook)
                for baseline in baselines:
                    run_id = baseline.get("source_run_id")
                    analysis = read_json(directory / "source" / "runs" / str(run_id) / "analysis.json", {})
                    evidence = read_json(directory / "evidence" / f"{run_id}.json", [])
                    longitudinal_run_id = baseline.get("longitudinal_run_id")
                    if longitudinal_run_id and isinstance(analysis, dict):
                        longitudinal_analysis = read_json(
                            directory / "source" / "runs" / str(longitudinal_run_id) / "analysis.json",
                            {},
                        )
                        if isinstance(longitudinal_analysis, dict) and isinstance(
                            longitudinal_analysis.get("longitudinal"), dict
                        ):
                            analysis = {**analysis, "longitudinal": longitudinal_analysis["longitudinal"]}
                        else:
                            warnings.append(
                                f"Baseline {baseline.get('baseline_id')} 缺少纵向分析：{longitudinal_run_id}"
                            )
                    if not isinstance(analysis, dict) or not isinstance(evidence, list):
                        warnings.append(f"Baseline {baseline.get('baseline_id')} 缺少分析或 Evidence")
                        analysis = analysis if isinstance(analysis, dict) else {}
                        evidence = evidence if isinstance(evidence, list) else []
                    relative = Path("creators") / creator_id / "baselines" / f"{baseline['baseline_id']}.html"
                    pages[relative] = _baseline_page(creator, baseline, analysis, evidence)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                warnings.append(f"跳过 Creator {directory.name}：{exc}")

    project_root = state / "projects"
    if project_root.is_dir():
        for directory in sorted(path for path in project_root.iterdir() if path.is_dir()):
            try:
                project = read_json(directory / "project.json")
                if not isinstance(project, dict) or not project.get("project_id"):
                    raise ValueError("project.json 无效")
                active = read_json(directory / "brief" / "active.json", {})
                brief = read_json(Path(active["path"])) if isinstance(active, dict) and active.get("path") else None
                routes = []
                for route_path in (directory / "routes").glob("*/*.json"):
                    if route_path.name == "route-set.json": continue
                    value = read_json(route_path)
                    if isinstance(value, dict) and value.get("route_id"): routes.append(value)
                selection = read_json(directory / "routes" / "selection.json")
                outlines = [value for path in (directory / "outlines").glob("*.json") if isinstance((value := read_json(path)), dict)]
                outlines.sort(key=lambda item: int(item.get("version", 0)))
                copies = [value for path in (directory / "publication-copy").glob("*.json") if isinstance((value := read_json(path)), dict)]
                copies.sort(key=lambda item: int(item.get("version", 0)))
                backtests = [value for path in (directory / "backtests").glob("*.json") if isinstance((value := read_json(path)), dict)]
                backtests.sort(key=lambda item: str(item.get("created_at", "")))
                bundle = read_json(directory / "archive" / "bundle.json")
                learning = [value for path in (directory / "learning").glob("*.json") if isinstance((value := read_json(path)), dict)]
                project_records.append(project)
                base = Path("projects") / project["project_id"]
                pages[base / "index.html"] = _project_page(project, brief, routes, outlines, copies, bundle if isinstance(bundle, dict) else None, backtests)
                if isinstance(brief, dict): pages[base / "brief.html"] = _brief_page(project, brief)
                if routes: pages[base / "routes.html"] = _routes_page(project, routes, selection if isinstance(selection, dict) else None)
                route_by_id = {item["route_id"]: item for item in routes}
                for outline in outlines: pages[base / "outlines" / f"{outline['outline_id']}.html"] = _outline_page(project, outline, route_by_id.get(outline.get("route_id")))
                for copy in copies: pages[base / "copy" / f"{copy['copy_id']}.html"] = _copy_page(project, copy)
                for report in backtests: pages[base / "backtests" / f"{report['backtest_id']}.html"] = _backtest_page(project, report)
                if isinstance(bundle, dict): pages[base / "archive.html"] = _archive_page(project, bundle, learning)
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                warnings.append(f"跳过 Project {directory.name}：{exc}")

    pages[Path("index.html")] = _index_page(creator_records, project_records, warnings)
    asset_root = files("xhs_agent.renderers.assets")
    pages[Path("assets/workbench.css")] = asset_root.joinpath("workbench.css").read_text(encoding="utf-8")
    pages[Path("assets/workbench.js")] = asset_root.joinpath("workbench.js").read_text(encoding="utf-8")

    manifest_path = state / "cache" / "workbench-manifest.json"
    previous = read_json(manifest_path, {"generated_files": []})
    new_files = {str(path) for path in pages}
    for relative_text in previous.get("generated_files", []) if isinstance(previous, dict) else []:
        stale = (output / str(relative_text)).resolve()
        if stale.is_relative_to(output) and str(relative_text) not in new_files and stale.is_file():
            stale.unlink()
    for relative, content in pages.items():
        _write_text_atomic(output / relative, content)
    write_json_atomic(manifest_path, {
        "schema_version": 1,
        "generated_at": utc_now(),
        "generated_files": sorted(new_files),
        "warnings": warnings,
    })
    return BuildResult(
        output=output,
        index_path=output / "index.html",
        creator_count=len(creator_records),
        baseline_count=sum(len(items) for _creator, items in creator_records),
        project_count=len(project_records),
        page_count=sum(path.suffix == ".html" for path in pages),
        warnings=warnings,
    )
