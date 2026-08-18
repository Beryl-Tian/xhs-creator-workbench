from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..storage import (
    new_id,
    next_baseline_version,
    read_json,
    register_creator,
    update_registry_with_baseline,
    write_json_atomic,
)
from .analyzer import analyze_creator
from .baseline import (
    BaselineCandidateError,
    build_baseline,
    build_evidence,
    stable_id,
    utc_now,
    validate_candidate,
)
from .collector import CollectionOptions, CreatorSource, collect_creator
from .distillation import build_distillation_task


@dataclass(frozen=True)
class AnalyzeResult:
    run: dict[str, Any]
    creator: dict[str, Any]
    analysis: dict[str, Any]
    evidence_count: int
    creator_root: Path
    task_path: Path


@dataclass(frozen=True)
class FinalizeResult:
    run: dict[str, Any]
    baseline: dict[str, Any]
    baseline_path: Path


@dataclass(frozen=True)
class RevisionResult:
    run: dict[str, Any]
    analysis: dict[str, Any]
    confirmation_path: Path
    task_path: Path


def prepare_commercial_revision(
    state: Path,
    source_run_id: str,
    commercial_note_ids: list[str],
    *,
    note: str | None = None,
) -> RevisionResult:
    """Create an immutable Baseline revision run from human-confirmed labels."""
    source_run = read_json(state / "runs" / f"{source_run_id}.json")
    if not isinstance(source_run, dict) or source_run.get("run_id") != source_run_id:
        raise ValueError(f"找不到来源 Run：{source_run_id}")
    source_outputs = source_run.get("outputs", {})
    creator_id = str(source_outputs.get("creator_id") or "")
    if not creator_id:
        raise ValueError("来源 Run 缺少 creator_id")
    creator_root = state / "creators" / creator_id
    original_root = creator_root / "source" / "runs" / source_run_id
    profile = read_json(original_root / "profile.json")
    notes = read_json(original_root / "notes.json")
    original_analysis = read_json(Path(str(source_outputs.get("analysis_path", ""))))
    evidence = read_json(Path(str(source_outputs.get("evidence_path", ""))))
    if not isinstance(profile, dict) or not isinstance(notes, list):
        raise ValueError("来源 Run 缺少 profile 或 notes")
    if not isinstance(original_analysis, dict) or not isinstance(evidence, list):
        raise ValueError("来源 Run 缺少 analysis 或 Evidence")
    confirmed_ids = list(dict.fromkeys(commercial_note_ids))
    if not confirmed_ids:
        raise ValueError("至少需要确认一篇商业笔记")

    analysis = analyze_creator(
        notes,
        original_analysis.get("quality", {}),
        commercial_note_ids=set(confirmed_ids),
    )
    created_at = utc_now()
    run_id = new_id("run")
    revision_root = creator_root / "source" / "runs" / run_id
    notes_path = revision_root / "notes.json"
    analysis_path = revision_root / "analysis.json"
    evidence_path = creator_root / "evidence" / f"{run_id}.json"
    confirmation_path = revision_root / "commercial-confirmation.json"
    task_path = revision_root / "distillation-task.json"
    confirmation = {
        "schema_version": 1,
        "confirmation_id": new_id("cconfirm"),
        "creator_id": creator_id,
        "source_run_id": source_run_id,
        "revision_run_id": run_id,
        "commercial_note_ids": confirmed_ids,
        "organic_note_ids": analysis["segments"]["organic"]["note_ids"],
        "note": note.strip() if note else None,
        "confirmed_at": created_at,
    }
    task = build_distillation_task(
        creator_id=creator_id,
        run_id=run_id,
        profile=profile,
        analysis=analysis,
        evidence=evidence,
        notes_path=notes_path,
        evidence_path=evidence_path,
        protocol_path="references/creator-baseline-distillation.md",
    )
    run = {
        "schema_version": 1,
        "run_id": run_id,
        "operation": "creator.baseline.revise",
        "status": "waiting_for_agent" if task["status"] == "ready" else "waiting_for_user",
        "inputs": {
            "source_run_id": source_run_id,
            "commercial_confirmation_id": confirmation["confirmation_id"],
        },
        "outputs": {
            "creator_id": creator_id,
            "creator_root": str(creator_root),
            "analysis_path": str(analysis_path),
            "evidence_path": str(evidence_path),
            "distillation_task_path": str(task_path),
            "candidate_output_path": task["candidate_output"],
            "distillation_gate": task["status"],
            "evidence_count": len(evidence),
            "commercial_confirmation_path": str(confirmation_path),
        },
        "steps": [
            {"name": "apply_human_commercial_labels", "status": "completed", "error": None},
            {"name": "deterministic_analysis", "status": "completed", "error": None},
            {"name": "prepare_distillation_task", "status": "completed", "error": None},
            {"name": "ai_baseline_distillation", "status": "pending", "error": None},
            {"name": "validate_and_version_baseline", "status": "pending", "error": None},
        ],
        "error_code": None,
        "recovery_hint": None,
        "started_at": created_at,
        "updated_at": created_at,
    }
    write_json_atomic(revision_root / "profile.json", profile)
    write_json_atomic(notes_path, notes)
    write_json_atomic(analysis_path, analysis)
    write_json_atomic(evidence_path, evidence)
    write_json_atomic(confirmation_path, confirmation)
    write_json_atomic(task_path, task)
    write_json_atomic(state / "runs" / f"{run_id}.json", run)
    return RevisionResult(run=run, analysis=analysis, confirmation_path=confirmation_path, task_path=task_path)


def _run_record(run_id: str, account: str, options: CollectionOptions, started_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "operation": "creator.analyze",
        "status": "running",
        "inputs": {
            "account": account,
            "sample_size": options.sample_size,
            "comment_note_limit": options.comment_note_limit,
            "comments_per_note": options.comments_per_note,
        },
        "outputs": {},
        "steps": [
            {"name": "collect_public_data", "status": "running", "error": None},
            {"name": "deterministic_analysis", "status": "pending", "error": None},
            {"name": "prepare_distillation_task", "status": "pending", "error": None},
            {"name": "ai_baseline_distillation", "status": "pending", "error": None},
            {"name": "validate_and_version_baseline", "status": "pending", "error": None},
        ],
        "error_code": None,
        "recovery_hint": None,
        "started_at": started_at,
        "updated_at": started_at,
    }


def analyze_and_store_creator(
    source: CreatorSource,
    account: str,
    options: CollectionOptions,
    state: Path,
) -> AnalyzeResult:
    started_at = utc_now()
    run_id = f"run_{uuid.uuid4().hex[:20]}"
    run_path = state / "runs" / f"{run_id}.json"
    run = _run_record(run_id, account, options, started_at)
    write_json_atomic(run_path, run)
    try:
        collection = collect_creator(source, account, options)
        run["steps"][0]["status"] = "completed"
        run["steps"][1]["status"] = "running"
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)

        analysis = analyze_creator(collection.notes, collection.quality)
        run["steps"][1]["status"] = "completed"
        run["steps"][2]["status"] = "running"
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)

        profile = collection.profile
        creator_id = stable_id("creator", f"xiaohongshu:{profile['account_id']}")
        creator_root = state / "creators" / creator_id
        existing_creator = read_json(creator_root / "creator.json", {})
        creator = {
            "schema_version": 1,
            "creator_id": creator_id,
            "display_name": profile["nickname"],
            "platform_accounts": [{
                "platform": "xiaohongshu",
                "account_id": profile["account_id"],
                "profile_url": None,
            }],
            "is_primary": True,
            "created_at": existing_creator.get("created_at", started_at),
        }
        evidence = build_evidence(
            creator_id, run_id, profile, collection.notes, analysis, started_at
        )
        source_run = creator_root / "source" / "runs" / run_id
        notes_path = source_run / "notes.json"
        analysis_path = source_run / "analysis.json"
        evidence_path = creator_root / "evidence" / f"{run_id}.json"
        task_path = source_run / "distillation-task.json"
        task = build_distillation_task(
            creator_id=creator_id,
            run_id=run_id,
            profile=profile,
            analysis=analysis,
            evidence=evidence,
            notes_path=notes_path,
            evidence_path=evidence_path,
            protocol_path="references/creator-baseline-distillation.md",
        )

        write_json_atomic(creator_root / "creator.json", creator)
        write_json_atomic(source_run / "profile.json", profile)
        write_json_atomic(notes_path, collection.notes)
        write_json_atomic(analysis_path, analysis)
        write_json_atomic(evidence_path, evidence)
        write_json_atomic(task_path, task)
        register_creator(state, creator, updated_at=started_at)

        run["steps"][2]["status"] = "completed"
        run["status"] = (
            "waiting_for_agent" if task["status"] == "ready" else "waiting_for_user"
        )
        run["outputs"] = {
            "creator_id": creator_id,
            "creator_root": str(creator_root),
            "analysis_path": str(analysis_path),
            "evidence_path": str(evidence_path),
            "distillation_task_path": str(task_path),
            "candidate_output_path": task["candidate_output"],
            "distillation_gate": task["status"],
            "evidence_count": len(evidence),
        }
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)
        return AnalyzeResult(
            run=run,
            creator=creator,
            analysis=analysis,
            evidence_count=len(evidence),
            creator_root=creator_root,
            task_path=task_path,
        )
    except Exception as exc:
        for step in run["steps"]:
            if step["status"] == "running":
                step["status"] = "failed"
                step["error"] = str(exc)
                break
        run["status"] = "failed"
        run["error_code"] = "creator_analysis_failed"
        run["recovery_hint"] = "检查账号、TikHub 权限和采集参数后重试；失败 Run 已保留。"
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)
        raise


def finalize_baseline_candidate(state: Path, run_id: str, candidate_path: Path) -> FinalizeResult:
    state = state.resolve()
    candidate_path = candidate_path.resolve()
    if not candidate_path.is_relative_to(state):
        raise BaselineCandidateError("candidate 必须位于私有 .xhs-agent 目录内")
    run_path = state / "runs" / f"{run_id}.json"
    run = read_json(run_path)
    if not isinstance(run, dict) or run.get("run_id") != run_id:
        raise BaselineCandidateError(f"找不到 Run：{run_id}")
    outputs = run.get("outputs", {})
    if outputs.get("distillation_gate") != "ready":
        raise BaselineCandidateError("数据质量闸门未通过，不能生成正式 Baseline candidate")
    creator_id = outputs.get("creator_id")
    creator_root = state / "creators" / str(creator_id)
    creator = read_json(creator_root / "creator.json")
    analysis = read_json(Path(outputs["analysis_path"]))
    evidence = read_json(Path(outputs["evidence_path"]))
    candidate = read_json(candidate_path)
    if not all(isinstance(value, expected) for value, expected in (
        (creator, dict), (analysis, dict), (evidence, list), (candidate, dict)
    )):
        raise BaselineCandidateError("Run 的分析、Evidence 或 candidate 文件无效")

    ai_step = next(step for step in run["steps"] if step["name"] == "ai_baseline_distillation")
    validation_step = next(step for step in run["steps"] if step["name"] == "validate_and_version_baseline")
    ai_step["status"] = "completed"
    ai_step["error"] = None
    validation_step["status"] = "running"
    validation_step["error"] = None
    run["updated_at"] = utc_now()
    write_json_atomic(run_path, run)
    try:
        normalized, validation_notes = validate_candidate(
            candidate,
            creator_id=creator_id,
            run_id=run_id,
            evidence=evidence,
            analysis=analysis,
        )
        version = next_baseline_version(creator_root)
        created_at = utc_now()
        baseline = build_baseline(
            creator_id,
            run_id,
            normalized,
            analysis,
            version=version,
            created_at=created_at,
            validation_notes=validation_notes,
        )
        baseline_path = creator_root / "baselines" / f"{baseline['baseline_id']}.json"
        normalized_path = candidate_path.parent / "baseline-candidate.validated.json"
        write_json_atomic(normalized_path, normalized)
        write_json_atomic(baseline_path, baseline)
        update_registry_with_baseline(state, creator, baseline)
        validation_step["status"] = "completed"
        run["status"] = "completed"
        run["outputs"].update({
            "baseline_id": baseline["baseline_id"],
            "baseline_version": version,
            "baseline_path": str(baseline_path),
            "baseline_review_status": baseline["review_status"],
            "validated_candidate_path": str(normalized_path),
        })
        run["error_code"] = None
        run["recovery_hint"] = None
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)
        return FinalizeResult(run=run, baseline=baseline, baseline_path=baseline_path)
    except (BaselineCandidateError, KeyError, TypeError, ValueError) as exc:
        validation_step["status"] = "failed"
        validation_step["error"] = str(exc)
        run["status"] = "waiting_for_agent"
        run["error_code"] = "baseline_candidate_invalid"
        run["recovery_hint"] = "按 distillation protocol 修订 candidate JSON 后重新执行 finalize。"
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)
        raise
