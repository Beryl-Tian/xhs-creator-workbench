from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_collector import SyntheticSource

from xhs_agent.creator.baseline import BaselineCandidateError
from xhs_agent.creator.collector import CollectionOptions
from xhs_agent.creator.review import attach_longitudinal_analysis, calibrate_baseline
from xhs_agent.creator.service import (
    analyze_and_store_creator, finalize_baseline_candidate, prepare_commercial_revision,
)
from xhs_agent.storage import read_json, write_json_atomic


class EligibleSyntheticSource(SyntheticSource):
    def get_user_posted_notes(self, account, *, cursor=""):
        return {"data": {
            "notes": [{
                "note_id": f"note-{number}",
                "note_card": {
                    "display_title": f"{number}个示例方法",
                    "interact_info": {"liked_count": str(number * 10)},
                },
            } for number in range(1, 13)],
            "has_more": False,
            "cursor": "",
        }}

    def get_note_detail(self, note_id, *, note_type="normal"):
        number = int(note_id.split("-")[1])
        commercial = "品牌合作" if number in (11, 12) else ""
        return {"data": {"note": {
            "note_id": note_id,
            "title": f"{number}个示例方法{commercial}",
            "desc": f"我认为先解释问题，再给出步骤。第{number}次公开示例 #示例",
            "time": 1_700_000_000 + number * 86_400,
            "interact_info": {
                "liked_count": number * 10,
                "collected_count": number,
                "comment_count": 2,
            },
        }}}


def _candidate_for(result) -> dict:
    evidence_path = Path(result.run["outputs"]["evidence_path"])
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    note_refs = [item["evidence_id"] for item in evidence if item["kind"] == "note"]
    collection_ref = next(
        item["evidence_id"] for item in evidence if item["kind"] == "collection_quality"
    )
    return {
        "schema_version": 1,
        "creator_id": result.creator["creator_id"],
        "run_id": result.run["run_id"],
        "summary": {
            "one_line_positioning": {
                "statement": "用个人经验解释问题并给出可执行步骤的示例账号",
                "evidence_refs": note_refs[:3], "limitations": ["仅限公开内容"]
            },
            "audience": {
                "statement": "希望快速理解并执行方法的读者",
                "evidence_refs": note_refs[:1], "limitations": ["评论样本有限"]
            },
            "content_identity": {
                "statement": "第一人称经验加步骤化解释",
                "evidence_refs": note_refs[:3], "limitations": []
            },
            "commercial_identity": {
                "statement": "商业候选仍沿用经验到方法的内容顺序，待人工确认",
                "evidence_refs": note_refs[-2:], "limitations": ["商业属性待确认"]
            },
        },
        "findings": [
            {
                "category": "cognition",
                "finding_type": "core_belief",
                "statement": "解决问题前应先解释原因，再提供步骤。",
                "epistemic_status": "inferred",
                "confidence": 0.95,
                "evidence_refs": note_refs[:3],
                "counter_evidence_refs": [],
                "applicable_to": ["commercial_route", "commercial_outline"],
                "limitations": ["仅来自当前公开样本"],
            },
            {
                "category": "organic",
                "finding_type": "title_formula",
                "statement": "标题常用数字加方法主题的结构。",
                "epistemic_status": "observed",
                "confidence": 0.9,
                "evidence_refs": note_refs[:2],
                "counter_evidence_refs": [],
                "applicable_to": ["publication_copy"],
                "limitations": [],
            },
            {
                "category": "visual",
                "finding_type": "unknown_visual",
                "statement": "当前没有图片和镜头 Evidence，不能形成视觉规律。",
                "epistemic_status": "observed",
                "confidence": 0.95,
                "evidence_refs": [collection_ref],
                "counter_evidence_refs": [],
                "applicable_to": ["review"],
                "limitations": ["没有采集媒体"],
            },
        ],
        "missing_dimensions": ["图片构图与视频镜头"],
        "human_review_questions": ["两篇商业候选是否均为已报备合作？"],
        "limitations": ["公开内容不等于本人全部真实想法"],
    }


def _analyze_and_finalize(state: Path):
    analyzed = analyze_and_store_creator(
        EligibleSyntheticSource(),
        "synthetic-user",
        CollectionOptions(sample_size=12, comment_note_limit=1, comments_per_note=1),
        state,
    )
    candidate_path = Path(analyzed.run["outputs"]["candidate_output_path"])
    write_json_atomic(candidate_path, _candidate_for(analyzed))
    finalized = finalize_baseline_candidate(state, analyzed.run["run_id"], candidate_path)
    return analyzed, finalized


def test_analysis_creates_task_before_baseline(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    analyzed = analyze_and_store_creator(
        EligibleSyntheticSource(),
        "synthetic-user",
        CollectionOptions(sample_size=12, comment_note_limit=1, comments_per_note=1),
        state,
    )
    assert analyzed.run["status"] == "waiting_for_agent"
    assert analyzed.run["outputs"]["distillation_gate"] == "ready"
    assert analyzed.task_path.is_file()
    assert not (analyzed.creator_root / "baselines").exists()


def test_finalize_versions_baselines_and_caps_confidence(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    first_analyzed, first = _analyze_and_finalize(state)
    _second_analyzed, second = _analyze_and_finalize(state)
    assert first.baseline["version"] == 1
    assert second.baseline["version"] == 2
    assert first.baseline["review_status"] == "pending_confirmation"
    assert first.baseline["claims"][0]["confidence"] == 0.65
    assert first.baseline["validation_notes"]
    assert len(list((first_analyzed.creator_root / "baselines").glob("*.json"))) == 2
    registry = json.loads((state / "registry.json").read_text(encoding="utf-8"))
    assert registry["creators"][0]["latest_candidate_baseline_version"] == 2


def test_claims_reference_existing_note_evidence(tmp_path: Path) -> None:
    analyzed, finalized = _analyze_and_finalize(tmp_path / ".xhs-agent")
    evidence = json.loads(Path(analyzed.run["outputs"]["evidence_path"]).read_text(encoding="utf-8"))
    evidence_ids = {item["evidence_id"] for item in evidence}
    for claim in finalized.baseline["claims"]:
        assert claim["evidence_refs"]
        assert all(ref["evidence_id"] in evidence_ids for ref in claim["evidence_refs"])


def test_core_belief_requires_three_distinct_note_evidence(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    analyzed = analyze_and_store_creator(
        EligibleSyntheticSource(), "synthetic-user", CollectionOptions(sample_size=12), state
    )
    candidate = _candidate_for(analyzed)
    candidate["findings"][0]["evidence_refs"] = candidate["findings"][0]["evidence_refs"][:2]
    candidate_path = Path(analyzed.run["outputs"]["candidate_output_path"])
    write_json_atomic(candidate_path, candidate)
    with pytest.raises(BaselineCandidateError, match="至少需要 3 篇"):
        finalize_baseline_candidate(state, analyzed.run["run_id"], candidate_path)
    run = json.loads((state / "runs" / f"{analyzed.run['run_id']}.json").read_text(encoding="utf-8"))
    assert run["status"] == "waiting_for_agent"
    assert run["error_code"] == "baseline_candidate_invalid"


def test_commercial_confirmation_creates_immutable_revision_run(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    analyzed = analyze_and_store_creator(
        EligibleSyntheticSource(), "synthetic-user", CollectionOptions(sample_size=12), state
    )
    original_analysis_path = Path(analyzed.run["outputs"]["analysis_path"])
    original_analysis = json.loads(original_analysis_path.read_text(encoding="utf-8"))
    revised = prepare_commercial_revision(
        state,
        analyzed.run["run_id"],
        ["note-10", "note-11", "note-12"],
        note="三篇均已人工核对",
    )
    assert revised.run["run_id"] != analyzed.run["run_id"]
    assert revised.run["operation"] == "creator.baseline.revise"
    assert revised.analysis["segments"]["commercial_detection"] == "human_confirmed"
    assert revised.analysis["segments"]["commercial_candidates"]["count"] == 3
    assert json.loads(original_analysis_path.read_text(encoding="utf-8")) == original_analysis
    assert revised.task_path.is_file()
    assert revised.confirmation_path.is_file()
    assert Path(revised.run["outputs"]["evidence_path"]).is_file()


def test_human_calibration_versions_goal_context_without_rewriting_evidence(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    _analyzed, finalized = _analyze_and_finalize(state)
    source_claims = json.loads(finalized.baseline_path.read_text(encoding="utf-8"))["claims"]
    calibrated = calibrate_baseline(
        state,
        finalized.baseline["baseline_id"],
        desired_positioning="合成目标定位：清晰解释与可执行步骤",
        target_audience="虚构目标受众：需要结构化示例的测试用户",
        accepted_question_numbers=[1],
    )
    assert calibrated.baseline["version"] == 2
    assert calibrated.baseline["source_baseline_id"] == finalized.baseline["baseline_id"]
    assert calibrated.baseline["claims"] == source_claims
    assert [item["context_type"] for item in calibrated.baseline["human_context"]] == [
        "desired_positioning", "target_audience"
    ]
    assert calibrated.baseline["human_review_questions"] == []
    assert json.loads(finalized.baseline_path.read_text(encoding="utf-8"))["review_status"] == "superseded"

    second = calibrate_baseline(
        state,
        calibrated.baseline["baseline_id"],
        commercial_guardrail="合成商业约束：强制展示只作为测试例外",
        rejected_question_numbers=[],
    )
    assert second.baseline["version"] == 3
    assert len(second.baseline["human_context"]) == 3
    assert second.baseline["human_context"][-1]["context_type"] == "commercial_guardrail"


def test_attach_longitudinal_analysis_versions_without_rewriting_claims(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    analyzed, finalized = _analyze_and_finalize(state)
    history_run_id = "run_history"
    history_root = analyzed.creator_root / "source" / "runs" / history_run_id
    history_analysis_path = history_root / "analysis.json"
    write_json_atomic(history_analysis_path, {
        "sample_count": 60,
        "longitudinal": {"status": "ready", "dated_note_count": 60},
    })
    write_json_atomic(state / "runs" / f"{history_run_id}.json", {
        "run_id": history_run_id,
        "outputs": {
            "creator_id": analyzed.creator["creator_id"],
            "analysis_path": str(history_analysis_path),
        },
    })
    attached = attach_longitudinal_analysis(
        state, finalized.baseline["baseline_id"], history_run_id
    )
    assert attached.baseline["version"] == 2
    assert attached.baseline["longitudinal_run_id"] == history_run_id
    assert attached.baseline["claims"] == finalized.baseline["claims"]
    assert read_json(finalized.baseline_path)["review_status"] == "superseded"


def test_finding_category_must_match_type(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    analyzed = analyze_and_store_creator(
        EligibleSyntheticSource(), "synthetic-user", CollectionOptions(sample_size=12), state
    )
    candidate = _candidate_for(analyzed)
    candidate["findings"][0]["category"] = "commercial"
    candidate_path = Path(analyzed.run["outputs"]["candidate_output_path"])
    write_json_atomic(candidate_path, candidate)
    with pytest.raises(BaselineCandidateError, match="不能归入"):
        finalize_baseline_candidate(state, analyzed.run["run_id"], candidate_path)


def test_quality_gate_blocks_tiny_sample_finalization(tmp_path: Path) -> None:
    state = tmp_path / ".xhs-agent"
    analyzed = analyze_and_store_creator(
        SyntheticSource(), "synthetic-user", CollectionOptions(sample_size=2), state
    )
    candidate_path = Path(analyzed.run["outputs"]["candidate_output_path"])
    write_json_atomic(candidate_path, {"schema_version": 1})
    with pytest.raises(BaselineCandidateError, match="质量闸门"):
        finalize_baseline_candidate(state, analyzed.run["run_id"], candidate_path)


def test_failed_collection_keeps_recoverable_run(tmp_path: Path) -> None:
    class FailingSource(SyntheticSource):
        def get_user_info(self, account):
            raise RuntimeError("synthetic upstream failure")

    state = tmp_path / ".xhs-agent"
    with pytest.raises(RuntimeError):
        analyze_and_store_creator(
            FailingSource(), "synthetic-user", CollectionOptions(sample_size=2), state
        )
    run_paths = list((state / "runs").glob("*.json"))
    assert len(run_paths) == 1
    run = json.loads(run_paths[0].read_text(encoding="utf-8"))
    assert run["status"] == "failed"
    assert run["steps"][0]["status"] == "failed"
    assert run["recovery_hint"]
