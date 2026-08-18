from __future__ import annotations

from pathlib import Path

import pytest

from test_creator_service import _analyze_and_finalize
from xhs_agent.creator.review import confirm_baseline
from xhs_agent.projects import (
    WorkflowError, approve_submission, create_project, create_submission,
    finalize_brief, finalize_outline, finalize_publication_copy, finalize_routes,
    import_brief, prepare_outline, prepare_publication_copy, prepare_routes,
    record_internal_feedback, record_publication_copy_feedback, select_route,
)
from xhs_agent.renderers import build_workbench
from xhs_agent.storage import read_json, write_json_atomic


def _private_candidate(result, name: str, value: dict) -> Path:
    path = Path(result.run["outputs"]["candidate_output_path"])
    assert path.name == name
    write_json_atomic(path, value)
    return path


def _project_with_brief(tmp_path: Path):
    state = tmp_path / ".xhs-agent"
    analyzed, finalized = _analyze_and_finalize(state)
    confirm_baseline(state, finalized.baseline["baseline_id"], note="阶段 4 测试确认")
    created = create_project(state, creator_id=analyzed.creator["creator_id"], baseline_id=finalized.baseline["baseline_id"], title="合成卡片整理项目", brand="虚构品牌A", product="测试用模块盒")
    source = tmp_path / "brief.md"
    source.write_text("# 合成合作要求\n产品：测试用模块盒\n场景：虚构卡片整理演示\n必须提：可拆分\n禁用：保证永久有效\n", encoding="utf-8")
    imported = import_brief(state, created.object["project_id"], source)
    candidate = _private_candidate(imported, "brief-candidate.json", {
        "schema_version": 1, "brand": "虚构品牌A", "product": "测试用模块盒", "deliverable": "合成视频大纲",
        "audience": "需要验证整理流程的虚构测试用户", "pain_points": ["测试卡片分类混乱"], "selling_points": ["可拆分"],
        "must_include": ["可拆分"], "forbidden": ["保证永久有效"], "scene": "虚构卡片整理演示", "campaign": None,
        "deadline": None, "facts": ["要求在合成整理场景中展示可拆分结构"],
        "inferences": [{"statement": "适合使用步骤化测试演示", "confidence": 0.7}], "open_questions": [],
    })
    brief = finalize_brief(state, imported.run["run_id"], candidate)
    return state, analyzed, finalized, created, brief


def _routes(state: Path, project_id: str, baseline: dict):
    evidence_id = baseline["claims"][0]["evidence_refs"][0]["evidence_id"]
    prepared = prepare_routes(state, project_id, count=3)
    candidate = _private_candidate(prepared, "routes-candidate.json", {
        "schema_version": 1, "rationale": "三条合成路线分别验证分类、计时和协作结构。", "routes": [
            {"premise": "先把三类测试卡片分开", "conflict": "颜色和编号混在一起", "scene": "合成工作台A", "emotional_arc": ["混乱", "分类", "完成"], "product_role": "提供可拆分分区", "creator_fit": {"reason": "符合先解释原因再给方法的测试表达", "evidence_refs": [evidence_id]}, "brief_coverage": ["可拆分"], "risks": ["避免永久有效承诺"], "recommended": True},
            {"premise": "按五分钟回合整理", "conflict": "一次处理全部样本耗时", "scene": "合成工作台B", "emotional_arc": ["停顿", "计时", "完成"], "product_role": "承接每回合的样本", "creator_fit": {"reason": "适合步骤化测试表达", "evidence_refs": [evidence_id]}, "brief_coverage": ["可拆分"], "risks": [], "recommended": False},
            {"premise": "让两名测试员协作归档", "conflict": "分类标准不一致", "scene": "合成工作台C", "emotional_arc": ["分歧", "标记", "同步"], "product_role": "显示统一分区", "creator_fit": {"reason": "保留第一人称测试视角", "evidence_refs": [evidence_id]}, "brief_coverage": ["可拆分"], "risks": ["明确这是虚构演示"], "recommended": False},
        ]})
    return finalize_routes(state, prepared.run["run_id"], candidate)


def _outline(state: Path, project_id: str, route_id: str):
    select_route(state, project_id, route_id)
    prepared = prepare_outline(state, project_id)
    candidate = _private_candidate(prepared, "outline-candidate.json", {
        "schema_version": 1, "working_titles": ["三类测试卡片怎么归位"], "hooks": ["这是一段只用于自动化测试的合成演示"],
        "target_duration_seconds": 70, "estimated_duration_seconds": {"min": 63, "max": 78},
        "sections": [
            {"order": 1, "label": "开场 Hook", "duration_seconds": {"min": 6, "max": 8}, "goal": "标明合成测试场景", "shots": ["展示红蓝绿三类测试卡片", "展示空工作台"], "rough_voiceover": ["以下内容完全由虚构测试数据构成。"], "on_screen_text": ["合成演示"], "brand_presence": None},
            {"order": 2, "label": "痛点铺垫", "duration_seconds": {"min": 10, "max": 12}, "goal": "展示分类问题", "shots": ["混合测试卡片", "显示重复编号"], "rough_voiceover": ["三类卡片混在一起时，测试步骤很难核对。"], "on_screen_text": ["合成问题：分类混乱"], "brand_presence": None},
            {"order": 3, "label": "转折 / 决策", "duration_seconds": {"min": 8, "max": 10}, "goal": "说明测试分类规则", "shots": ["按颜色分组", "添加A/B/C标签"], "rough_voiceover": ["先按颜色分组，再核对编号。"], "on_screen_text": ["先分类，再核对"], "brand_presence": "测试用模块盒进入画面"},
            {"order": 4, "label": "产品自然进入", "duration_seconds": {"min": 10, "max": 12}, "goal": "展示可拆分结构", "shots": ["拆分三个模块", "分别放入卡片"], "rough_voiceover": ["可拆分结构让三类测试样本保持独立。"], "on_screen_text": ["可拆分"], "brand_presence": "展示虚构产品结构和合成卖点"},
            {"order": 5, "label": "行动 / 体验验证", "duration_seconds": {"min": 15, "max": 18}, "goal": "通过动作验证测试流程", "shots": ["依次归档A类", "依次归档B类", "依次归档C类"], "rough_voiceover": ["每放入一张卡片，就同步核对一次编号。"], "on_screen_text": ["合成步骤验证"], "brand_presence": "模块盒持续用于测试演示"},
            {"order": 6, "label": "结果 / 感受回收", "duration_seconds": {"min": 8, "max": 10}, "goal": "展示合成测试结果", "shots": ["展示三个分区", "显示核对清单"], "rough_voiceover": ["三类合成样本都已归位，测试流程完成。"], "on_screen_text": ["合成结果已核对"], "brand_presence": "保留虚构产品全景"},
            {"order": 7, "label": "收尾互动", "duration_seconds": {"min": 6, "max": 8}, "goal": "结束自动化测试样例", "shots": ["关闭核对清单", "显示测试结束卡"], "rough_voiceover": ["这个虚构示例只用于验证工作流。"], "on_screen_text": ["测试结束"], "brand_presence": None},
        ],
        "shot_rows": [
            {"shot_no": 1, "section_order": 1, "duration_seconds": 7, "scene": "展示三类测试卡片和空工作台", "framing": "固定中景", "rough_voiceover": "以下内容完全由虚构测试数据构成。", "on_screen_text": ["合成演示"], "audio_or_notes": ["测试环境声"], "brand_presence": None},
            {"shot_no": 2, "section_order": 2, "duration_seconds": 11, "scene": "混合卡片并显示重复编号", "framing": "俯拍近景", "rough_voiceover": "三类卡片混在一起时，测试步骤很难核对。", "on_screen_text": ["合成问题：分类混乱"], "audio_or_notes": [], "brand_presence": None},
            {"shot_no": 3, "section_order": 3, "duration_seconds": 9, "scene": "按颜色分组并添加标签", "framing": "俯拍中景", "rough_voiceover": "先按颜色分组，再核对编号。", "on_screen_text": ["先分类，再核对"], "audio_or_notes": [], "brand_presence": "测试用模块盒进入画面"},
            {"shot_no": 4, "section_order": 4, "duration_seconds": 11, "scene": "拆分三个模块并分别放入卡片", "framing": "结构特写转中景", "rough_voiceover": "可拆分结构让三类测试样本保持独立。", "on_screen_text": ["可拆分"], "audio_or_notes": ["合成卖点随动作出现"], "brand_presence": "展示虚构产品结构"},
            {"shot_no": 5, "section_order": 5, "duration_seconds": 16, "scene": "依次归档A/B/C三类卡片", "framing": "俯拍、标签特写、固定中景", "rough_voiceover": "每放入一张卡片，就同步核对一次编号。", "on_screen_text": ["合成步骤验证"], "audio_or_notes": ["不作永久效果承诺"], "brand_presence": "模块盒持续用于测试演示"},
            {"shot_no": 6, "section_order": 6, "duration_seconds": 9, "scene": "展示三个分区和核对清单", "framing": "固定中景", "rough_voiceover": "三类合成样本都已归位，测试流程完成。", "on_screen_text": ["合成结果已核对"], "audio_or_notes": [], "brand_presence": "保留虚构产品全景"},
            {"shot_no": 7, "section_order": 7, "duration_seconds": 7, "scene": "关闭核对清单并显示结束卡", "framing": "固定全景", "rough_voiceover": "这个虚构示例只用于验证工作流。", "on_screen_text": ["测试结束"], "audio_or_notes": ["合成收尾"], "brand_presence": None},
        ],
        "brief_coverage": ["已覆盖：可拆分", "已规避：保证永久有效"], "creator_fit_checks": ["先解释合成问题再给测试步骤"], "assumptions": [], "risks": [], "open_questions": [],
    })
    return finalize_outline(state, prepared.run["run_id"], candidate)


def test_full_brief_route_outline_copy_workflow_and_workbench(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, brief = _project_with_brief(tmp_path)
    assert brief.object["facts"] and brief.object["inferences"]
    stored_source = state / brief.object["source_files"][0]["path"]
    assert stored_source.is_file() and stored_source.name.endswith("brief.md")
    routes = _routes(state, project.object["project_id"], finalized.baseline)
    assert routes.run["status"] == "waiting_for_user"
    outline = _outline(state, project.object["project_id"], routes.object["routes"][0])
    feedback = record_internal_feedback(state, project.object["project_id"], outline.object["outline_id"], "第二段补一个全身跑动镜头")
    revision_task = prepare_outline(state, project.object["project_id"], feedback_id=feedback.object["feedback_id"])
    assert revision_task.object["inputs"]["previous_outline_path"].endswith(f"{outline.object['outline_id']}.json")
    submission = create_submission(state, project.object["project_id"], track="outline", source_object_id=outline.object["outline_id"])
    assert submission.object["submitted_content"]["target_duration_seconds"] == 70
    assert submission.object["submitted_content"]["shot_rows"] == outline.object["shot_rows"]
    approval = approve_submission(state, project.object["project_id"], submission.object["submission_id"], confirmation_source="合成测试确认")
    assert approval.object["track"] == "outline"
    copy_task = prepare_publication_copy(state, project.object["project_id"])
    assert "baseline_path" not in copy_task.object["inputs"]
    creator_context = read_json(Path(copy_task.object["inputs"]["creator_context_path"]))
    assert creator_context["baseline"]["baseline_id"] == finalized.baseline["baseline_id"]
    assert "playbook" in creator_context
    copy_candidate = _private_candidate(copy_task, "copy-candidate.json", {"schema_version": 1, "title_options": ["三类测试卡片怎么归位"], "body": "这是一段用于验证归档流程的合成测试正文。", "tags": ["合成样例", "流程测试"], "brief_coverage": ["可拆分已覆盖", "禁用词未出现"], "risks": []})
    copy = finalize_publication_copy(state, copy_task.run["run_id"], copy_candidate)
    copy_feedback = record_publication_copy_feedback(
        state, project.object["project_id"], copy.object["copy_id"],
        "正文增加少量有语义的 Emoji",
    )
    copy_revision = prepare_publication_copy(
        state, project.object["project_id"], feedback_id=copy_feedback.object["feedback_id"],
    )
    assert copy_revision.object["inputs"]["feedback_path"].endswith(f"{copy_feedback.object['feedback_id']}.json")
    copy_submission = create_submission(state, project.object["project_id"], track="publication_copy", source_object_id=copy.object["copy_id"])
    approve_submission(state, project.object["project_id"], copy_submission.object["submission_id"])
    write_json_atomic(state / "projects" / project.object["project_id"] / "backtests" / "backtest_demo.json", {
        "schema_version": 1,
        "backtest_id": "backtest_demo",
        "project_id": project.object["project_id"],
        "outline_id": outline.object["outline_id"],
        "review_status": "pending_review",
        "verdict": "策略通过，交付颗粒度待补强",
        "summary": "路线合理，但需要逐镜头行。",
        "sources": [{"label": "历史脚本", "reference": "final.docx", "note": None}],
        "scorecard": [{"dimension": "结构", "generated": "7段", "historical": "20镜", "assessment": "需拆行"}],
        "key_matches": ["路线一致"],
        "material_gaps": [{"priority": "high", "gap": "缺少逐镜头行", "evidence": "历史脚本20镜", "recommendation": "增加shot rows"}],
        "deliberate_differences": ["不学习补偿式措辞"],
        "performance_context": {"captured_after_hours": 14.4, "metrics": {"likes": 10}, "reference_benchmark": ["观察窗口不一致"], "interpretation": "只作早期事实"},
        "learning_candidates": {"keep": ["保留路线"], "change": ["增加shot rows"], "do_not_learn": ["不复制答案"]},
        "next_step": "等待用户Review",
        "created_at": "2026-08-14T00:00:00Z",
    })
    workbench = build_workbench(state, tmp_path / "workbench")
    assert workbench.project_count == 1
    project_pages = tmp_path / "workbench" / "projects" / project.object["project_id"]
    assert (project_pages / "brief.html").is_file()
    assert (project_pages / "routes.html").is_file()
    outline_html = project_pages / "outlines" / f"{outline.object['outline_id']}.html"
    rendered_outline = outline_html.read_text(encoding="utf-8")
    assert "Outline Preview" in rendered_outline
    assert "秒数" in rendered_outline and "镜头" in rendered_outline and "大致口播" in rendered_outline
    assert "第一层：7 段叙事骨架" in rendered_outline
    assert "第二层：逐镜头 Shot Rows" in rendered_outline
    assert "拍摄场景 / 画面内容" in rendered_outline and "景别 / 机位" in rendered_outline
    assert "目标 70 秒" in rendered_outline and "预计范围 63–78 秒" in rendered_outline
    assert (project_pages / "copy" / f"{copy.object['copy_id']}.html").is_file()
    rendered_copy = (project_pages / "copy" / f"{copy.object['copy_id']}.html").read_text(encoding="utf-8")
    assert "字符数用于发布前人工检查" in rendered_copy
    assert "风险与发布前确认" in rendered_copy
    backtest_html = project_pages / "backtests" / "backtest_demo.html"
    assert backtest_html.is_file()
    assert "大纲盲测复盘" in backtest_html.read_text(encoding="utf-8")
    assert "逐镜头" in backtest_html.read_text(encoding="utf-8")


def test_project_rejects_unconfirmed_baseline(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"; analyzed, finalized = _analyze_and_finalize(state)
    with pytest.raises(WorkflowError, match="人工确认"):
        create_project(state, creator_id=analyzed.creator["creator_id"], baseline_id=finalized.baseline["baseline_id"], title="项目", brand="品牌", product="产品")


def test_outline_rejects_inconsistent_shot_rows(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    routes = _routes(state, project.object["project_id"], finalized.baseline)
    outline = _outline(state, project.object["project_id"], routes.object["routes"][0])
    prepared = prepare_outline(state, project.object["project_id"])
    candidate = {
        key: outline.object[key]
        for key in (
            "schema_version", "working_titles", "hooks", "target_duration_seconds",
            "estimated_duration_seconds", "sections", "shot_rows", "brief_coverage",
            "creator_fit_checks", "assumptions", "risks", "open_questions",
        )
    }
    candidate["shot_rows"] = [dict(item) for item in candidate["shot_rows"]]
    candidate["shot_rows"][1]["shot_no"] = 8
    candidate_path = _private_candidate(prepared, "outline-candidate.json", candidate)
    with pytest.raises(WorkflowError, match="连续编号"):
        finalize_outline(state, prepared.run["run_id"], candidate_path)


def test_routes_must_be_materially_different(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    prepared = prepare_routes(state, project.object["project_id"], count=2)
    evidence_id = finalized.baseline["claims"][0]["evidence_refs"][0]["evidence_id"]
    same = {"premise": "A", "conflict": "相同", "scene": "相同", "emotional_arc": ["相同"], "product_role": "相同", "creator_fit": {"reason": "有证据", "evidence_refs": [evidence_id]}, "brief_coverage": [], "risks": [], "recommended": False}
    candidate = _private_candidate(prepared, "routes-candidate.json", {"schema_version": 1, "rationale": "", "routes": [{**same, "recommended": True}, {**same, "premise": "B"}]})
    with pytest.raises(WorkflowError, match="路线差异不足"):
        finalize_routes(state, prepared.run["run_id"], candidate)


def test_routes_default_to_one_recommended_direction(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    prepared = prepare_routes(state, project.object["project_id"])
    assert prepared.run["inputs"]["route_count"] == 1
    assert prepared.object["inputs"]["route_count"] == 1
    assert prepared.object["instructions"][0].startswith("严格生成 1 条路线")
    evidence_id = finalized.baseline["claims"][0]["evidence_refs"][0]["evidence_id"]
    candidate = _private_candidate(prepared, "routes-candidate.json", {
        "schema_version": 1, "rationale": "Brief 已明确主题，直接推进一条路线。", "routes": [{
            "premise": "先把三类测试卡片分开", "conflict": "颜色和编号混在一起", "scene": "合成工作台A",
            "emotional_arc": ["混乱", "分类", "完成"], "product_role": "提供可拆分分区",
            "creator_fit": {"reason": "符合本人表达顺序", "evidence_refs": [evidence_id]},
            "brief_coverage": ["可拆分"], "risks": [], "recommended": True,
        }]})
    finalized_routes = finalize_routes(state, prepared.run["run_id"], candidate)
    assert len(finalized_routes.object["routes"]) == 1


def test_route_finalize_rejects_count_drift(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    prepared = prepare_routes(state, project.object["project_id"])
    evidence_id = finalized.baseline["claims"][0]["evidence_refs"][0]["evidence_id"]
    route = {"premise": "A", "conflict": "A", "scene": "A", "emotional_arc": ["A"], "product_role": "A", "creator_fit": {"reason": "有证据", "evidence_refs": [evidence_id]}, "brief_coverage": [], "risks": [], "recommended": True}
    candidate = _private_candidate(prepared, "routes-candidate.json", {"schema_version": 1, "rationale": "", "routes": [route, {**route, "premise": "B", "recommended": False}]})
    with pytest.raises(WorkflowError, match="严格包含 1 条"):
        finalize_routes(state, prepared.run["run_id"], candidate)


def test_backtest_route_context_excludes_published_note_evidence(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    evidence_id = finalized.baseline["claims"][0]["evidence_refs"][0]["evidence_id"]
    prepared = prepare_routes(
        state, project.object["project_id"], exclude_evidence_ids=[evidence_id]
    )
    context = read_json(Path(prepared.object["inputs"]["creator_context_path"]))
    assert context["backtest"]["excluded_evidence_ids"] == [evidence_id]
    assert all(
        item.get("evidence_id") != evidence_id
        for claim in context["baseline"].get("claims", [])
        for item in claim.get("evidence_refs", [])
    )
    candidate = _private_candidate(prepared, "routes-candidate.json", {
        "schema_version": 1, "rationale": "回测", "routes": [{
            "premise": "A", "conflict": "A", "scene": "A", "emotional_arc": ["A"],
            "product_role": "A", "creator_fit": {"reason": "错误引用", "evidence_refs": [evidence_id]},
            "brief_coverage": [], "risks": [], "recommended": True,
        }],
    })
    with pytest.raises(WorkflowError, match="不属于绑定 Baseline"):
        finalize_routes(state, prepared.run["run_id"], candidate)


def test_backtest_exclusion_carries_from_routes_into_outline_context(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    refs = list(dict.fromkeys(
        item["evidence_id"]
        for claim in finalized.baseline["claims"]
        for item in claim.get("evidence_refs", [])
    ))
    assert len(refs) >= 2
    excluded_id, allowed_id = refs[:2]
    prepared = prepare_routes(state, project.object["project_id"], exclude_evidence_ids=[excluded_id])
    candidate = _private_candidate(prepared, "routes-candidate.json", {
        "schema_version": 1, "rationale": "隔离已发布案例后生成", "routes": [{
            "premise": "新路线", "conflict": "新冲突", "scene": "新场景", "emotional_arc": ["开始", "变化"],
            "product_role": "自然进入", "creator_fit": {"reason": "使用未排除证据", "evidence_refs": [allowed_id]},
            "brief_coverage": ["可拆分"], "risks": [], "recommended": True,
        }],
    })
    route_set = finalize_routes(state, prepared.run["run_id"], candidate)
    select_route(state, project.object["project_id"], route_set.object["routes"][0])
    outline_task = prepare_outline(state, project.object["project_id"])
    context = read_json(Path(outline_task.object["inputs"]["creator_context_path"]))
    assert context["backtest"]["excluded_evidence_ids"] == [excluded_id]
    assert all(
        item.get("evidence_id") != excluded_id
        for source in (context["baseline"], context["playbook"])
        if source is not None
        for claim in source.get("claims", [])
        for item in claim.get("evidence_refs", [])
    )
    assert "baseline_path" not in outline_task.object["inputs"]


def test_backtest_exclusion_carries_into_publication_copy_context(tmp_path: Path) -> None:
    state, _analyzed, finalized, project, _brief = _project_with_brief(tmp_path)
    routes = _routes(state, project.object["project_id"], finalized.baseline)
    outline = _outline(state, project.object["project_id"], routes.object["routes"][0])
    submission = create_submission(
        state, project.object["project_id"], track="outline",
        source_object_id=outline.object["outline_id"],
    )
    approve_submission(state, project.object["project_id"], submission.object["submission_id"])
    excluded_id = finalized.baseline["claims"][0]["evidence_refs"][0]["evidence_id"]
    stored_project = read_json(project.path)
    stored_project["backtest_excluded_evidence_ids"] = [excluded_id]
    write_json_atomic(project.path, stored_project)

    copy_task = prepare_publication_copy(state, project.object["project_id"])
    context = read_json(Path(copy_task.object["inputs"]["creator_context_path"]))
    assert context["backtest"]["excluded_evidence_ids"] == [excluded_id]
    filtered_sources = {"baseline": context["baseline"], "playbook": context["playbook"]}
    assert excluded_id not in str(filtered_sources)
    assert all(
        item.get("evidence_id") != excluded_id
        for source in (context["baseline"], context["playbook"])
        if source is not None
        for claim in source.get("claims", [])
        for item in claim.get("evidence_refs", [])
    )
    assert "baseline_path" not in copy_task.object["inputs"]
