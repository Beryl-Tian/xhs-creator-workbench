from __future__ import annotations

import shutil
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..creator.baseline import stable_id, utc_now
from ..storage import file_sha256, new_id, read_json, write_json_atomic
from .extractors import extract_document
from .service import WorkflowError, WorkflowResult, _candidate_for_run, _finish_task_run, _project_root, _run, _strings


CHANGE_TYPES = {"added", "removed", "reordered", "weakened", "strengthened"}
CHANGE_SOURCES = {"brand_review", "creator_creation", "shoot_execution", "unknown"}
LEARNING_SCOPES = {"project_only", "brand", "category", "commercial", "organic", "global"}


@dataclass(frozen=True)
class ArchiveResult:
    bundle: dict[str, Any]
    bundle_path: Path
    run: dict[str, Any] | None
    task_path: Path | None


def _approved_submission(root: Path, track: str) -> tuple[dict[str, Any], Path]:
    approvals = list((root / "brand" / track / "approvals").glob("*.json"))
    if len(approvals) != 1:
        label = "Outline" if track == "outline" else "Publication Copy"
        raise WorkflowError(f"完整归档前必须先确认一版 {label} Submission")
    approval = read_json(approvals[0]); path = root / "brand" / track / "submissions" / f"{approval['submission_id']}.json"; submission = read_json(path)
    if not isinstance(submission, dict) or not isinstance(submission.get("submitted_content"), dict): raise WorkflowError(f"Approved {track} Submission 已损坏")
    return submission, path


def _store_source(state: Path, root: Path, source: Path, slot: str) -> tuple[dict[str, Any], str, list[str]]:
    source = source.resolve()
    if not source.is_file(): raise WorkflowError(f"归档文件不存在：{source}")
    digest = file_sha256(source); media, text, _blocks, warnings = extract_document(source)
    stored = root / "archive" / "source" / slot / f"{digest[:12]}-{source.name}"
    stored.parent.mkdir(parents=True, exist_ok=True)
    if not stored.exists(): shutil.copy2(source, stored)
    return {"path": str(stored.relative_to(state)), "sha256": digest, "media_type": media, "original_name": source.name}, text, warnings


def _store_attachment(state: Path, root: Path, source: Path, slot: str) -> dict[str, Any]:
    source = source.resolve()
    if not source.is_file(): raise WorkflowError(f"归档附件不存在：{source}")
    digest = file_sha256(source)
    stored = root / "archive" / "source" / slot / f"{digest[:12]}-{source.name}"
    stored.parent.mkdir(parents=True, exist_ok=True)
    if not stored.exists(): shutil.copy2(source, stored)
    media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    return {"path": str(stored.relative_to(state)), "sha256": digest, "media_type": media_type, "original_name": source.name}


def _evidence(project: dict[str, Any], bundle_id: str, kind: str, text: str, now: str, published_at: str | None) -> dict[str, Any]:
    return {"schema_version": 1, "evidence_id": stable_id("ev", f"{kind}:{project['project_id']}:{bundle_id}"), "creator_id": project["creator_id"], "kind": kind, "source_id": bundle_id, "captured_at": now, "published_at": published_at, "content_excerpt": text[:1000] or None, "metrics": {}, "source_ref": project["project_id"], "quality": "complete"}


def archive_publication(
    state: Path, project_id: str, *, oral_script: Path | None = None,
    published_copy: Path | None = None, published_at: str | None = None,
    published_url: str | None = None, published_copy_screenshot: Path | None = None,
) -> ArchiveResult:
    if oral_script is None and published_copy is None: raise WorkflowError("至少上传最终口播脚本或实际发布配文之一")
    root = _project_root(state, project_id); project = read_json(root / "project.json")
    if published_url and not published_url.startswith(("http://", "https://")):
        raise WorkflowError("published_url 必须是 http 或 https 链接")
    if published_at:
        try:
            from datetime import datetime
            datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise WorkflowError("published_at 必须是 ISO 8601 时间") from exc
    bundle_path = root / "archive" / "bundle.json"
    bundle = read_json(bundle_path, {"schema_version": 1, "bundle_id": new_id("bundle"), "project_id": project_id, "oral_script_source": None, "oral_script": None, "oral_script_warnings": [], "published_copy_source": None, "published_copy_screenshot_source": None, "published_copy_extracted_text": None, "published_copy_warnings": [], "published_title": None, "published_body": None, "published_tags": [], "approved_outline_diff": None, "approved_copy_diff": None, "published_at": None, "published_url": None, "completeness": "partial", "created_at": utc_now(), "updated_at": utc_now()})
    if bundle.get("completeness") == "complete":
        raise WorkflowError("该项目已完成最终归档；不能重复创建差异任务")
    will_have_oral = bool(bundle.get("oral_script") or oral_script)
    will_have_copy = bool(bundle.get("published_copy_extracted_text") or published_copy)
    approved_paths: tuple[Path, Path] | None = None
    if will_have_oral and will_have_copy:
        _outline, outline_path = _approved_submission(root, "outline")
        _copy, copy_path = _approved_submission(root, "publication_copy")
        approved_paths = (outline_path, copy_path)
    if oral_script:
        ref, text, warnings = _store_source(state, root, oral_script, "oral-script")
        if bundle.get("oral_script_source") and bundle["oral_script_source"]["sha256"] != ref["sha256"]: raise WorkflowError("最终口播脚本已归档；不能覆盖原件")
        bundle.update({"oral_script_source": ref, "oral_script": text, "oral_script_warnings": warnings})
    if published_copy:
        ref, text, warnings = _store_source(state, root, published_copy, "published-copy")
        if bundle.get("published_copy_source") and bundle["published_copy_source"]["sha256"] != ref["sha256"]: raise WorkflowError("实际发布配文已归档；不能覆盖原件")
        bundle.update({"published_copy_source": ref, "published_copy_extracted_text": text, "published_copy_warnings": warnings})
    if published_copy_screenshot:
        ref = _store_attachment(state, root, published_copy_screenshot, "published-copy-screenshot")
        if bundle.get("published_copy_screenshot_source") and bundle["published_copy_screenshot_source"]["sha256"] != ref["sha256"]: raise WorkflowError("实际发布配文截图已归档；不能覆盖原件")
        bundle["published_copy_screenshot_source"] = ref
    if published_at: bundle["published_at"] = published_at
    if published_url: bundle["published_url"] = published_url
    bundle["updated_at"] = utc_now(); write_json_atomic(bundle_path, bundle)
    now = utc_now(); evidence = []
    if bundle.get("oral_script"): evidence.append(_evidence(project, bundle["bundle_id"], "oral_script", bundle["oral_script"], now, bundle.get("published_at")))
    if bundle.get("published_copy_extracted_text"): evidence.append(_evidence(project, bundle["bundle_id"], "published_copy", bundle["published_copy_extracted_text"], now, bundle.get("published_at")))
    evidence_path = root / "archive" / "evidence.json"; write_json_atomic(evidence_path, evidence)
    project["workflow_state"]["creator_production"] = "complete" if bundle.get("oral_script") else project["workflow_state"]["creator_production"]
    if bundle.get("published_copy_extracted_text"): project["workflow_state"]["publication"] = "published"
    project["updated_at"] = utc_now(); write_json_atomic(root / "project.json", project)
    if not bundle.get("oral_script") or not bundle.get("published_copy_extracted_text"):
        return ArchiveResult(bundle, bundle_path, None, None)
    assert approved_paths is not None
    outline_path, copy_path = approved_paths
    run, run_path = _run(state, "published.archive", {"project_id": project_id, "bundle_id": bundle["bundle_id"]}, ["preserve_final_sources", "ai_compare_and_distill", "validate_archive"])
    run_dir = root / "runs" / run["run_id"]; task_path = run_dir / "archive-task.json"; candidate = run_dir / "archive-candidate.json"
    task = {"schema_version": 1, "task_type": "final_publication_archive", "run_id": run["run_id"], "project_id": project_id, "protocol": "references/archive-final.md", "inputs": {"bundle_path": str(bundle_path), "approved_outline_submission_path": str(outline_path), "approved_copy_submission_path": str(copy_path), "evidence_path": str(evidence_path)}, "candidate_output": str(candidate), "candidate_schema": "schemas/v1/archive-candidate.schema.json", "instructions": ["以品牌真正确认的 Submission submitted_content 为基准，分别比较 Outline→最终口播和 Copy→实际发布配文", "若 Submission 带 actual_file_text，以它作为品牌收到内容的最高优先级基准", "变化只能标 added、removed、reordered、weakened、strengthened", "来源不确定时必须标 unknown", "候选规律默认 proposed；单项目优先 project_only，不能自动进入 Baseline"]}
    write_json_atomic(task_path, task); _finish_task_run(run, run_path, task_path, candidate, project_id=project_id, bundle_path=str(bundle_path), evidence_path=str(evidence_path))
    return ArchiveResult(bundle, bundle_path, run, task_path)


def _validate_diff(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("summary"), str) or not isinstance(value.get("changes"), list): raise WorkflowError(f"{label} 无效")
    changes = []
    for item in value["changes"]:
        if item.get("type") not in CHANGE_TYPES or item.get("likely_source") not in CHANGE_SOURCES or not str(item.get("description", "")).strip(): raise WorkflowError(f"{label} 含无效变化")
        changes.append({"change_id": new_id("change"), "type": item["type"], "description": item["description"].strip(), "approved_ref": item.get("approved_ref"), "final_ref": item.get("final_ref"), "likely_source": item["likely_source"], "confidence": min(1.0, max(0.0, float(item.get("confidence", 0))))})
    return {"summary": value["summary"].strip(), "changes": changes}


def finalize_archive(state: Path, run_id: str, candidate_path: Path) -> ArchiveResult:
    run, run_path, candidate = _candidate_for_run(state, run_id, candidate_path, "published.archive")
    project_id = run["inputs"]["project_id"]; root = _project_root(state, project_id); project = read_json(root / "project.json")
    bundle_path = Path(run["outputs"]["bundle_path"]); bundle = read_json(bundle_path); evidence = read_json(Path(run["outputs"]["evidence_path"]), [])
    if candidate.get("schema_version") != 1: raise WorkflowError("archive candidate schema_version 必须为 1")
    expected_keys = {"schema_version", "published_copy", "approved_outline_diff", "approved_copy_diff", "learning_candidates"}
    if set(candidate) != expected_keys: raise WorkflowError("archive candidate 字段不完整或含未知字段")
    published = candidate.get("published_copy")
    if not isinstance(published, dict) or not str(published.get("title", "")).strip() or not str(published.get("body", "")).strip(): raise WorkflowError("candidate 必须结构化实际发布标题和正文")
    tags = _strings(published.get("tags", []), "published_copy.tags")
    if not tags: raise WorkflowError("实际发布 Tags 不能为空")
    bundle["published_title"] = published["title"].strip(); bundle["published_body"] = published["body"].strip(); bundle["published_tags"] = tags
    bundle["approved_outline_diff"] = _validate_diff(candidate.get("approved_outline_diff"), "approved_outline_diff")
    bundle["approved_copy_diff"] = _validate_diff(candidate.get("approved_copy_diff"), "approved_copy_diff")
    bundle["completeness"] = "complete"; bundle["updated_at"] = utc_now(); write_json_atomic(bundle_path, bundle)
    allowed = {item["evidence_id"] for item in evidence}; learning = candidate.get("learning_candidates", [])
    if not isinstance(learning, list): raise WorkflowError("learning_candidates 必须是数组")
    learning_ids = []
    for item in learning:
        if item.get("scope") not in LEARNING_SCOPES or not str(item.get("statement", "")).strip() or not str(item.get("reason", "")).strip(): raise WorkflowError("Learning Candidate 字段无效")
        refs = list(dict.fromkeys(_strings(item.get("evidence_refs", []), "learning.evidence_refs")))
        if not refs or any(ref not in allowed for ref in refs): raise WorkflowError("Learning Candidate 必须引用本次归档 Evidence")
        value = {"schema_version": 1, "candidate_id": new_id("learning"), "creator_id": project["creator_id"], "project_id": project_id, "scope": item["scope"], "statement": item["statement"].strip(), "reason": item["reason"].strip(), "evidence_refs": [{"evidence_id": ref, "note": None} for ref in refs], "counter_evidence_refs": [], "confidence": min(0.75, max(0.0, float(item.get("confidence", 0)))), "status": "proposed", "review_note": None, "created_at": utc_now()}
        path = root / "learning" / f"{value['candidate_id']}.json"; write_json_atomic(path, value); learning_ids.append(value["candidate_id"])
    project["workflow_state"].update({"creator_production": "complete", "publication": "published", "archive": "complete"}); project["updated_at"] = utc_now(); write_json_atomic(root / "project.json", project)
    run["steps"][1]["status"] = "completed"; run["steps"][2]["status"] = "completed"; run["status"] = "waiting_for_user" if learning_ids else "completed"; run["outputs"].update({"bundle_id": bundle["bundle_id"], "learning_candidate_ids": learning_ids}); run["updated_at"] = utc_now(); write_json_atomic(run_path, run)
    return ArchiveResult(bundle, bundle_path, run, None)


def review_learning(state: Path, project_id: str, candidate_id: str, decision: str, *, note: str | None = None) -> WorkflowResult:
    if decision not in {"accepted", "rejected"}: raise WorkflowError("decision 只能是 accepted 或 rejected")
    root = _project_root(state, project_id); path = root / "learning" / f"{candidate_id}.json"; candidate = read_json(path)
    if not isinstance(candidate, dict) or candidate.get("status") != "proposed": raise WorkflowError("只可 Review proposed Learning Candidate")
    reviewed_at = utc_now(); review = {"schema_version": 1, "review_id": new_id("lreview"), "project_id": project_id, "candidate_id": candidate_id, "decision": decision, "note": note.strip() if note else None, "reviewed_at": reviewed_at}
    review_path = root / "learning" / "reviews" / f"{review['review_id']}.json"; write_json_atomic(review_path, review)
    candidate["status"] = decision; candidate["review_note"] = review["note"]; write_json_atomic(path, candidate)
    return WorkflowResult(review, review_path)
