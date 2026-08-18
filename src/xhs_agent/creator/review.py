from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..storage import (
    new_id, next_baseline_version, read_json, update_registry_with_baseline,
    write_json_atomic,
)
from .baseline import utc_now


class BaselineReviewError(ValueError):
    pass


@dataclass(frozen=True)
class BaselineReviewResult:
    confirmation: dict[str, Any]
    confirmation_path: Path
    baseline: dict[str, Any]


@dataclass(frozen=True)
class BaselineCalibrationResult:
    calibration: dict[str, Any]
    calibration_path: Path
    baseline: dict[str, Any]
    baseline_path: Path


@dataclass(frozen=True)
class BaselineLongitudinalResult:
    link: dict[str, Any]
    link_path: Path
    baseline: dict[str, Any]
    baseline_path: Path


def attach_longitudinal_analysis(
    state: Path,
    baseline_id: str,
    run_id: str,
) -> BaselineLongitudinalResult:
    matches = list((state / "creators").glob(f"*/baselines/{baseline_id}.json"))
    if len(matches) != 1:
        raise BaselineReviewError(f"找不到唯一 Baseline：{baseline_id}")
    source_path = matches[0]
    source = read_json(source_path)
    if not isinstance(source, dict) or source.get("review_status") not in {
        "pending_confirmation", "confirmed"
    }:
        raise BaselineReviewError("只有待确认或已确认的 Baseline 可以绑定纵向分析")
    run = read_json(state / "runs" / f"{run_id}.json")
    if not isinstance(run, dict) or run.get("run_id") != run_id:
        raise BaselineReviewError(f"找不到纵向分析 Run：{run_id}")
    outputs = run.get("outputs", {})
    if outputs.get("creator_id") != source.get("creator_id"):
        raise BaselineReviewError("纵向分析 Run 不属于当前 Creator")
    analysis = read_json(Path(str(outputs.get("analysis_path", ""))))
    longitudinal = analysis.get("longitudinal") if isinstance(analysis, dict) else None
    if not isinstance(longitudinal, dict) or longitudinal.get("status") != "ready":
        raise BaselineReviewError("纵向分析历史窗口不足，不能绑定为正式时间画像")
    attached_at = utc_now()
    link_id = new_id("blong")
    creator_id = str(source["creator_id"])
    creator_root = source_path.parent.parent
    version = next_baseline_version(creator_root)
    revised = deepcopy(source)
    revised.update({
        "baseline_id": f"baseline_{creator_id.removeprefix('creator_')}_v{version}",
        "version": version,
        "review_status": "pending_confirmation",
        "source_baseline_id": baseline_id,
        "longitudinal_run_id": run_id,
        "source_longitudinal_link_id": link_id,
        "created_at": attached_at,
    })
    revised.pop("confirmed_at", None)
    revised.pop("source_calibration_id", None)
    link = {
        "schema_version": 1,
        "link_id": link_id,
        "creator_id": creator_id,
        "source_baseline_id": baseline_id,
        "result_baseline_id": revised["baseline_id"],
        "longitudinal_run_id": run_id,
        "sample_count": int(analysis.get("sample_count", 0)),
        "dated_note_count": int(longitudinal.get("dated_note_count", 0)),
        "attached_at": attached_at,
    }
    link_path = creator_root / "baseline-longitudinal-links" / f"{link_id}.json"
    baseline_path = source_path.parent / f"{revised['baseline_id']}.json"
    write_json_atomic(link_path, link)
    write_json_atomic(baseline_path, revised)
    source["review_status"] = "superseded"
    write_json_atomic(source_path, source)
    creator = read_json(creator_root / "creator.json")
    if isinstance(creator, dict):
        update_registry_with_baseline(state, creator, revised)
    return BaselineLongitudinalResult(link, link_path, revised, baseline_path)


def calibrate_baseline(
    state: Path,
    baseline_id: str,
    *,
    desired_positioning: str | None = None,
    target_audience: str | None = None,
    commercial_guardrail: str | None = None,
    accepted_question_numbers: list[int] | None = None,
    rejected_question_numbers: list[int] | None = None,
    note: str | None = None,
) -> BaselineCalibrationResult:
    matches = list((state / "creators").glob(f"*/baselines/{baseline_id}.json"))
    if len(matches) != 1:
        raise BaselineReviewError(f"找不到唯一 Baseline：{baseline_id}")
    source_path = matches[0]
    source = read_json(source_path)
    if not isinstance(source, dict) or source.get("review_status") not in {
        "pending_confirmation", "confirmed"
    }:
        raise BaselineReviewError("只有待确认或已确认的 Baseline 可以创建校准版本")
    desired_positioning = desired_positioning.strip() if desired_positioning else None
    target_audience = target_audience.strip() if target_audience else None
    commercial_guardrail = commercial_guardrail.strip() if commercial_guardrail else None
    questions = list(source.get("human_review_questions", []))
    accepted_numbers = sorted(set(accepted_question_numbers or []))
    rejected_numbers = sorted(set(rejected_question_numbers or []))
    if set(accepted_numbers).intersection(rejected_numbers):
        raise BaselineReviewError("同一个问题不能同时确认和否定")
    resolved_numbers = sorted(set(accepted_numbers + rejected_numbers))
    if any(number < 1 or number > len(questions) for number in resolved_numbers):
        raise BaselineReviewError("确认问题序号超出当前 Baseline 范围")
    accepted_questions = [questions[number - 1] for number in accepted_numbers]
    rejected_questions = [questions[number - 1] for number in rejected_numbers]
    remaining_questions = [
        question for index, question in enumerate(questions, start=1)
        if index not in resolved_numbers
    ]
    recorded_at = utc_now()
    calibration_id = new_id("bcal")
    creator_id = str(source["creator_id"])
    creator_root = source_path.parent.parent
    version = next_baseline_version(creator_root)
    human_context = list(source.get("human_context", []))
    additions = {
        "desired_positioning": desired_positioning,
        "target_audience": target_audience,
        "commercial_guardrail": commercial_guardrail,
    }
    for context_type, statement in additions.items():
        if not statement:
            continue
        human_context = [item for item in human_context if item.get("context_type") != context_type]
        human_context.append({
            "context_id": new_id("hctx"),
            "context_type": context_type,
            "statement": statement,
            "source": "creator_team",
            "status": "confirmed",
            "applicable_to": ["topic_selection", "commercial_route", "commercial_outline", "publication_copy", "review"],
            "recorded_at": recorded_at,
        })
    context_by_type = {item.get("context_type"): item.get("statement") for item in human_context}
    if not context_by_type.get("desired_positioning") or not context_by_type.get("target_audience"):
        raise BaselineReviewError("首次校准必须提供目标定位和目标受众")
    if not any((desired_positioning, target_audience, commercial_guardrail, resolved_numbers)):
        raise BaselineReviewError("本次校准没有新的目标信息或问题处理结果")
    revised = deepcopy(source)
    revised.update({
        "baseline_id": f"baseline_{creator_id.removeprefix('creator_')}_v{version}",
        "version": version,
        "review_status": "pending_confirmation",
        "human_context": human_context,
        "human_review_questions": remaining_questions,
        "source_baseline_id": baseline_id,
        "source_calibration_id": calibration_id,
        "created_at": recorded_at,
    })
    revised.pop("confirmed_at", None)
    calibration = {
        "schema_version": 1,
        "calibration_id": calibration_id,
        "creator_id": creator_id,
        "source_baseline_id": baseline_id,
        "result_baseline_id": revised["baseline_id"],
        "desired_positioning": context_by_type["desired_positioning"],
        "target_audience": context_by_type["target_audience"],
        "commercial_guardrail": commercial_guardrail,
        "accepted_review_questions": accepted_questions,
        "rejected_review_questions": rejected_questions,
        "remaining_review_questions": remaining_questions,
        "note": note.strip() if note else None,
        "recorded_at": recorded_at,
    }
    calibration_path = creator_root / "baseline-calibrations" / f"{calibration_id}.json"
    baseline_path = source_path.parent / f"{revised['baseline_id']}.json"
    write_json_atomic(calibration_path, calibration)
    write_json_atomic(baseline_path, revised)
    source["review_status"] = "superseded"
    write_json_atomic(source_path, source)
    creator = read_json(creator_root / "creator.json")
    if isinstance(creator, dict):
        update_registry_with_baseline(state, creator, revised)
    return BaselineCalibrationResult(calibration, calibration_path, revised, baseline_path)


def confirm_baseline(state: Path, baseline_id: str, *, note: str | None = None) -> BaselineReviewResult:
    matches = list((state / "creators").glob(f"*/baselines/{baseline_id}.json"))
    if len(matches) != 1:
        raise BaselineReviewError(f"找不到唯一 Baseline：{baseline_id}")
    baseline_path = matches[0]
    baseline = read_json(baseline_path)
    if not isinstance(baseline, dict) or baseline.get("review_status") not in {
        "pending_confirmation", "confirmed"
    }:
        raise BaselineReviewError("只有待确认或已确认的 Baseline 可以登记确认")
    creator_id = str(baseline["creator_id"])
    existing = list((baseline_path.parent.parent / "baseline-confirmations").glob("*.json"))
    for path in existing:
        value = read_json(path, {})
        if value.get("baseline_id") == baseline_id:
            return BaselineReviewResult(value, path, baseline)
    confirmed_at = utc_now()
    confirmation = {
        "schema_version": 1,
        "confirmation_id": new_id("bconf"),
        "baseline_id": baseline_id,
        "creator_id": creator_id,
        "decision": "confirmed",
        "note": note.strip() if note else None,
        "confirmed_at": confirmed_at,
    }
    confirmation_path = (
        baseline_path.parent.parent / "baseline-confirmations" / f"{confirmation['confirmation_id']}.json"
    )
    write_json_atomic(confirmation_path, confirmation)
    baseline["review_status"] = "confirmed"
    baseline["confirmed_at"] = confirmed_at
    write_json_atomic(baseline_path, baseline)

    registry_path = state / "registry.json"
    registry = read_json(registry_path, {"schema_version": 1, "creators": []})
    for item in registry.get("creators", []):
        if item.get("creator_id") == creator_id:
            item["active_baseline_id"] = baseline_id
            item["active_baseline_version"] = baseline.get("version")
            item["updated_at"] = confirmed_at
    write_json_atomic(registry_path, registry)
    return BaselineReviewResult(confirmation, confirmation_path, baseline)
