from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..storage import new_id, next_object_version, read_json, write_json_atomic
from .baseline import utc_now


class PlaybookError(ValueError):
    pass


@dataclass(frozen=True)
class PlaybookResult:
    playbook: dict[str, Any]
    playbook_path: Path
    run: dict[str, Any] | None = None
    task_path: Path | None = None


def _find_baseline(state: Path, baseline_id: str) -> tuple[Path, dict[str, Any]]:
    matches = list((state / "creators").glob(f"*/baselines/{baseline_id}.json"))
    if len(matches) != 1:
        raise PlaybookError(f"找不到唯一 Baseline：{baseline_id}")
    baseline = read_json(matches[0])
    if not isinstance(baseline, dict) or baseline.get("review_status") != "confirmed":
        raise PlaybookError("Creator Playbook 只能从已人工确认的 Baseline 生成")
    return matches[0], baseline


def _merged_evidence(creator_root: Path, baseline: dict[str, Any]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for run_id in (baseline.get("source_run_id"), baseline.get("longitudinal_run_id")):
        if not run_id:
            continue
        values = read_json(creator_root / "evidence" / f"{run_id}.json", [])
        for value in values if isinstance(values, list) else []:
            if isinstance(value, dict) and value.get("evidence_id"):
                merged[str(value["evidence_id"])] = value
    return list(merged.values())


def prepare_playbook(state: Path, baseline_id: str) -> PlaybookResult:
    baseline_path, baseline = _find_baseline(state, baseline_id)
    creator_root = baseline_path.parent.parent
    now = utc_now()
    run_id = new_id("run")
    run_dir = creator_root / "source" / "playbook-runs" / run_id
    evidence_path = run_dir / "evidence.json"
    candidate_path = run_dir / "playbook-candidate.json"
    task_path = run_dir / "playbook-task.json"
    evidence = _merged_evidence(creator_root, baseline)
    write_json_atomic(evidence_path, evidence)
    task = {
        "schema_version": 1,
        "task_type": "creator_playbook_distillation",
        "run_id": run_id,
        "creator_id": baseline["creator_id"],
        "baseline_id": baseline_id,
        "protocol": "references/creator-playbook.md",
        "inputs": {
            "baseline_path": str(baseline_path),
            "primary_analysis_path": str(creator_root / "source" / "runs" / str(baseline["source_run_id"]) / "analysis.json"),
            "longitudinal_analysis_path": str(creator_root / "source" / "runs" / str(baseline.get("longitudinal_run_id")) / "analysis.json") if baseline.get("longitudinal_run_id") else None,
            "evidence_path": str(evidence_path),
        },
        "candidate_output": str(candidate_path),
        "candidate_schema": "schemas/v1/playbook-candidate.schema.json",
        "instructions": [
            "Baseline 是事实与目标边界；Playbook 只做可执行翻译，不得发明新画像结论",
            "当前主轴优先使用近期窗口；历史能力必须标注为次级或特定场景调用",
            "内容路线、标题和语言例句都必须回指 claim_id 或 evidence_id",
            "硬广式表达仅在品牌强约束时作为例外路线，不得写成默认风格",
            "输出选题与大纲方法，不代写博主最终逐字口播稿",
        ],
    }
    write_json_atomic(task_path, task)
    run = {
        "schema_version": 1,
        "run_id": run_id,
        "operation": "creator.playbook_generate",
        "status": "waiting_for_agent",
        "inputs": {"creator_id": baseline["creator_id"], "baseline_id": baseline_id},
        "outputs": {
            "task_path": str(task_path),
            "candidate_output_path": str(candidate_path),
            "baseline_path": str(baseline_path),
            "evidence_path": str(evidence_path),
        },
        "steps": [
            {"name": "prepare_playbook_task", "status": "completed", "error": None},
            {"name": "ai_playbook_distillation", "status": "pending", "error": None},
            {"name": "validate_and_version_playbook", "status": "pending", "error": None},
        ],
        "error_code": None,
        "recovery_hint": None,
        "started_at": now,
        "updated_at": now,
    }
    write_json_atomic(state / "runs" / f"{run_id}.json", run)
    return PlaybookResult({}, candidate_path, run, task_path)


def _strings(value: Any, label: str, *, minimum: int = 0, maximum: int | None = None) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise PlaybookError(f"{label} 必须是非空字符串数组")
    result = [item.strip() for item in value]
    if len(result) < minimum or (maximum is not None and len(result) > maximum):
        raise PlaybookError(f"{label} 数量必须为 {minimum}–{maximum or '不限'}")
    return result


def _validate_candidate(candidate: Any, baseline: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise PlaybookError("Playbook candidate 必须是 JSON 对象")
    required = {
        "schema_version", "creator_id", "baseline_id", "core_thesis", "current_content_axes",
        "legacy_capabilities", "route_patterns", "title_formulas", "body_templates", "language_kit",
        "commercial_rules", "audience_translation", "review_checklist", "limitations",
    }
    if set(candidate) != required:
        raise PlaybookError(f"Playbook candidate 字段不匹配，缺少 {sorted(required - set(candidate))}，多出 {sorted(set(candidate) - required)}")
    if candidate.get("schema_version") != 1 or candidate.get("creator_id") != baseline.get("creator_id") or candidate.get("baseline_id") != baseline.get("baseline_id"):
        raise PlaybookError("Playbook candidate 与当前 Creator/Baseline 不匹配")
    claim_ids = {str(item.get("claim_id")) for item in baseline.get("claims", [])}
    evidence_ids = {str(item.get("evidence_id")) for item in evidence}
    referenced_claims: list[str] = []
    referenced_evidence: list[str] = []
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "claim_ids": referenced_claims.extend(_strings(item, key, minimum=1))
                elif key == "evidence_id":
                    if not isinstance(item, str) or not item: raise PlaybookError("evidence_id 必须是非空字符串")
                    referenced_evidence.append(item)
                else: walk(item)
        elif isinstance(value, list):
            for item in value: walk(item)
    walk(candidate)
    unknown_claims = sorted(set(referenced_claims) - claim_ids)
    unknown_evidence = sorted(set(referenced_evidence) - evidence_ids)
    if unknown_claims or unknown_evidence:
        raise PlaybookError(f"存在无法追溯的引用：claim={unknown_claims} evidence={unknown_evidence}")
    for field, minimum, maximum in (
        ("current_content_axes", 2, 5), ("route_patterns", 3, 5),
        ("title_formulas", 3, 5), ("body_templates", 2, 5),
        ("review_checklist", 5, 12),
    ):
        value = candidate.get(field)
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            raise PlaybookError(f"{field} 数量必须为 {minimum}–{maximum}")
    _strings(candidate["review_checklist"], "review_checklist", minimum=5, maximum=12)
    _strings(candidate["limitations"], "limitations", minimum=1)
    return candidate


def finalize_playbook(state: Path, run_id: str, candidate_path: Path) -> PlaybookResult:
    run_path = state / "runs" / f"{run_id}.json"
    run = read_json(run_path)
    if not isinstance(run, dict) or run.get("operation") != "creator.playbook_generate":
        raise PlaybookError(f"找不到 Playbook Run：{run_id}")
    expected = Path(str(run.get("outputs", {}).get("candidate_output_path", ""))).resolve()
    if candidate_path.resolve() != expected:
        raise PlaybookError("只接受当前 Run 私有目录内声明的 candidate 文件")
    baseline = read_json(Path(run["outputs"]["baseline_path"]))
    evidence = read_json(Path(run["outputs"]["evidence_path"]), [])
    if not isinstance(baseline, dict) or baseline.get("review_status") != "confirmed":
        raise PlaybookError("源 Baseline 已失效或不再处于确认状态")
    candidate = _validate_candidate(read_json(candidate_path), baseline, evidence)
    creator_root = Path(run["outputs"]["baseline_path"]).parent.parent
    playbooks_dir = creator_root / "playbooks"
    version = next_object_version(playbooks_dir)
    playbook_id = f"playbook_{str(baseline['creator_id']).removeprefix('creator_')}_v{version}"
    playbook = {
        **candidate,
        "playbook_id": playbook_id,
        "version": version,
        "review_status": "pending_confirmation",
        "source_run_id": run_id,
        "created_at": utc_now(),
    }
    playbook_path = playbooks_dir / f"{playbook_id}.json"
    write_json_atomic(playbook_path, playbook)
    run["steps"][1]["status"] = "completed"
    run["steps"][2]["status"] = "completed"
    run["status"] = "waiting_for_user"
    run["outputs"].update({"playbook_id": playbook_id, "playbook_path": str(playbook_path)})
    run["updated_at"] = utc_now()
    write_json_atomic(run_path, run)
    return PlaybookResult(playbook, playbook_path, run, Path(run["outputs"]["task_path"]))


def confirm_playbook(state: Path, playbook_id: str, *, note: str | None = None) -> PlaybookResult:
    matches = list((state / "creators").glob(f"*/playbooks/{playbook_id}.json"))
    if len(matches) != 1:
        raise PlaybookError(f"找不到唯一 Playbook：{playbook_id}")
    path = matches[0]
    playbook = read_json(path)
    if not isinstance(playbook, dict) or playbook.get("review_status") not in {"pending_confirmation", "confirmed"}:
        raise PlaybookError("只有待确认或已确认的 Playbook 可以确认")
    if playbook.get("review_status") != "confirmed":
        playbook["review_status"] = "confirmed"
        playbook["confirmed_at"] = utc_now()
        playbook["confirmation_note"] = note.strip() if note else None
        write_json_atomic(path, playbook)
    return PlaybookResult(playbook, path)
