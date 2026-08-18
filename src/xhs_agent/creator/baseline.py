from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any


CATEGORIES = {
    "positioning", "audience", "cognition", "strategy", "organic",
    "commercial", "voice", "visual", "guardrail",
}
FINDING_TYPES = {
    "positioning", "audience_need", "content_pillar", "core_belief",
    "viewpoint_tension", "mental_model", "value_stance", "content_series",
    "topical_strategy", "operating_hypothesis", "title_formula",
    "opening_pattern", "body_structure", "emotional_arc", "language_dna",
    "cta_pattern", "tag_strategy", "publishing_cadence",
    "commercial_integration", "commercial_difference", "must_keep",
    "avoid", "unknown_visual",
}
FINDING_CATEGORIES = {
    "positioning": {"positioning"},
    "content_pillar": {"positioning"},
    "audience_need": {"audience"},
    "core_belief": {"cognition"},
    "viewpoint_tension": {"cognition"},
    "mental_model": {"cognition"},
    "value_stance": {"cognition"},
    "content_series": {"strategy"},
    "topical_strategy": {"strategy"},
    "operating_hypothesis": {"strategy"},
    "publishing_cadence": {"strategy"},
    "title_formula": {"organic"},
    "opening_pattern": {"organic"},
    "body_structure": {"organic"},
    "emotional_arc": {"organic"},
    "commercial_integration": {"commercial"},
    "commercial_difference": {"commercial"},
    "language_dna": {"voice"},
    "cta_pattern": {"voice"},
    "tag_strategy": {"voice"},
    "unknown_visual": {"visual"},
    "must_keep": {"guardrail"},
    "avoid": {"guardrail"},
}
APPLICABILITY = {
    "creator_understanding", "topic_selection", "commercial_route",
    "commercial_outline", "publication_copy", "review", "archive_learning",
}
MULTI_NOTE_TYPES = {
    "content_pillar", "core_belief", "mental_model", "value_stance",
    "content_series", "title_formula", "opening_pattern", "body_structure",
    "emotional_arc", "language_dna", "cta_pattern", "tag_strategy",
    "commercial_integration", "commercial_difference", "must_keep", "avoid",
}


class BaselineCandidateError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, value: str, length: int = 16) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def build_evidence(
    creator_id: str,
    run_id: str,
    profile: dict[str, Any],
    notes: list[dict[str, Any]],
    analysis: dict[str, Any],
    captured_at: str,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = [{
        "schema_version": 1,
        "evidence_id": stable_id("ev", f"profile:{creator_id}:{profile['account_id']}"),
        "creator_id": creator_id,
        "kind": "profile",
        "source_id": profile["account_id"],
        "captured_at": captured_at,
        "published_at": None,
        "content_excerpt": profile.get("description") or None,
        "metrics": {
            "followers": profile.get("followers", 0),
            "following": profile.get("following", 0),
            "received_interactions": profile.get("received_interactions", 0),
        },
        "source_ref": None,
        "quality": "complete",
    }, {
        "schema_version": 1,
        "evidence_id": stable_id("ev", f"collection-quality:{creator_id}:{run_id}"),
        "creator_id": creator_id,
        "kind": "collection_quality",
        "source_id": run_id,
        "captured_at": captured_at,
        "published_at": None,
        "content_excerpt": "本次采集不包含图片像素、视频画面、镜头或音频转写。",
        "metrics": {
            "sample_count": analysis["sample_count"],
            "detail_success_rate": analysis["distillation_gate"]["detail_success_rate"],
            "content_completeness": analysis["distillation_gate"]["content_completeness"],
        },
        "source_ref": None,
        "quality": "complete",
    }]
    for note in notes:
        note_id = note["note_id"]
        note_evidence_id = stable_id("ev", f"note:{creator_id}:{note_id}")
        evidence.append({
            "schema_version": 1,
            "evidence_id": note_evidence_id,
            "creator_id": creator_id,
            "kind": "note",
            "source_id": note_id,
            "captured_at": captured_at,
            "published_at": note.get("published_at"),
            "content_excerpt": "\n".join(
                part for part in (note.get("title", ""), note.get("desc", "")) if part
            )[:1000] or None,
            "metrics": note.get("metrics", {}),
            "source_ref": None,
            "quality": note.get("quality", "partial"),
        })
        for position, comment in enumerate(note.get("comments", []), start=1):
            content = str(comment.get("content") or comment.get("text") or "").strip()
            if not content:
                continue
            evidence.append({
                "schema_version": 1,
                "evidence_id": stable_id("ev", f"comment:{creator_id}:{note_id}:{position}:{content}"),
                "creator_id": creator_id,
                "kind": "comment",
                "source_id": f"{note_id}:comment:{position}",
                "captured_at": captured_at,
                "published_at": None,
                "content_excerpt": f"{comment.get('speaker', '读者')}：{content}"[:1000],
                "metrics": {},
                "source_ref": note_evidence_id,
                "quality": "complete",
            })
    return evidence


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BaselineCandidateError(f"{label} 必须是非空字符串")
    return value.strip()


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    missing = expected - value.keys()
    unknown = value.keys() - expected
    if missing:
        raise BaselineCandidateError(f"{label} 缺少字段：{sorted(missing)[0]}")
    if unknown:
        raise BaselineCandidateError(f"{label} 含未知字段：{sorted(unknown)[0]}")


def validate_candidate(
    candidate: dict[str, Any],
    *,
    creator_id: str,
    run_id: str,
    evidence: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(candidate, dict):
        raise BaselineCandidateError("Baseline candidate 必须是 JSON 对象")
    if candidate.get("schema_version") != 1:
        raise BaselineCandidateError("Baseline candidate schema_version 必须为 1")
    _require_exact_keys(
        candidate,
        {"schema_version", "creator_id", "run_id", "summary", "findings", "missing_dimensions", "human_review_questions", "limitations"},
        "candidate",
    )
    if candidate.get("creator_id") != creator_id or candidate.get("run_id") != run_id:
        raise BaselineCandidateError("candidate 的 creator_id 或 run_id 与蒸馏任务不匹配")
    summary = candidate.get("summary")
    if not isinstance(summary, dict):
        raise BaselineCandidateError("candidate.summary 必须是对象")
    required_summary = ("one_line_positioning", "audience", "content_identity", "commercial_identity")
    _require_exact_keys(summary, set(required_summary), "candidate.summary")
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    if any(item.get("creator_id") != creator_id for item in evidence):
        raise BaselineCandidateError("Evidence 中存在不属于当前 Creator 的条目")
    normalized_summary = {}
    for key in required_summary:
        item = summary.get(key)
        if not isinstance(item, dict):
            raise BaselineCandidateError(f"summary.{key} 必须是对象")
        _require_exact_keys(item, {"statement", "evidence_refs", "limitations"}, f"summary.{key}")
        statement = _require_string(item.get("statement"), f"summary.{key}.statement")
        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
            raise BaselineCandidateError(f"summary.{key} 必须引用 Evidence ID")
        refs = list(dict.fromkeys(refs))
        if any(ref not in evidence_by_id for ref in refs):
            raise BaselineCandidateError(f"summary.{key} 引用了不存在的 Evidence")
        minimum_notes = 3 if key in ("one_line_positioning", "content_identity") else 1
        note_sources = {
            evidence_by_id[ref]["source_id"] for ref in refs
            if evidence_by_id[ref]["kind"] == "note"
        }
        if len(note_sources) < minimum_notes:
            raise BaselineCandidateError(f"summary.{key} 至少需要 {minimum_notes} 篇不同笔记 Evidence")
        if key == "commercial_identity" and analysis["segments"]["commercial_candidates"]["count"]:
            commercial_ids = set(analysis["segments"]["commercial_candidates"]["note_ids"])
            if not note_sources.intersection(commercial_ids):
                raise BaselineCandidateError("summary.commercial_identity 必须引用商业候选笔记 Evidence")
        limitations = item.get("limitations", [])
        if not isinstance(limitations, list) or not all(isinstance(value, str) and value.strip() for value in limitations):
            raise BaselineCandidateError(f"summary.{key}.limitations 必须是字符串数组")
        normalized_summary[key] = {
            "statement": statement,
            "evidence_refs": refs,
            "limitations": [value.strip() for value in limitations],
        }

    findings = candidate.get("findings")
    if not isinstance(findings, list) or not findings:
        raise BaselineCandidateError("candidate.findings 至少需要一条结论")
    sample_count = int(analysis.get("sample_count", 0))
    sample_cap = 0.9 if sample_count >= 50 else 0.8 if sample_count >= 20 else 0.65
    normalized_findings = []
    validation_notes = []
    statements: set[str] = set()
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            raise BaselineCandidateError(f"finding #{index} 必须是对象")
        _require_exact_keys(
            finding,
            {"category", "finding_type", "statement", "epistemic_status", "confidence", "evidence_refs", "counter_evidence_refs", "applicable_to", "limitations"},
            f"finding #{index}",
        )
        category = finding.get("category")
        finding_type = finding.get("finding_type")
        if category not in CATEGORIES:
            raise BaselineCandidateError(f"finding #{index} category 不受支持：{category}")
        if finding_type not in FINDING_TYPES:
            raise BaselineCandidateError(f"finding #{index} finding_type 不受支持：{finding_type}")
        if category not in FINDING_CATEGORIES[finding_type]:
            raise BaselineCandidateError(
                f"finding #{index} 的 {finding_type} 不能归入 {category}"
            )
        statement = _require_string(finding.get("statement"), f"finding #{index}.statement")
        if statement in statements:
            raise BaselineCandidateError(f"finding #{index} 与前面的结论重复")
        statements.add(statement)
        epistemic_status = finding.get("epistemic_status")
        if epistemic_status not in ("observed", "inferred"):
            raise BaselineCandidateError(f"finding #{index} 只能标记 observed 或 inferred")
        try:
            confidence = float(finding.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise BaselineCandidateError(f"finding #{index}.confidence 必须是数字") from exc
        if not 0 <= confidence <= 1:
            raise BaselineCandidateError(f"finding #{index}.confidence 必须在 0 到 1 之间")

        refs = finding.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
            raise BaselineCandidateError(f"finding #{index} 必须引用 Evidence ID")
        refs = list(dict.fromkeys(refs))
        unknown = [ref for ref in refs if ref not in evidence_by_id]
        if unknown:
            raise BaselineCandidateError(f"finding #{index} 引用了不存在的 Evidence：{unknown[0]}")
        note_sources = {
            evidence_by_id[ref]["source_id"]
            for ref in refs if evidence_by_id[ref]["kind"] == "note"
        }
        minimum_notes = 3 if finding_type == "core_belief" else 2 if finding_type in MULTI_NOTE_TYPES else 1
        if finding_type == "viewpoint_tension":
            minimum_notes = 2
        elif finding_type == "unknown_visual":
            minimum_notes = 0
        if len(note_sources) < minimum_notes:
            raise BaselineCandidateError(
                f"finding #{index}（{finding_type}）至少需要 {minimum_notes} 篇不同笔记 Evidence"
            )
        if finding_type == "unknown_visual" and not any(
            evidence_by_id[ref]["kind"] == "collection_quality" for ref in refs
        ):
            raise BaselineCandidateError(
                f"finding #{index} unknown_visual 必须引用 collection_quality Evidence"
            )
        if category == "commercial":
            commercial_ids = set(analysis["segments"]["commercial_candidates"]["note_ids"])
            if not note_sources.intersection(commercial_ids):
                raise BaselineCandidateError(f"finding #{index} 必须引用至少一篇商业候选笔记")
            if finding_type == "commercial_difference":
                organic_ids = set(analysis["segments"]["organic"]["note_ids"])
                if not note_sources.intersection(organic_ids):
                    raise BaselineCandidateError(
                        f"finding #{index} commercial_difference 必须同时引用自然内容 Evidence"
                    )

        counter_refs = finding.get("counter_evidence_refs", [])
        if not isinstance(counter_refs, list) or not all(isinstance(ref, str) for ref in counter_refs):
            raise BaselineCandidateError(f"finding #{index}.counter_evidence_refs 必须是数组")
        unknown_counter = [ref for ref in counter_refs if ref not in evidence_by_id]
        if unknown_counter:
            raise BaselineCandidateError(f"finding #{index} 引用了不存在的反证 Evidence")
        applicable_to = finding.get("applicable_to", [])
        if not isinstance(applicable_to, list) or any(item not in APPLICABILITY for item in applicable_to):
            raise BaselineCandidateError(f"finding #{index}.applicable_to 含不支持的场景")
        limitations = finding.get("limitations", [])
        if not isinstance(limitations, list) or not all(isinstance(item, str) and item.strip() for item in limitations):
            raise BaselineCandidateError(f"finding #{index}.limitations 必须是非空字符串数组")

        effective_cap = sample_cap
        if epistemic_status == "inferred":
            effective_cap = min(effective_cap, 0.85)
        if category == "commercial" and analysis["segments"]["commercial_detection"].endswith("requires_human_confirmation"):
            effective_cap = min(effective_cap, 0.65)
        adjusted = round(min(confidence, effective_cap), 2)
        if adjusted != confidence:
            validation_notes.append(f"finding #{index} 置信度由 {confidence} 限制为 {adjusted}")
        normalized_findings.append({
            "category": category,
            "finding_type": finding_type,
            "statement": statement,
            "epistemic_status": epistemic_status,
            "confidence": adjusted,
            "evidence_refs": refs,
            "counter_evidence_refs": list(dict.fromkeys(counter_refs)),
            "applicable_to": list(dict.fromkeys(applicable_to)),
            "limitations": [item.strip() for item in limitations],
        })

    if not any(item["finding_type"] == "unknown_visual" for item in normalized_findings):
        raise BaselineCandidateError("当前没有媒体 Evidence，candidate 必须明确加入 unknown_visual")

    for field in ("missing_dimensions", "human_review_questions", "limitations"):
        value = candidate.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise BaselineCandidateError(f"candidate.{field} 必须是非空字符串数组")

    normalized = {
        "schema_version": 1,
        "creator_id": creator_id,
        "run_id": run_id,
        "summary": normalized_summary,
        "findings": normalized_findings,
        "missing_dimensions": [item.strip() for item in candidate.get("missing_dimensions", [])],
        "human_review_questions": [item.strip() for item in candidate.get("human_review_questions", [])],
        "limitations": [item.strip() for item in candidate.get("limitations", [])],
    }
    return normalized, validation_notes


def build_baseline(
    creator_id: str,
    run_id: str,
    candidate: dict[str, Any],
    analysis: dict[str, Any],
    *,
    version: int,
    created_at: str,
    validation_notes: list[str],
) -> dict[str, Any]:
    claims = []
    sections = {category: [] for category in sorted(CATEGORIES)}
    for position, finding in enumerate(candidate["findings"], start=1):
        claim_id = stable_id(
            "claim",
            f"{creator_id}:{version}:{position}:{finding['finding_type']}:{finding['statement']}",
        )
        sections[finding["category"]].append(claim_id)
        claims.append({
            "claim_id": claim_id,
            **finding,
            "evidence_refs": [{"evidence_id": ref, "note": None} for ref in finding["evidence_refs"]],
            "counter_evidence_refs": [
                {"evidence_id": ref, "note": None} for ref in finding["counter_evidence_refs"]
            ],
        })
    cadence = analysis["cadence"]
    return {
        "schema_version": 1,
        "baseline_id": f"baseline_{creator_id.removeprefix('creator_')}_v{version}",
        "creator_id": creator_id,
        "source_run_id": run_id,
        "version": version,
        "review_status": "pending_confirmation",
        "sample_window": {
            "captured_at": created_at,
            "sample_count": analysis["sample_count"],
            "oldest_published_at": cadence["oldest_published_at"],
            "newest_published_at": cadence["newest_published_at"],
        },
        "summary": {
            key: {
                **value,
                "evidence_refs": [
                    {"evidence_id": ref, "note": None} for ref in value["evidence_refs"]
                ],
            }
            for key, value in candidate["summary"].items()
        },
        "sections": sections,
        "claims": claims,
        "missing_dimensions": candidate["missing_dimensions"],
        "human_review_questions": candidate["human_review_questions"],
        "limitations": list(dict.fromkeys(analysis["limitations"] + candidate["limitations"])),
        "validation_notes": validation_notes,
        "source_candidate_ids": [],
        "created_at": created_at,
    }
