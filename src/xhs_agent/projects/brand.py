from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..creator.baseline import utc_now
from ..storage import file_sha256, new_id, next_object_version, read_json, write_json_atomic
from .service import (
    WorkflowError, WorkflowResult, _active_brief, _candidate_for_run,
    _find_baseline, _find_confirmed_playbook, _finish_task_run, _mask_evidence,
    _project_root, _run, _strings,
)
from .extractors import extract_document


TRACK_DIRS = {"outline": "outlines", "publication_copy": "publication-copy"}


def _source_object(root: Path, track: str, object_id: str) -> tuple[Path, dict[str, Any]]:
    directory = TRACK_DIRS.get(track)
    if not directory:
        raise WorkflowError("track 只能是 outline 或 publication_copy")
    path = root / directory / f"{object_id}.json"
    value = read_json(path)
    if not isinstance(value, dict):
        raise WorkflowError(f"找不到 {track} 对象：{object_id}")
    return path, value


def _clean_delivery(track: str, source: dict[str, Any]) -> dict[str, Any]:
    if track == "outline":
        return {
            "working_titles": source.get("working_titles", []),
            "hooks": source.get("hooks", []),
            "target_duration_seconds": source.get("target_duration_seconds"),
            "estimated_duration_seconds": source.get("estimated_duration_seconds"),
            "sections": source.get("sections", []),
            "shot_rows": source.get("shot_rows", []),
            "brief_coverage": source.get("brief_coverage", []),
        }
    return {
        "title_options": source.get("title_options", []),
        "body": source.get("body", ""),
        "tags": source.get("tags", []),
        "brief_coverage": source.get("brief_coverage", []),
    }


def create_submission(
    state: Path,
    project_id: str,
    *,
    track: str,
    source_object_id: str,
    source_file: Path | None = None,
) -> WorkflowResult:
    root = _project_root(state, project_id)
    _path, source = _source_object(root, track, source_object_id)
    submissions = root / "brand" / track / "submissions"
    round_number = len(list(submissions.glob("*.json"))) + 1
    file_ref = None
    if source_file:
        source_file = source_file.resolve()
        if not source_file.is_file():
            raise WorkflowError("实际提交文件不存在")
        digest = file_sha256(source_file)
        stored = root / "brand" / track / "source" / f"{digest[:12]}-{source_file.name}"
        stored.parent.mkdir(parents=True, exist_ok=True)
        if not stored.exists():
            shutil.copy2(source_file, stored)
        file_ref = {"path": str(stored.relative_to(state)), "sha256": digest, "media_type": None, "original_name": source_file.name}
    submitted_content = _clean_delivery(track, source)
    if source_file:
        _media, actual_text, _blocks, actual_warnings = extract_document(source_file)
        submitted_content["actual_file_text"] = actual_text
        submitted_content["actual_file_warnings"] = actual_warnings
    value = {
        "schema_version": 1, "submission_id": new_id("submission"), "project_id": project_id,
        "track": track, "round": round_number, "source_object_id": source_object_id,
        "submitted_content": submitted_content, "source_file": file_ref,
        "submitted_at": utc_now(), "corrects_submission_id": None,
    }
    path = submissions / f"{value['submission_id']}.json"
    write_json_atomic(path, value)
    project = read_json(root / "project.json")
    project["workflow_state"]["outline" if track == "outline" else "publication_copy"] = "brand_review"
    project["updated_at"] = utc_now(); write_json_atomic(root / "project.json", project)
    return WorkflowResult(value, path)


def prepare_brand_feedback(state: Path, project_id: str, submission_id: str, raw_text: str) -> WorkflowResult:
    root = _project_root(state, project_id)
    matches = list((root / "brand").glob(f"*/submissions/{submission_id}.json"))
    if len(matches) != 1:
        raise WorkflowError(f"找不到唯一 Submission：{submission_id}")
    if not raw_text.strip():
        raise WorkflowError("品牌反馈不能为空")
    submission = read_json(matches[0]); track = submission["track"]
    run, run_path = _run(state, "brand.feedback", {"project_id": project_id, "submission_id": submission_id, "track": track}, ["save_raw_feedback", "ai_structure_feedback", "validate_feedback"])
    run_dir = root / "runs" / run["run_id"]
    raw_path = run_dir / "brand-feedback.txt"; raw_path.parent.mkdir(parents=True, exist_ok=True); raw_path.write_text(raw_text.strip() + "\n", encoding="utf-8")
    task_path = run_dir / "feedback-task.json"; candidate = run_dir / "feedback-candidate.json"
    task = {
        "schema_version": 1, "task_type": "brand_feedback", "run_id": run["run_id"], "project_id": project_id,
        "protocol": "references/brand-review.md", "inputs": {"submission_path": str(matches[0]), "raw_feedback_path": str(raw_path)},
        "candidate_output": str(candidate),
        "candidate_schema": "schemas/v1/brand-feedback-candidate.schema.json",
        "instructions": ["逐条保留品牌原意，不扩写新要求", "标记 clear、ambiguous 或 creator_conflict", "只有确实无需确认的意见可标 clear"],
    }
    write_json_atomic(task_path, task); _finish_task_run(run, run_path, task_path, candidate, project_id=project_id, submission_id=submission_id, raw_feedback_path=str(raw_path))
    return WorkflowResult(task, task_path, run, task_path)


def finalize_brand_feedback(state: Path, run_id: str, candidate_path: Path) -> WorkflowResult:
    run, run_path, candidate = _candidate_for_run(state, run_id, candidate_path, "brand.feedback")
    project_id = run["inputs"]["project_id"]; root = _project_root(state, project_id)
    items = candidate.get("items")
    if candidate.get("schema_version") != 1 or not isinstance(items, list) or not items:
        raise WorkflowError("反馈 candidate 必须包含非空 items")
    normalized = []
    for item in items:
        if item.get("type") not in {"structure", "selling_point", "wording", "compliance", "creator_fit", "other"}:
            raise WorkflowError("反馈 type 不受支持")
        if item.get("understanding") not in {"clear", "ambiguous", "creator_conflict"} or not str(item.get("request", "")).strip():
            raise WorkflowError("反馈必须有 request 和有效 understanding")
        normalized.append({"item_id": new_id("fitem"), "location": item.get("location"), "request": str(item["request"]).strip(), "type": item["type"], "understanding": item["understanding"], "resolution_status": "pending" if item["understanding"] == "clear" else "needs_confirmation", "resolution_note": None})
    feedback = {
        "schema_version": 1, "feedback_id": new_id("feedback"), "project_id": project_id,
        "submission_id": run["inputs"]["submission_id"], "raw_sources": [Path(run["outputs"]["raw_feedback_path"]).read_text(encoding="utf-8").strip()],
        "items": normalized, "received_at": utc_now(),
    }
    path = root / "brand" / run["inputs"]["track"] / "feedback" / f"{feedback['feedback_id']}.json"
    write_json_atomic(path, feedback)
    run["steps"][1]["status"] = "completed"; run["steps"][-1]["status"] = "completed"; run["status"] = "waiting_for_user" if any(item["understanding"] != "clear" for item in normalized) else "completed"; run["outputs"].update({"feedback_id": feedback["feedback_id"], "feedback_path": str(path)}); run["updated_at"] = utc_now(); write_json_atomic(run_path, run)
    return WorkflowResult(feedback, path, run)


def approve_submission(state: Path, project_id: str, submission_id: str, *, note: str | None = None, confirmation_source: str | None = None) -> WorkflowResult:
    root = _project_root(state, project_id); matches = list((root / "brand").glob(f"*/submissions/{submission_id}.json"))
    if len(matches) != 1: raise WorkflowError(f"找不到唯一 Submission：{submission_id}")
    submission = read_json(matches[0]); track = submission["track"]
    existing = list((root / "brand" / track / "approvals").glob("*.json"))
    if existing: raise WorkflowError(f"{track} 已经存在 Approval；不可被后续草稿覆盖")
    value = {"schema_version": 1, "approval_id": new_id("approval"), "project_id": project_id, "submission_id": submission_id, "track": track, "approved_at": utc_now(), "confirmation_source": confirmation_source, "note": note}
    path = root / "brand" / track / "approvals" / f"{value['approval_id']}.json"; write_json_atomic(path, value)
    project = read_json(root / "project.json"); state_key = "outline" if track == "outline" else "publication_copy"; project["workflow_state"][state_key] = "approved"
    if track == "outline": project["workflow_state"]["creator_production"] = "in_progress"
    project["updated_at"] = utc_now(); write_json_atomic(root / "project.json", project)
    return WorkflowResult(value, path)


def _approved_outline(root: Path) -> tuple[dict[str, Any], Path]:
    approvals = list((root / "brand" / "outline" / "approvals").glob("*.json"))
    if len(approvals) != 1: raise WorkflowError("生成发布文案前必须先确认一版大纲 Submission")
    approval = read_json(approvals[0]); submission = read_json(root / "brand" / "outline" / "submissions" / f"{approval['submission_id']}.json")
    outline_path = root / "outlines" / f"{submission['source_object_id']}.json"; outline = read_json(outline_path)
    if not isinstance(outline, dict): raise WorkflowError("Approved Outline 源对象已损坏")
    return outline, outline_path


def prepare_publication_copy(state: Path, project_id: str, *, feedback_id: str | None = None) -> WorkflowResult:
    root = _project_root(state, project_id); project = read_json(root / "project.json"); brief_path, _ = _active_brief(root); _baseline_path, baseline = _find_baseline(state, project["baseline_id"]); _outline, outline_path = _approved_outline(root)
    _playbook_path, playbook = _find_confirmed_playbook(state, project["baseline_id"])
    if project.get("playbook_id"):
        matches = list((state / "creators").glob(f"*/playbooks/{project['playbook_id']}.json"))
        if len(matches) != 1:
            raise WorkflowError("Project 绑定的 Creator Playbook 已不存在")
        playbook = read_json(matches[0])
    excluded = {str(value).strip() for value in project.get("backtest_excluded_evidence_ids", []) if str(value).strip()}
    run, run_path = _run(state, "copy.generate", {"project_id": project_id, "feedback_id": feedback_id, "excluded_evidence_ids": sorted(excluded)}, ["load_approved_context", "ai_generate_copy", "validate_and_version"])
    run_dir = root / "runs" / run["run_id"]; task_path = run_dir / "copy-task.json"; candidate = run_dir / "copy-candidate.json"
    context_path = run_dir / "creator-context.json"
    context = {
        "schema_version": 1,
        "baseline": _mask_evidence(baseline, excluded),
        "playbook": _mask_evidence(playbook, excluded) if playbook else None,
        "backtest": {"excluded_evidence_ids": sorted(excluded), "reason": "防止已发布案例答案泄漏"} if excluded else None,
    }
    write_json_atomic(context_path, context)
    feedback_path = None
    if feedback_id:
        candidates = [
            root / "feedback" / f"{feedback_id}.json",
            root / "brand" / "publication_copy" / "feedback" / f"{feedback_id}.json",
        ]
        feedback_path = next((path for path in candidates if path.is_file()), None)
        if feedback_path is None: raise WorkflowError(f"找不到 Publication Copy Feedback：{feedback_id}")
    task = {"schema_version": 1, "task_type": "publication_copy", "run_id": run["run_id"], "project_id": project_id, "protocol": "references/brand-review.md", "inputs": {"approved_outline_path": str(outline_path), "brief_path": str(brief_path), "creator_context_path": str(context_path), "feedback_path": str(feedback_path) if feedback_path else None}, "candidate_output": str(candidate), "candidate_schema": "schemas/v1/publication-copy-candidate.schema.json", "instructions": ["输出标题候选、完整小红书正文和 Tags", "正文是发布配文，不复述完整逐镜头口播；以个人状态、产品使用场景和必要卖点组成可读文案", "逐项检查 must_include、forbidden、活动信息与必带Tags", "同时使用已确认 Baseline 与 Creator Playbook；只能读取 creator_context_path 中未排除的证据", "回测排除项、历史最终标题、最终发布正文和Tags不得用于生成、复述或补全候选", "不要生成博主最终口播脚本"]}
    write_json_atomic(task_path, task); _finish_task_run(run, run_path, task_path, candidate, project_id=project_id)
    return WorkflowResult(task, task_path, run, task_path)


def record_publication_copy_feedback(state: Path, project_id: str, copy_id: str, text: str) -> WorkflowResult:
    root = _project_root(state, project_id)
    if not (root / "publication-copy" / f"{copy_id}.json").is_file():
        raise WorkflowError("反馈目标 Publication Copy 不存在")
    if not text.strip():
        raise WorkflowError("反馈不能为空")
    value = {
        "schema_version": 1,
        "feedback_id": new_id("ifeedback"),
        "project_id": project_id,
        "target_type": "publication_copy",
        "target_id": copy_id,
        "raw_feedback": text.strip(),
        "created_at": utc_now(),
    }
    path = root / "feedback" / f"{value['feedback_id']}.json"
    write_json_atomic(path, value)
    return WorkflowResult(value, path)


def finalize_publication_copy(state: Path, run_id: str, candidate_path: Path) -> WorkflowResult:
    run, run_path, candidate = _candidate_for_run(state, run_id, candidate_path, "copy.generate")
    project_id = run["inputs"]["project_id"]; root = _project_root(state, project_id); outline, _ = _approved_outline(root)
    if candidate.get("schema_version") != 1 or not str(candidate.get("body", "")).strip(): raise WorkflowError("发布文案 candidate 缺少 body")
    version = next_object_version(root / "publication-copy")
    value = {"schema_version": 1, "copy_id": new_id("copy"), "project_id": project_id, "version": version, "approved_outline_id": outline["outline_id"], "title_options": _strings(candidate.get("title_options", []), "title_options"), "body": candidate["body"].strip(), "tags": _strings(candidate.get("tags", []), "tags"), "brief_coverage": _strings(candidate.get("brief_coverage", []), "brief_coverage"), "risks": _strings(candidate.get("risks", []), "risks"), "created_from_feedback_id": run["inputs"].get("feedback_id"), "created_at": utc_now()}
    path = root / "publication-copy" / f"{value['copy_id']}.json"; write_json_atomic(path, value)
    project = read_json(root / "project.json"); project["workflow_state"]["publication_copy"] = "drafting"; project["updated_at"] = utc_now(); write_json_atomic(root / "project.json", project)
    run["steps"][1]["status"] = "completed"; run["steps"][-1]["status"] = "completed"; run["status"] = "completed"; run["outputs"].update({"copy_id": value["copy_id"], "copy_version": version, "copy_path": str(path)}); run["updated_at"] = utc_now(); write_json_atomic(run_path, run)
    return WorkflowResult(value, path, run)
