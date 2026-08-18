from __future__ import annotations

import json
from pathlib import Path

from xhs_agent.cli import _info_payload, _planned_commands, build_parser


def test_info_paths_stay_inside_workspace(tmp_path: Path) -> None:
    payload = _info_payload(tmp_path)
    assert payload["paths"]["state"] == str(tmp_path / ".xhs-agent")
    assert payload["paths"]["workbench"] == str(tmp_path / "workbench")
    assert payload["privacy"]["token_location"] == "environment_or_user_config"


def test_info_payload_is_json_serializable(tmp_path: Path) -> None:
    json.dumps(_info_payload(tmp_path), ensure_ascii=False)
    assert _info_payload(tmp_path)["status"] == "final_archive_learning_available"


def test_planned_commands_include_two_brand_review_tracks() -> None:
    commands = _planned_commands()
    assert "brand submit" in commands
    assert "creator baseline-finalize" in commands
    assert "copy generate" in commands
    assert "copy feedback" in commands
    assert "published archive" in commands
    assert "published finalize" in commands


def test_creator_analyze_parser_uses_reviewed_sample_sizes(tmp_path: Path) -> None:
    args = build_parser().parse_args([
        "creator", "analyze", "--account", "synthetic-user",
        "--sample-size", "50", "--workspace", str(tmp_path), "--json",
    ])
    assert args.creator_command == "analyze"
    assert args.sample_size == 50
    assert args.workspace == tmp_path


def test_baseline_finalize_parser(tmp_path: Path) -> None:
    candidate = tmp_path / ".xhs-agent" / "candidate.json"
    args = build_parser().parse_args([
        "creator", "baseline-finalize", "--run-id", "run_synthetic",
        "--candidate", str(candidate), "--workspace", str(tmp_path), "--json",
    ])
    assert args.creator_command == "baseline-finalize"
    assert args.candidate == candidate


def test_commercial_confirmation_parser(tmp_path: Path) -> None:
    args = build_parser().parse_args([
        "creator", "commercial-confirm", "--source-run-id", "run_source",
        "--note-id", "note-1", "--note-id", "note-2", "--workspace", str(tmp_path),
    ])
    assert args.creator_command == "commercial-confirm"
    assert args.note_ids == ["note-1", "note-2"]


def test_baseline_calibration_parser(tmp_path: Path) -> None:
    args = build_parser().parse_args([
        "creator", "baseline-calibrate", "--baseline-id", "baseline_demo_v1",
        "--desired-positioning", "合成目标定位", "--target-audience", "虚构测试受众",
        "--accept-question", "1", "--accept-question", "4", "--workspace", str(tmp_path),
    ])
    assert args.creator_command == "baseline-calibrate"
    assert args.accepted_questions == [1, 4]

    followup = build_parser().parse_args([
        "creator", "baseline-calibrate", "--baseline-id", "baseline_demo_v2",
        "--commercial-guardrail", "硬广只作例外", "--reject-question", "1",
    ])
    assert followup.rejected_questions == [1]


def test_baseline_attach_history_parser(tmp_path: Path) -> None:
    args = build_parser().parse_args([
        "creator", "baseline-attach-history", "--baseline-id", "baseline_demo_v2",
        "--run-id", "run_history", "--workspace", str(tmp_path),
    ])
    assert args.creator_command == "baseline-attach-history"
    assert args.run_id == "run_history"


def test_playbook_parsers(tmp_path: Path) -> None:
    generated = build_parser().parse_args([
        "creator", "playbook-generate", "--baseline-id", "baseline_demo_v1", "--workspace", str(tmp_path),
    ])
    finalized = build_parser().parse_args([
        "creator", "playbook-finalize", "--run-id", "run_demo", "--candidate", "candidate.json",
    ])
    confirmed = build_parser().parse_args([
        "creator", "playbook-confirm", "--playbook-id", "playbook_demo_v1",
    ])
    assert generated.baseline_id == "baseline_demo_v1"
    assert finalized.candidate == Path("candidate.json")
    assert confirmed.playbook_id == "playbook_demo_v1"


def test_workbench_build_parser(tmp_path: Path) -> None:
    args = build_parser().parse_args([
        "workbench", "build", "--workspace", str(tmp_path), "--json",
    ])
    assert args.workbench_command == "build"
    assert args.workspace == tmp_path


def test_routes_generate_defaults_to_one_and_accepts_explicit_count(tmp_path: Path) -> None:
    default = build_parser().parse_args(["routes", "generate", "--project-id", "project_demo"])
    explicit = build_parser().parse_args(["routes", "generate", "--project-id", "project_demo", "--count", "3"])
    assert default.count == 1
    assert explicit.count == 3
    isolated = build_parser().parse_args([
        "routes", "generate", "--project-id", "project_demo",
        "--exclude-evidence-id", "ev_published",
    ])
    assert isolated.exclude_evidence_ids == ["ev_published"]


def test_published_archive_and_learning_review_parsers(tmp_path: Path) -> None:
    archive = build_parser().parse_args(["published", "archive", "--project-id", "project_demo", "--oral-script", "final.md"])
    review = build_parser().parse_args(["learning", "review", "--project-id", "project_demo", "--candidate-id", "learning_demo", "--decision", "accepted"])
    assert archive.oral_script == Path("final.md")
    assert review.decision == "accepted"
