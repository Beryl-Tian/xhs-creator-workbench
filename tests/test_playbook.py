from pathlib import Path

import pytest

from xhs_agent.creator.playbook import PlaybookError, confirm_playbook, finalize_playbook, prepare_playbook
from xhs_agent.renderers.workbench import build_workbench
from xhs_agent.storage import read_json, write_json_atomic


def _candidate(creator_id: str, baseline_id: str) -> dict:
    claim_ids = ["claim_demo"]
    example = {"text": "合成证据示例", "evidence_id": "ev_demo"}
    return {
        "schema_version": 1, "creator_id": creator_id, "baseline_id": baseline_id,
        "core_thesis": {"statement": "合成主题：先解释再执行", "claim_ids": claim_ids},
        "current_content_axes": [
            {"name": "示例轴A", "role": "主轴", "use_when": "合成场景A", "claim_ids": claim_ids},
            {"name": "示例轴B", "role": "主轴", "use_when": "合成场景B", "claim_ids": claim_ids},
        ],
        "legacy_capabilities": [{"name": "历史示例能力", "current_role": "仅供测试", "evidence_refs": [example]}],
        "route_patterns": [
            {"name": f"路线{i}", "use_when": "适用", "premise": "前提", "structure": ["状态", "行动", "回收"], "product_entry": "行动后", "claim_ids": claim_ids}
            for i in range(3)
        ],
        "title_formulas": [
            {"formula": f"公式{i}", "use_when": "适用", "examples": [example], "claim_ids": claim_ids}
            for i in range(3)
        ],
        "body_templates": [
            {"name": f"结构{i}", "use_when": "适用", "steps": ["状态", "行动", "回收"], "claim_ids": claim_ids}
            for i in range(2)
        ],
        "language_kit": {"keep": ["口语"], "avoid": ["品牌腔"], "cta": ["一起去"], "phrase_examples": [example]},
        "commercial_rules": {"default_path": ["自然进入"], "exception_path": ["强约束才例外"], "checklist": ["真实动作"], "claim_ids": claim_ids},
        "audience_translation": {"observed_audience": "合成观察受众", "desired_audience": "虚构测试受众", "content_signals": ["示例信号"], "claim_ids": claim_ids},
        "review_checklist": [f"检查{i}" for i in range(5)],
        "limitations": ["没有视频画面证据"],
    }


def _state(tmp_path: Path) -> tuple[Path, str, str]:
    state = tmp_path / ".xhs-agent"
    creator_id = "creator_demo"
    baseline_id = "baseline_demo_v1"
    root = state / "creators" / creator_id
    write_json_atomic(root / "creator.json", {"schema_version": 1, "creator_id": creator_id, "display_name": "示例博主"})
    write_json_atomic(root / "baselines" / f"{baseline_id}.json", {
        "schema_version": 1, "baseline_id": baseline_id, "creator_id": creator_id,
        "source_run_id": "run_source", "version": 1, "review_status": "confirmed",
        "claims": [{"claim_id": "claim_demo"}], "summary": {"one_line_positioning": {"statement": "示例"}},
        "sample_window": {"sample_count": 1}, "created_at": "2026-01-01T00:00:00Z",
    })
    write_json_atomic(root / "evidence" / "run_source.json", [{"evidence_id": "ev_demo", "kind": "note", "content_excerpt": "合成证据示例"}])
    write_json_atomic(root / "source" / "runs" / "run_source" / "analysis.json", {})
    return state, creator_id, baseline_id


def test_playbook_is_versioned_and_stops_for_human_review(tmp_path: Path) -> None:
    state, creator_id, baseline_id = _state(tmp_path)
    prepared = prepare_playbook(state, baseline_id)
    candidate_path = Path(prepared.run["outputs"]["candidate_output_path"])
    write_json_atomic(candidate_path, _candidate(creator_id, baseline_id))
    result = finalize_playbook(state, prepared.run["run_id"], candidate_path)
    assert result.playbook["review_status"] == "pending_confirmation"
    assert result.run["status"] == "waiting_for_user"
    confirmed = confirm_playbook(state, result.playbook["playbook_id"])
    assert confirmed.playbook["review_status"] == "confirmed"
    built = build_workbench(state, tmp_path / "workbench")
    html = (tmp_path / "workbench" / "creators" / creator_id / "playbooks" / f"{result.playbook['playbook_id']}.html").read_text()
    assert "创作执行指南" in html
    assert "路线模板" in html
    assert built.warnings == []


def test_playbook_rejects_untraceable_evidence(tmp_path: Path) -> None:
    state, creator_id, baseline_id = _state(tmp_path)
    prepared = prepare_playbook(state, baseline_id)
    candidate = _candidate(creator_id, baseline_id)
    candidate["title_formulas"][0]["examples"][0]["evidence_id"] = "ev_invented"
    candidate_path = Path(prepared.run["outputs"]["candidate_output_path"])
    write_json_atomic(candidate_path, candidate)
    with pytest.raises(PlaybookError, match="无法追溯"):
        finalize_playbook(state, prepared.run["run_id"], candidate_path)
