from __future__ import annotations

from pathlib import Path

import pytest

from test_project_workflow import _outline, _private_candidate, _project_with_brief, _routes
from xhs_agent.projects import (
    WorkflowError, approve_submission, archive_publication, create_submission,
    finalize_archive, finalize_publication_copy, prepare_publication_copy, review_learning,
)
from xhs_agent.renderers import build_workbench
from xhs_agent.storage import read_json


def _approved_project(tmp_path: Path):
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    routes = _routes(state, project.object["project_id"], finalized.baseline)
    outline = _outline(state, project.object["project_id"], routes.object["routes"][0])
    submission = create_submission(state, project.object["project_id"], track="outline", source_object_id=outline.object["outline_id"])
    approve_submission(state, project.object["project_id"], submission.object["submission_id"])
    task = prepare_publication_copy(state, project.object["project_id"])
    candidate = _private_candidate(task, "copy-candidate.json", {"schema_version": 1, "title_options": ["三类测试卡片怎么归位"], "body": "这是一段用于验证归档流程的合成测试正文。", "tags": ["合成样例"], "brief_coverage": ["可拆分"], "risks": []})
    copy = finalize_publication_copy(state, task.run["run_id"], candidate)
    copy_submission = create_submission(state, project.object["project_id"], track="publication_copy", source_object_id=copy.object["copy_id"])
    approve_submission(state, project.object["project_id"], copy_submission.object["submission_id"])
    return state, project, outline, copy


def test_archive_is_incremental_and_finalizes_with_learning_gate(tmp_path: Path) -> None:
    state, project, _outline, _copy = _approved_project(tmp_path)
    oral = tmp_path / "最终口播.md"; oral.write_text("这是合成口播样例。先给测试卡片分类，再放入对应模块。", encoding="utf-8")
    first = archive_publication(state, project.object["project_id"], oral_script=oral)
    assert first.bundle["completeness"] == "partial" and first.run is None
    project_after_oral = read_json(project.path)
    assert project_after_oral["workflow_state"]["creator_production"] == "complete"
    assert project_after_oral["workflow_state"]["archive"] == "incomplete"

    copy = tmp_path / "实际发布配文.md"; copy.write_text("# 三类测试卡片怎么归位\n这是一段合成测试正文，并新增D类测试卡片。\n#合成样例 #流程测试", encoding="utf-8")
    screenshot = tmp_path / "实际发布截图.jpg"; screenshot.write_bytes(b"\xff\xd8\xff\xd9")
    second = archive_publication(state, project.object["project_id"], published_copy=copy, published_copy_screenshot=screenshot, published_at="2026-08-13T08:00:00Z", published_url="https://www.xiaohongshu.com/explore/synthetic")
    assert second.run["status"] == "waiting_for_agent"
    screenshot_ref = second.bundle["published_copy_screenshot_source"]
    assert screenshot_ref["media_type"] == "image/jpeg"
    assert (state / screenshot_ref["path"]).read_bytes() == screenshot.read_bytes()
    assert "submissions" in read_json(second.task_path)["inputs"]["approved_outline_submission_path"]
    assert "submissions" in read_json(second.task_path)["inputs"]["approved_copy_submission_path"]
    evidence = read_json(Path(second.run["outputs"]["evidence_path"]))
    oral_ev = next(item["evidence_id"] for item in evidence if item["kind"] == "oral_script")
    copy_ev = next(item["evidence_id"] for item in evidence if item["kind"] == "published_copy")
    candidate = _private_candidate(second, "archive-candidate.json", {
        "schema_version": 1,
        "published_copy": {"title": "三类测试卡片怎么归位", "body": "这是一段合成测试正文，并新增D类测试卡片。", "tags": ["合成样例", "流程测试"]},
        "approved_outline_diff": {"summary": "保留合成流程，新增一个测试分类。", "changes": [{"type": "added", "description": "增加D类测试卡片", "approved_ref": "A/B/C三类", "final_ref": "新增D类", "likely_source": "creator_creation", "confidence": 0.8}]},
        "approved_copy_diff": {"summary": "正文新增一个测试分类和 Tag。", "changes": [{"type": "added", "description": "增加流程测试 Tag", "approved_ref": "#合成样例", "final_ref": "#流程测试", "likely_source": "unknown", "confidence": 0.6}]},
        "learning_candidates": [{"scope": "project_only", "statement": "新增合成分类可验证差异归档。", "reason": "最终口播和配文都包含新增测试分类。", "evidence_refs": [oral_ev, copy_ev], "confidence": 0.9}],
    })
    finalized = finalize_archive(state, second.run["run_id"], candidate)
    assert finalized.bundle["completeness"] == "complete"
    assert finalized.run["status"] == "waiting_for_user"
    project_final = read_json(project.path)
    assert project_final["workflow_state"]["archive"] == "complete"
    learning_id = finalized.run["outputs"]["learning_candidate_ids"][0]
    learning_path = state / "projects" / project.object["project_id"] / "learning" / f"{learning_id}.json"
    assert read_json(learning_path)["confidence"] == 0.75
    reviewed = review_learning(state, project.object["project_id"], learning_id, "accepted", note="先作为可复用候选，不升级 Baseline")
    assert reviewed.object["decision"] == "accepted"
    assert read_json(learning_path)["status"] == "accepted"

    output = tmp_path / "workbench"; result = build_workbench(state, output)
    archive_page = output / "projects" / project.object["project_id"] / "archive.html"
    html = archive_page.read_text(encoding="utf-8")
    assert result.project_count == 1 and "最终发布事实" in html
    assert "Approved Outline" in html and "候选经验" in html
    assert "发布截图原件" in html and "打开实际发布链接" in html


def test_archive_rejects_overwriting_preserved_source(tmp_path: Path) -> None:
    state, project, _outline, _copy = _approved_project(tmp_path)
    first = tmp_path / "final-v1.md"; first.write_text("第一版最终口播", encoding="utf-8")
    second = tmp_path / "final-v2.md"; second.write_text("不同文件", encoding="utf-8")
    archive_publication(state, project.object["project_id"], oral_script=first)
    with pytest.raises(WorkflowError, match="不能覆盖"):
        archive_publication(state, project.object["project_id"], oral_script=second)


def test_complete_archive_requires_approved_copy(tmp_path: Path) -> None:
    state, analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    routes = _routes(state, project.object["project_id"], finalized.baseline)
    outline = _outline(state, project.object["project_id"], routes.object["routes"][0])
    submission = create_submission(state, project.object["project_id"], track="outline", source_object_id=outline.object["outline_id"])
    approve_submission(state, project.object["project_id"], submission.object["submission_id"])
    oral = tmp_path / "oral.md"; oral.write_text("最终口播", encoding="utf-8")
    copy = tmp_path / "copy.md"; copy.write_text("标题\n正文\n#Tag", encoding="utf-8")
    with pytest.raises(WorkflowError, match="Publication Copy"):
        archive_publication(state, project.object["project_id"], oral_script=oral, published_copy=copy)
    assert not (state / "projects" / project.object["project_id"] / "archive" / "bundle.json").exists()


def test_partial_archive_has_readable_workbench_page(tmp_path: Path) -> None:
    state, project, _outline, _copy = _approved_project(tmp_path)
    oral = tmp_path / "oral.md"; oral.write_text("只有最终口播脚本", encoding="utf-8")
    archive_publication(state, project.object["project_id"], oral_script=oral)
    output = tmp_path / "workbench"; build_workbench(state, output)
    page = output / "projects" / project.object["project_id"] / "archive.html"
    html = page.read_text(encoding="utf-8")
    assert "partial" in html
    assert "实际发布配文尚未上传" in html
    assert "等待两类最终文件齐全后生成差异" in html


def test_learning_review_does_not_mutate_bound_baseline(tmp_path: Path) -> None:
    state, project, _outline, _copy = _approved_project(tmp_path)
    baseline_matches = list((state / "creators").glob(f"*/baselines/{project.object['baseline_id']}.json"))
    before = baseline_matches[0].read_bytes()
    oral = tmp_path / "oral.md"; oral.write_text("最终口播", encoding="utf-8")
    copy = tmp_path / "copy.md"; copy.write_text("标题\n正文\n#Tag", encoding="utf-8")
    archived = archive_publication(state, project.object["project_id"], oral_script=oral, published_copy=copy)
    evidence = read_json(Path(archived.run["outputs"]["evidence_path"]))
    candidate = _private_candidate(archived, "archive-candidate.json", {"schema_version": 1, "published_copy": {"title": "标题", "body": "正文", "tags": ["Tag"]}, "approved_outline_diff": {"summary": "", "changes": []}, "approved_copy_diff": {"summary": "", "changes": []}, "learning_candidates": [{"scope": "project_only", "statement": "候选规律", "reason": "只来自本项目", "evidence_refs": [evidence[0]["evidence_id"]], "confidence": 0.6}]})
    finalized = finalize_archive(state, archived.run["run_id"], candidate)
    review_learning(state, project.object["project_id"], finalized.run["outputs"]["learning_candidate_ids"][0], "accepted")
    assert baseline_matches[0].read_bytes() == before


def test_completed_archive_cannot_create_duplicate_task(tmp_path: Path) -> None:
    state, project, _outline, _copy = _approved_project(tmp_path)
    oral = tmp_path / "oral.md"; oral.write_text("最终口播", encoding="utf-8")
    copy = tmp_path / "copy.md"; copy.write_text("标题\n正文\n#Tag", encoding="utf-8")
    archived = archive_publication(state, project.object["project_id"], oral_script=oral, published_copy=copy)
    evidence = read_json(Path(archived.run["outputs"]["evidence_path"]))
    candidate = _private_candidate(archived, "archive-candidate.json", {"schema_version": 1, "published_copy": {"title": "标题", "body": "正文", "tags": ["Tag"]}, "approved_outline_diff": {"summary": "", "changes": []}, "approved_copy_diff": {"summary": "", "changes": []}, "learning_candidates": []})
    finalize_archive(state, archived.run["run_id"], candidate)
    with pytest.raises(WorkflowError, match="已完成最终归档"):
        archive_publication(state, project.object["project_id"], oral_script=oral)
