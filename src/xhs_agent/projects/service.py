from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..creator.baseline import utc_now
from ..storage import file_sha256, new_id, next_object_version, read_json, write_json_atomic
from .extractors import ExtractionError, extract_document


class WorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowResult:
    object: dict[str, Any]
    path: Path
    run: dict[str, Any] | None = None
    task_path: Path | None = None


def _project_root(state: Path, project_id: str) -> Path:
    root = state / "projects" / project_id
    project = read_json(root / "project.json")
    if not isinstance(project, dict) or project.get("project_id") != project_id:
        raise WorkflowError(f"找不到 Project：{project_id}")
    return root


def _find_baseline(state: Path, baseline_id: str) -> tuple[Path, dict[str, Any]]:
    matches = list((state / "creators").glob(f"*/baselines/{baseline_id}.json"))
    if len(matches) != 1:
        raise WorkflowError(f"找不到唯一 Baseline：{baseline_id}")
    baseline = read_json(matches[0])
    if not isinstance(baseline, dict) or baseline.get("review_status") != "confirmed":
        raise WorkflowError("Project 只能绑定已经人工确认的 Baseline")
    return matches[0], baseline


def _find_confirmed_playbook(state: Path, baseline_id: str) -> tuple[Path | None, dict[str, Any] | None]:
    matches: list[tuple[int, Path, dict[str, Any]]] = []
    for path in (state / "creators").glob("*/playbooks/*.json"):
        value = read_json(path)
        if isinstance(value, dict) and value.get("baseline_id") == baseline_id and value.get("review_status") == "confirmed":
            matches.append((int(value.get("version", 0)), path, value))
    if not matches:
        return None, None
    _version, path, value = max(matches, key=lambda item: item[0])
    return path, value


def _mask_evidence(value: Any, excluded: set[str]) -> Any:
    if isinstance(value, dict):
        if value.get("evidence_id") in excluded:
            return None
        return {key: masked for key, item in value.items() if (masked := _mask_evidence(item, excluded)) is not None}
    if isinstance(value, list):
        return [masked for item in value if (masked := _mask_evidence(item, excluded)) is not None]
    return deepcopy(value)


def _run(state: Path, operation: str, inputs: dict[str, Any], steps: list[str]) -> tuple[dict[str, Any], Path]:
    now = utc_now()
    run_id = new_id("run")
    value = {
        "schema_version": 1, "run_id": run_id, "operation": operation,
        "status": "running", "inputs": inputs, "outputs": {},
        "steps": [{"name": name, "status": "pending", "error": None} for name in steps],
        "error_code": None, "recovery_hint": None, "started_at": now, "updated_at": now,
    }
    path = state / "runs" / f"{run_id}.json"
    write_json_atomic(path, value)
    return value, path


def _finish_task_run(run: dict[str, Any], run_path: Path, task: Path, candidate: Path, **outputs: Any) -> None:
    run["steps"][0]["status"] = "completed"
    run["status"] = "waiting_for_agent"
    run["outputs"] = {**outputs, "task_path": str(task), "candidate_output_path": str(candidate)}
    run["updated_at"] = utc_now()
    write_json_atomic(run_path, run)


def create_project(state: Path, *, creator_id: str, baseline_id: str, title: str, brand: str, product: str) -> WorkflowResult:
    _baseline_path, baseline = _find_baseline(state, baseline_id)
    if baseline.get("creator_id") != creator_id:
        raise WorkflowError("Baseline 不属于指定 Creator")
    for label, value in (("title", title), ("brand", brand), ("product", product)):
        if not value.strip():
            raise WorkflowError(f"{label} 不能为空")
    now = utc_now()
    _playbook_path, playbook = _find_confirmed_playbook(state, baseline_id)
    project = {
        "schema_version": 1, "project_id": new_id("project"), "creator_id": creator_id,
        "title": title.strip(), "brand": brand.strip(), "product": product.strip(),
        "baseline_id": baseline_id,
        "workflow_state": {"outline": "not_started", "publication_copy": "not_started", "creator_production": "not_started", "publication": "not_published", "archive": "incomplete"},
        "created_at": now, "updated_at": now,
    }
    if playbook:
        project["playbook_id"] = playbook["playbook_id"]
    path = state / "projects" / project["project_id"] / "project.json"
    write_json_atomic(path, project)
    return WorkflowResult(project, path)


def import_brief(state: Path, project_id: str, source: Path) -> WorkflowResult:
    root = _project_root(state, project_id)
    source = source.resolve()
    if not source.is_file():
        raise WorkflowError(f"Brief 文件不存在：{source}")
    digest = file_sha256(source)
    media, text, blocks, warnings = extract_document(source)
    stored = root / "brief" / "source" / f"{digest[:12]}-{source.name}"
    stored.parent.mkdir(parents=True, exist_ok=True)
    if not stored.exists():
        shutil.copy2(source, stored)
    extraction_id = new_id("extract")
    extraction = {
        "schema_version": 1, "extraction_id": extraction_id, "project_id": project_id,
        "source_file": {"path": str(stored.relative_to(state)), "sha256": digest, "media_type": media, "original_name": source.name},
        "text": text, "blocks": blocks, "warnings": warnings, "extracted_at": utc_now(),
    }
    extraction_path = root / "brief" / "extractions" / f"{extraction_id}.json"
    write_json_atomic(extraction_path, extraction)
    run, run_path = _run(state, "brief.import", {"project_id": project_id, "source_sha256": digest}, ["copy_and_extract", "ai_structure_brief", "validate_brief"])
    run_dir = root / "runs" / run["run_id"]
    task_path = run_dir / "brief-task.json"
    candidate_path = run_dir / "brief-candidate.json"
    task = {
        "schema_version": 1, "task_type": "brief_structuring", "run_id": run["run_id"], "project_id": project_id,
        "protocol": "references/brief-to-outline.md", "inputs": {"project_path": str(root / "project.json"), "extraction_path": str(extraction_path)},
        "candidate_output": str(candidate_path),
        "candidate_schema": "schemas/v1/brief-candidate.schema.json",
        "instructions": ["只记录原文明确事实；推断必须带 confidence", "must_include、forbidden 与合规限制不得臆造", "列出会改变路线或造成合规风险的 open_questions"],
    }
    write_json_atomic(task_path, task)
    _finish_task_run(run, run_path, task_path, candidate_path, project_id=project_id, extraction_path=str(extraction_path))
    return WorkflowResult(extraction, extraction_path, run, task_path)


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise WorkflowError(f"{label} 必须是字符串数组")
    return [item.strip() for item in value]


def _candidate_for_run(state: Path, run_id: str, candidate_path: Path, operation: str) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    run_path = state / "runs" / f"{run_id}.json"
    run = read_json(run_path)
    if not isinstance(run, dict) or run.get("operation") != operation:
        raise WorkflowError(f"Run 不是 {operation}：{run_id}")
    candidate_path = candidate_path.resolve()
    if not candidate_path.is_relative_to(state.resolve()):
        raise WorkflowError("candidate 必须位于私有 .xhs-agent 目录")
    candidate = read_json(candidate_path)
    if not isinstance(candidate, dict):
        raise WorkflowError("candidate 必须是 JSON 对象")
    return run, run_path, candidate


def finalize_brief(state: Path, run_id: str, candidate_path: Path) -> WorkflowResult:
    run, run_path, candidate = _candidate_for_run(state, run_id, candidate_path, "brief.import")
    project_id = str(run["inputs"]["project_id"])
    root = _project_root(state, project_id)
    project = read_json(root / "project.json")
    required = {"brand", "product", "deliverable", "facts", "inferences", "open_questions"}
    if candidate.get("schema_version") != 1 or not required.issubset(candidate):
        raise WorkflowError("Brief candidate 缺少必需字段")
    if candidate["brand"].strip() != project["brand"] or candidate["product"].strip() != project["product"]:
        raise WorkflowError("Brief 的品牌/产品与 Project 不一致；请先确认而不是静默覆盖")
    inferences = candidate.get("inferences")
    if not isinstance(inferences, list):
        raise WorkflowError("inferences 必须是数组")
    for item in inferences:
        if not isinstance(item, dict) or not str(item.get("statement", "")).strip() or not 0 <= float(item.get("confidence", -1)) <= 1:
            raise WorkflowError("每条 inference 必须有 statement 和 0-1 confidence")
    extraction = read_json(Path(run["outputs"]["extraction_path"]))
    source_ref = extraction["source_file"]
    brief = {
        "schema_version": 1, "brief_id": new_id("brief"), "project_id": project_id,
        "source_files": [source_ref], "brand": project["brand"], "product": project["product"],
        "platform": "xiaohongshu", "deliverable": str(candidate["deliverable"]).strip(),
        "audience": candidate.get("audience"), "pain_points": _strings(candidate.get("pain_points", []), "pain_points"),
        "selling_points": _strings(candidate.get("selling_points", []), "selling_points"),
        "must_include": _strings(candidate.get("must_include", []), "must_include"),
        "forbidden": _strings(candidate.get("forbidden", []), "forbidden"),
        "scene": candidate.get("scene"), "campaign": candidate.get("campaign"), "deadline": candidate.get("deadline"),
        "facts": _strings(candidate["facts"], "facts"),
        "inferences": [{"statement": str(item["statement"]).strip(), "confidence": float(item["confidence"])} for item in inferences],
        "open_questions": _strings(candidate["open_questions"], "open_questions"),
    }
    path = root / "brief" / "briefs" / f"{brief['brief_id']}.json"
    write_json_atomic(path, brief)
    write_json_atomic(root / "brief" / "active.json", {"brief_id": brief["brief_id"], "path": str(path)})
    run["steps"][1]["status"] = "completed"; run["steps"][-1]["status"] = "completed"; run["status"] = "completed"; run["outputs"].update({"brief_id": brief["brief_id"], "brief_path": str(path)}); run["updated_at"] = utc_now()
    write_json_atomic(run_path, run)
    return WorkflowResult(brief, path, run)


def _active_brief(root: Path) -> tuple[Path, dict[str, Any]]:
    active = read_json(root / "brief" / "active.json")
    if not isinstance(active, dict):
        raise WorkflowError("Project 还没有结构化 Brief")
    path = Path(active["path"])
    value = read_json(path)
    if not isinstance(value, dict):
        raise WorkflowError("结构化 Brief 已损坏")
    return path, value


def prepare_routes(
    state: Path,
    project_id: str,
    *,
    count: int = 1,
    exclude_evidence_ids: list[str] | None = None,
) -> WorkflowResult:
    if count not in (1, 2, 3):
        raise WorkflowError("路线数量只能是 1、2 或 3")
    root = _project_root(state, project_id); project = read_json(root / "project.json"); brief_path, _brief = _active_brief(root)
    baseline_path, baseline = _find_baseline(state, project["baseline_id"])
    playbook_path, playbook = _find_confirmed_playbook(state, project["baseline_id"])
    if playbook and project.get("playbook_id") not in {None, playbook["playbook_id"]}:
        matches = list((state / "creators").glob(f"*/playbooks/{project['playbook_id']}.json"))
        if len(matches) != 1:
            raise WorkflowError("Project 绑定的 Creator Playbook 已不存在")
        playbook_path, playbook = matches[0], read_json(matches[0])
    if playbook and not project.get("playbook_id"):
        project["playbook_id"] = playbook["playbook_id"]
        project["updated_at"] = utc_now()
        write_json_atomic(root / "project.json", project)
    excluded = {str(value).strip() for value in (exclude_evidence_ids or []) if str(value).strip()}
    available = {ref["evidence_id"] for claim in baseline.get("claims", []) for ref in claim.get("evidence_refs", [])}
    unknown = sorted(excluded - available)
    if unknown:
        raise WorkflowError(f"回测排除项不属于绑定 Baseline：{unknown}")
    if excluded:
        project["backtest_excluded_evidence_ids"] = sorted(excluded)
    else:
        project.pop("backtest_excluded_evidence_ids", None)
    project["updated_at"] = utc_now()
    write_json_atomic(root / "project.json", project)
    run, run_path = _run(state, "routes.generate", {"project_id": project_id, "route_count": count, "excluded_evidence_ids": sorted(excluded)}, ["load_context", "ai_generate_routes", "validate_routes"])
    run_dir = root / "runs" / run["run_id"]; task_path = run_dir / "routes-task.json"; candidate = run_dir / "routes-candidate.json"
    context_path = run_dir / "creator-context.json"
    context = {
        "schema_version": 1,
        "baseline": _mask_evidence(baseline, excluded),
        "playbook": _mask_evidence(playbook, excluded) if playbook else None,
        "backtest": {"excluded_evidence_ids": sorted(excluded), "reason": "防止已发布案例答案泄漏"} if excluded else None,
    }
    write_json_atomic(context_path, context)
    task = {"schema_version": 1, "task_type": "content_routes", "run_id": run["run_id"], "project_id": project_id, "protocol": "references/brief-to-outline.md", "inputs": {"brief_path": str(brief_path), "creator_context_path": str(context_path), "route_count": count}, "candidate_output": str(candidate), "candidate_schema": "schemas/v1/content-routes-candidate.schema.json", "instructions": [f"严格生成 {count} 条路线，不自行增加或减少", "生成多条时，任意两条至少在 conflict、scene、product_role、emotional_arc 中两项不同", "同时使用已确认 Baseline 与 Creator Playbook；creator_fit 只能引用当前 context 中未排除的 evidence_id", "回测排除项及最终脚本不得用于生成、复述或补全路线", "只能推荐一条路线"]}
    write_json_atomic(task_path, task); _finish_task_run(run, run_path, task_path, candidate, project_id=project_id)
    return WorkflowResult(task, task_path, run, task_path)


def _route_difference(left: dict[str, Any], right: dict[str, Any]) -> int:
    return sum(left.get(field) != right.get(field) for field in ("conflict", "scene", "product_role", "emotional_arc"))


def finalize_routes(state: Path, run_id: str, candidate_path: Path) -> WorkflowResult:
    run, run_path, candidate = _candidate_for_run(state, run_id, candidate_path, "routes.generate")
    project_id = str(run["inputs"]["project_id"]); root = _project_root(state, project_id); project = read_json(root / "project.json")
    _baseline_path, baseline = _find_baseline(state, project["baseline_id"])
    excluded = set(run.get("inputs", {}).get("excluded_evidence_ids", []))
    allowed_evidence = {ref["evidence_id"] for claim in baseline.get("claims", []) for ref in claim.get("evidence_refs", [])} - excluded
    routes = candidate.get("routes")
    expected_count = int(run["inputs"].get("route_count", 1))
    if candidate.get("schema_version") != 1 or not isinstance(routes, list) or len(routes) != expected_count:
        raise WorkflowError(f"路线 candidate 必须严格包含 {expected_count} 条 routes")
    if sum(bool(item.get("recommended")) for item in routes) != 1:
        raise WorkflowError("必须且只能推荐一条路线")
    for index, route in enumerate(routes):
        for field in ("premise", "conflict", "scene", "product_role"):
            if not isinstance(route.get(field), str) or not route[field].strip():
                raise WorkflowError(f"路线 {index + 1} 缺少 {field}")
        if not isinstance(route.get("emotional_arc"), list) or not route["emotional_arc"]:
            raise WorkflowError(f"路线 {index + 1} 缺少 emotional_arc")
        fit = route.get("creator_fit")
        if not isinstance(fit, dict) or not fit.get("reason") or not isinstance(fit.get("evidence_refs"), list) or not fit["evidence_refs"]:
            raise WorkflowError(f"路线 {index + 1} creator_fit 无效")
        refs = [ref if isinstance(ref, str) else ref.get("evidence_id") if isinstance(ref, dict) else None for ref in fit["evidence_refs"]]
        if any(not ref or ref not in allowed_evidence for ref in refs):
            raise WorkflowError(f"路线 {index + 1} 引用了不属于绑定 Baseline 的 Evidence")
        fit["evidence_refs"] = [{"evidence_id": ref, "note": None} for ref in dict.fromkeys(refs)]
    for i, left in enumerate(routes):
        for right in routes[i + 1:]:
            if _route_difference(left, right) < 2:
                raise WorkflowError("路线差异不足：任意两条必须至少有两个策略维度不同")
    route_set_id = new_id("routeset"); set_root = root / "routes" / route_set_id; stored = []
    for route in routes:
        value = {"schema_version": 1, "route_id": new_id("route"), "project_id": project_id, **route}
        path = set_root / f"{value['route_id']}.json"; write_json_atomic(path, value); stored.append(value)
    route_set = {"schema_version": 1, "route_set_id": route_set_id, "project_id": project_id, "routes": [item["route_id"] for item in stored], "rationale": candidate.get("rationale"), "created_at": utc_now()}
    path = set_root / "route-set.json"; write_json_atomic(path, route_set)
    project["workflow_state"]["outline"] = "drafting"; project["updated_at"] = utc_now(); write_json_atomic(root / "project.json", project)
    run["steps"][1]["status"] = "completed"; run["steps"][-1]["status"] = "completed"; run["status"] = "waiting_for_user"; run["outputs"].update({"route_set_id": route_set_id, "route_ids": route_set["routes"], "route_set_path": str(path)}); run["updated_at"] = utc_now(); write_json_atomic(run_path, run)
    return WorkflowResult(route_set, path, run)


def select_route(state: Path, project_id: str, route_id: str, *, note: str | None = None) -> WorkflowResult:
    root = _project_root(state, project_id); matches = list((root / "routes").glob(f"*/{route_id}.json"))
    if len(matches) != 1: raise WorkflowError(f"找不到唯一 Route：{route_id}")
    selection = {"schema_version": 1, "selection_id": new_id("rsel"), "project_id": project_id, "route_id": route_id, "note": note.strip() if note else None, "selected_at": utc_now()}
    path = root / "routes" / "selection.json"; write_json_atomic(path, selection)
    return WorkflowResult(selection, path)


def prepare_outline(state: Path, project_id: str, *, feedback_id: str | None = None) -> WorkflowResult:
    root = _project_root(state, project_id); project = read_json(root / "project.json"); brief_path, _ = _active_brief(root); _baseline_path, baseline = _find_baseline(state, project["baseline_id"])
    _playbook_path, playbook = _find_confirmed_playbook(state, project["baseline_id"])
    if project.get("playbook_id"):
        matches = list((state / "creators").glob(f"*/playbooks/{project['playbook_id']}.json"))
        if len(matches) != 1:
            raise WorkflowError("Project 绑定的 Creator Playbook 已不存在")
        playbook = read_json(matches[0])
    excluded = {str(value).strip() for value in project.get("backtest_excluded_evidence_ids", []) if str(value).strip()}
    selection = read_json(root / "routes" / "selection.json")
    if not isinstance(selection, dict): raise WorkflowError("生成大纲前必须先选择路线")
    matches = list((root / "routes").glob(f"*/{selection['route_id']}.json")); route_path = matches[0] if len(matches) == 1 else None
    if route_path is None: raise WorkflowError("选中的 Route 不存在")
    run, run_path = _run(state, "outline.generate", {"project_id": project_id, "feedback_id": feedback_id, "excluded_evidence_ids": sorted(excluded)}, ["load_context", "ai_generate_outline", "validate_and_version"])
    run_dir = root / "runs" / run["run_id"]; task_path = run_dir / "outline-task.json"; candidate = run_dir / "outline-candidate.json"
    context_path = run_dir / "creator-context.json"
    context = {
        "schema_version": 1,
        "baseline": _mask_evidence(baseline, excluded),
        "playbook": _mask_evidence(playbook, excluded) if playbook else None,
        "backtest": {"excluded_evidence_ids": sorted(excluded), "reason": "防止已发布案例答案泄漏"} if excluded else None,
    }
    write_json_atomic(context_path, context)
    prior = sorted((root / "outlines").glob("*.json")); feedback_path = None
    if feedback_id:
        candidates = [root / "feedback" / f"{feedback_id}.json", root / "brand" / "outline" / "feedback" / f"{feedback_id}.json"]
        feedback_path = next((path for path in candidates if path.is_file()), None)
        if feedback_path is None: raise WorkflowError(f"找不到 Outline Feedback：{feedback_id}")
    task = {"schema_version": 1, "task_type": "outline", "run_id": run["run_id"], "project_id": project_id, "protocol": "references/brief-to-outline.md", "inputs": {"brief_path": str(brief_path), "creator_context_path": str(context_path), "route_path": str(route_path), "previous_outline_path": str(prior[-1]) if prior else None, "feedback_path": str(feedback_path) if feedback_path else None}, "candidate_output": str(candidate), "candidate_schema": "schemas/v1/outline-candidate.schema.json", "instructions": ["默认生成 7 段叙事分组 + 逐镜头 shot_rows 双层结构；Brief 明确要求其他结构时才调整段数", "sections 负责策略导航；shot_rows 负责可直接搬入品牌模板的执行颗粒度", "每个 shot row 必须对应镜号、所属分组、精确秒数、拍摄场景/画面、景别/机位、大致口播、花字、音效或拍摄要点、品牌露出", "镜号必须从 1 连续编号；每段至少一镜；每段逐镜头秒数之和必须落在该段 duration_seconds 范围内", "target_duration_seconds 必须等于全部 shot rows 的精确秒数之和，并落在 estimated_duration_seconds 范围内", "rough_voiceover 是品牌审核用的大致口播，不是替博主完成最终口播脚本", "同时使用已确认 Baseline 与 Creator Playbook；只能读取 creator_context_path 中未排除的证据", "回测排除项、最终脚本、最终发布正文和最终镜头顺序不得用于生成、复述或补全大纲", "逐项覆盖 must_include，并扫描 forbidden", "暂定标题不是最终发布标题"]}
    write_json_atomic(task_path, task); _finish_task_run(run, run_path, task_path, candidate, project_id=project_id)
    return WorkflowResult(task, task_path, run, task_path)


def finalize_outline(state: Path, run_id: str, candidate_path: Path) -> WorkflowResult:
    run, run_path, candidate = _candidate_for_run(state, run_id, candidate_path, "outline.generate")
    project_id = str(run["inputs"]["project_id"]); root = _project_root(state, project_id); selection = read_json(root / "routes" / "selection.json")
    sections = candidate.get("sections")
    if candidate.get("schema_version") != 1 or not isinstance(sections, list) or not sections:
        raise WorkflowError("大纲 candidate 必须包含 sections")
    for order, section in enumerate(sections, start=1):
        if section.get("order") != order or not section.get("goal") or not section.get("label"):
            raise WorkflowError("大纲 sections 必须从 1 连续编号并包含 label 和 goal")
        duration = section.get("duration_seconds")
        if not isinstance(duration, dict) or set(duration) != {"min", "max"} or not 1 <= int(duration["min"]) <= int(duration["max"]):
            raise WorkflowError("每个 section 必须包含有效 duration_seconds min/max")
        _strings(section.get("shots", []), "shots"); _strings(section.get("rough_voiceover", []), "rough_voiceover"); _strings(section.get("on_screen_text", []), "on_screen_text")
        if "brand_presence" not in section or section["brand_presence"] is not None and not isinstance(section["brand_presence"], str):
            raise WorkflowError("每个 section 必须包含 brand_presence（可为 null）")
    estimated = candidate.get("estimated_duration_seconds")
    if not isinstance(estimated, dict) or set(estimated) != {"min", "max"} or not 1 <= int(estimated["min"]) <= int(estimated["max"]):
        raise WorkflowError("大纲必须包含有效 estimated_duration_seconds min/max")
    summed_min = sum(int(item["duration_seconds"]["min"]) for item in sections); summed_max = sum(int(item["duration_seconds"]["max"]) for item in sections)
    if estimated != {"min": summed_min, "max": summed_max}:
        raise WorkflowError("estimated_duration_seconds 必须等于各段秒数之和")
    shot_rows = candidate.get("shot_rows")
    if not isinstance(shot_rows, list) or not shot_rows:
        raise WorkflowError("大纲必须包含逐镜头 shot_rows")
    section_orders = {int(item["order"]) for item in sections}
    shot_seconds_by_section = {order: 0 for order in section_orders}
    for shot_no, shot in enumerate(shot_rows, start=1):
        if shot.get("shot_no") != shot_no:
            raise WorkflowError("shot_rows 必须从 1 连续编号")
        section_order = shot.get("section_order")
        if section_order not in section_orders:
            raise WorkflowError("每个 shot row 必须关联有效 section_order")
        seconds = shot.get("duration_seconds")
        if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 1:
            raise WorkflowError("每个 shot row 必须包含大于 0 的精确 duration_seconds")
        for field in ("scene", "framing", "rough_voiceover"):
            if not isinstance(shot.get(field), str) or not shot[field].strip():
                raise WorkflowError(f"每个 shot row 必须包含 {field}")
        _strings(shot.get("on_screen_text", []), "shot_rows.on_screen_text")
        _strings(shot.get("audio_or_notes", []), "shot_rows.audio_or_notes")
        if "brand_presence" not in shot or shot["brand_presence"] is not None and not isinstance(shot["brand_presence"], str):
            raise WorkflowError("每个 shot row 必须包含 brand_presence（可为 null）")
        shot_seconds_by_section[int(section_order)] += seconds
    for section in sections:
        duration = section["duration_seconds"]
        actual = shot_seconds_by_section[int(section["order"])]
        if actual == 0 or not int(duration["min"]) <= actual <= int(duration["max"]):
            raise WorkflowError("每段至少包含一镜，且逐镜头秒数之和必须落在该段 duration_seconds 范围内")
    target = candidate.get("target_duration_seconds")
    shot_total = sum(int(item["duration_seconds"]) for item in shot_rows)
    if not isinstance(target, int) or isinstance(target, bool) or target != shot_total:
        raise WorkflowError("target_duration_seconds 必须等于全部 shot_rows 秒数之和")
    if not int(estimated["min"]) <= target <= int(estimated["max"]):
        raise WorkflowError("target_duration_seconds 必须落在 estimated_duration_seconds 范围内")
    version = next_object_version(root / "outlines")
    outline = {"schema_version": 1, "outline_id": new_id("outline"), "project_id": project_id, "route_id": selection["route_id"], "version": version, "working_titles": _strings(candidate.get("working_titles", []), "working_titles"), "hooks": _strings(candidate.get("hooks", []), "hooks"), "target_duration_seconds": target, "estimated_duration_seconds": estimated, "sections": sections, "shot_rows": shot_rows, "brief_coverage": _strings(candidate.get("brief_coverage", []), "brief_coverage"), "creator_fit_checks": _strings(candidate.get("creator_fit_checks", []), "creator_fit_checks"), "assumptions": _strings(candidate.get("assumptions", []), "assumptions"), "risks": _strings(candidate.get("risks", []), "risks"), "open_questions": _strings(candidate.get("open_questions", []), "open_questions"), "created_from_feedback_id": run["inputs"].get("feedback_id"), "created_at": utc_now()}
    path = root / "outlines" / f"{outline['outline_id']}.json"; write_json_atomic(path, outline)
    run["steps"][1]["status"] = "completed"; run["steps"][-1]["status"] = "completed"; run["status"] = "completed"; run["outputs"].update({"outline_id": outline["outline_id"], "outline_version": version, "outline_path": str(path)}); run["updated_at"] = utc_now(); write_json_atomic(run_path, run)
    return WorkflowResult(outline, path, run)


def record_internal_feedback(state: Path, project_id: str, outline_id: str, text: str) -> WorkflowResult:
    root = _project_root(state, project_id)
    if not (root / "outlines" / f"{outline_id}.json").is_file(): raise WorkflowError("反馈目标 Outline 不存在")
    if not text.strip(): raise WorkflowError("反馈不能为空")
    value = {"schema_version": 1, "feedback_id": new_id("ifeedback"), "project_id": project_id, "target_type": "outline", "target_id": outline_id, "raw_feedback": text.strip(), "created_at": utc_now()}
    path = root / "feedback" / f"{value['feedback_id']}.json"; write_json_atomic(path, value)
    return WorkflowResult(value, path)
