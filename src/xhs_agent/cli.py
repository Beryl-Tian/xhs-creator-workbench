from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import resolve_paths
from .creator.collector import CollectionOptions
from .creator.baseline import BaselineCandidateError
from .creator.service import analyze_and_store_creator, finalize_baseline_candidate, prepare_commercial_revision
from .creator.review import (
    BaselineReviewError, attach_longitudinal_analysis, calibrate_baseline, confirm_baseline,
)
from .creator.playbook import PlaybookError, confirm_playbook, finalize_playbook, prepare_playbook
from .integrations.tikhub import TikHubClient, TikHubError
from .workbench import rebuild_workbench
from .projects import (
    ExtractionError, WorkflowError, approve_submission, create_project, create_submission,
    finalize_brand_feedback, finalize_brief, finalize_outline, finalize_publication_copy,
    finalize_routes, import_brief, prepare_brand_feedback, prepare_outline,
    prepare_publication_copy, prepare_routes, record_internal_feedback,
    record_publication_copy_feedback, select_route,
    archive_publication, finalize_archive, review_learning,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xhs-agent",
        description="小红书创作工作台的本地运行引擎",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="显示当前引擎和隐私目录配置")
    info.add_argument("--workspace", type=Path, default=Path.cwd())
    info.add_argument("--json", action="store_true", dest="as_json")

    subparsers.add_parser("commands", help="列出后续阶段规划的工作流命令")

    creator = subparsers.add_parser("creator", help="采集并分析博主公开内容")
    creator_commands = creator.add_subparsers(dest="creator_command", required=True)
    analyze = creator_commands.add_parser("analyze", help="建立新版本 Creator Baseline")
    analyze.add_argument("--account", required=True, help="小红书主页分享文本、URL 或账号 ID")
    analyze.add_argument("--sample-size", type=int, choices=(30, 50, 80), default=30)
    analyze.add_argument("--comment-note-limit", type=int, default=20)
    analyze.add_argument("--comments-per-note", type=int, default=20)
    analyze.add_argument("--workspace", type=Path, default=Path.cwd())
    analyze.add_argument("--json", action="store_true", dest="as_json")
    finalize = creator_commands.add_parser(
        "baseline-finalize", help="校验 AI 蒸馏结果并生成待人工确认 Baseline"
    )
    finalize.add_argument("--run-id", required=True)
    finalize.add_argument("--candidate", required=True, type=Path)
    finalize.add_argument("--workspace", type=Path, default=Path.cwd())
    finalize.add_argument("--json", action="store_true", dest="as_json")
    confirm = creator_commands.add_parser("baseline-confirm", help="人工确认一版 Baseline")
    confirm.add_argument("--baseline-id", required=True)
    confirm.add_argument("--note")
    confirm.add_argument("--workspace", type=Path, default=Path.cwd())
    confirm.add_argument("--json", action="store_true", dest="as_json")
    commercial = creator_commands.add_parser(
        "commercial-confirm", help="确认商业笔记并创建新一版 Baseline 蒸馏任务"
    )
    commercial.add_argument("--source-run-id", required=True)
    commercial.add_argument("--note-id", action="append", required=True, dest="note_ids")
    commercial.add_argument("--note")
    commercial.add_argument("--workspace", type=Path, default=Path.cwd())
    commercial.add_argument("--json", action="store_true", dest="as_json")
    calibrate = creator_commands.add_parser(
        "baseline-calibrate", help="用团队确认的目标定位校准并创建新版 Baseline"
    )
    calibrate.add_argument("--baseline-id", required=True)
    calibrate.add_argument("--desired-positioning")
    calibrate.add_argument("--target-audience")
    calibrate.add_argument("--commercial-guardrail")
    calibrate.add_argument("--accept-question", action="append", type=int, default=[], dest="accepted_questions")
    calibrate.add_argument("--reject-question", action="append", type=int, default=[], dest="rejected_questions")
    calibrate.add_argument("--note")
    calibrate.add_argument("--workspace", type=Path, default=Path.cwd())
    calibrate.add_argument("--json", action="store_true", dest="as_json")
    history = creator_commands.add_parser(
        "baseline-attach-history", help="将扩展主页样本的纵向分析绑定为新版 Baseline"
    )
    history.add_argument("--baseline-id", required=True)
    history.add_argument("--run-id", required=True)
    history.add_argument("--workspace", type=Path, default=Path.cwd())
    history.add_argument("--json", action="store_true", dest="as_json")
    playbook_generate = creator_commands.add_parser(
        "playbook-generate", help="从已确认 Baseline 创建 Creator Playbook 蒸馏任务"
    )
    playbook_generate.add_argument("--baseline-id", required=True)
    playbook_generate.add_argument("--workspace", type=Path, default=Path.cwd())
    playbook_generate.add_argument("--json", action="store_true", dest="as_json")
    playbook_finalize = creator_commands.add_parser(
        "playbook-finalize", help="校验 AI 候选并生成待确认 Creator Playbook"
    )
    playbook_finalize.add_argument("--run-id", required=True)
    playbook_finalize.add_argument("--candidate", required=True, type=Path)
    playbook_finalize.add_argument("--workspace", type=Path, default=Path.cwd())
    playbook_finalize.add_argument("--json", action="store_true", dest="as_json")
    playbook_confirm = creator_commands.add_parser("playbook-confirm", help="人工确认 Creator Playbook")
    playbook_confirm.add_argument("--playbook-id", required=True)
    playbook_confirm.add_argument("--note")
    playbook_confirm.add_argument("--workspace", type=Path, default=Path.cwd())
    playbook_confirm.add_argument("--json", action="store_true", dest="as_json")

    project = subparsers.add_parser("project", help="管理品牌合作项目")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_create = project_commands.add_parser("create", help="创建并冻结 Baseline 的项目")
    for name in ("creator-id", "baseline-id", "title", "brand", "product"):
        project_create.add_argument(f"--{name}", required=True)
    project_create.add_argument("--workspace", type=Path, default=Path.cwd())
    project_create.add_argument("--json", action="store_true", dest="as_json")

    brief = subparsers.add_parser("brief", help="导入和结构化品牌 Brief")
    brief_commands = brief.add_subparsers(dest="brief_command", required=True)
    brief_import = brief_commands.add_parser("import")
    brief_import.add_argument("--project-id", required=True); brief_import.add_argument("--file", required=True, type=Path)
    brief_finalize = brief_commands.add_parser("finalize")
    brief_finalize.add_argument("--run-id", required=True); brief_finalize.add_argument("--candidate", required=True, type=Path)
    for command in (brief_import, brief_finalize):
        command.add_argument("--workspace", type=Path, default=Path.cwd()); command.add_argument("--json", action="store_true", dest="as_json")

    routes = subparsers.add_parser("routes", help="生成、校验和选择内容路线")
    route_commands = routes.add_subparsers(dest="routes_command", required=True)
    for name in ("generate", "finalize", "select"):
        command = route_commands.add_parser(name)
        if name != "finalize": command.add_argument("--project-id", required=True)
        if name == "generate":
            command.add_argument("--count", type=int, choices=(1, 2, 3), default=1)
            command.add_argument("--exclude-evidence-id", action="append", default=[], dest="exclude_evidence_ids")
        if name == "finalize": command.add_argument("--run-id", required=True); command.add_argument("--candidate", required=True, type=Path)
        if name == "select": command.add_argument("--route-id", required=True); command.add_argument("--note")
        command.add_argument("--workspace", type=Path, default=Path.cwd()); command.add_argument("--json", action="store_true", dest="as_json")

    outline = subparsers.add_parser("outline", help="生成与修订版本化大纲")
    outline_commands = outline.add_subparsers(dest="outline_command", required=True)
    outline_generate = outline_commands.add_parser("generate"); outline_generate.add_argument("--project-id", required=True); outline_generate.add_argument("--feedback-id")
    outline_finalize = outline_commands.add_parser("finalize"); outline_finalize.add_argument("--run-id", required=True); outline_finalize.add_argument("--candidate", required=True, type=Path)
    outline_feedback = outline_commands.add_parser("feedback"); outline_feedback.add_argument("--project-id", required=True); outline_feedback.add_argument("--outline-id", required=True); outline_feedback.add_argument("--text", required=True)
    for command in (outline_generate, outline_finalize, outline_feedback): command.add_argument("--workspace", type=Path, default=Path.cwd()); command.add_argument("--json", action="store_true", dest="as_json")

    brand = subparsers.add_parser("brand", help="记录品牌提交、反馈和确认")
    brand_commands = brand.add_subparsers(dest="brand_command", required=True)
    submit = brand_commands.add_parser("submit"); submit.add_argument("--project-id", required=True); submit.add_argument("--track", choices=("outline", "publication_copy"), required=True); submit.add_argument("--source-object-id", required=True); submit.add_argument("--file", type=Path)
    feedback = brand_commands.add_parser("feedback"); feedback.add_argument("--project-id", required=True); feedback.add_argument("--submission-id", required=True); feedback.add_argument("--text", required=True)
    feedback_finalize = brand_commands.add_parser("feedback-finalize"); feedback_finalize.add_argument("--run-id", required=True); feedback_finalize.add_argument("--candidate", required=True, type=Path)
    approve = brand_commands.add_parser("approve"); approve.add_argument("--project-id", required=True); approve.add_argument("--submission-id", required=True); approve.add_argument("--source"); approve.add_argument("--note")
    for command in (submit, feedback, feedback_finalize, approve): command.add_argument("--workspace", type=Path, default=Path.cwd()); command.add_argument("--json", action="store_true", dest="as_json")

    copy = subparsers.add_parser("copy", help="生成标题、正文和 Tags")
    copy_commands = copy.add_subparsers(dest="copy_command", required=True)
    copy_generate = copy_commands.add_parser("generate"); copy_generate.add_argument("--project-id", required=True); copy_generate.add_argument("--feedback-id")
    copy_finalize = copy_commands.add_parser("finalize"); copy_finalize.add_argument("--run-id", required=True); copy_finalize.add_argument("--candidate", required=True, type=Path)
    copy_feedback = copy_commands.add_parser("feedback"); copy_feedback.add_argument("--project-id", required=True); copy_feedback.add_argument("--copy-id", required=True); copy_feedback.add_argument("--text", required=True)
    for command in (copy_generate, copy_finalize, copy_feedback): command.add_argument("--workspace", type=Path, default=Path.cwd()); command.add_argument("--json", action="store_true", dest="as_json")

    published = subparsers.add_parser("published", help="归档最终口播脚本与实际发布配文")
    published_commands = published.add_subparsers(dest="published_command", required=True)
    archive = published_commands.add_parser("archive")
    archive.add_argument("--project-id", required=True); archive.add_argument("--oral-script", type=Path); archive.add_argument("--published-copy", type=Path); archive.add_argument("--published-copy-screenshot", type=Path); archive.add_argument("--published-at"); archive.add_argument("--published-url")
    archive_finalize = published_commands.add_parser("finalize")
    archive_finalize.add_argument("--run-id", required=True); archive_finalize.add_argument("--candidate", required=True, type=Path)
    for command in (archive, archive_finalize): command.add_argument("--workspace", type=Path, default=Path.cwd()); command.add_argument("--json", action="store_true", dest="as_json")

    learning = subparsers.add_parser("learning", help="Review 候选经验")
    learning_commands = learning.add_subparsers(dest="learning_command", required=True)
    learning_review = learning_commands.add_parser("review")
    learning_review.add_argument("--project-id", required=True); learning_review.add_argument("--candidate-id", required=True); learning_review.add_argument("--decision", choices=("accepted", "rejected"), required=True); learning_review.add_argument("--note")
    learning_review.add_argument("--workspace", type=Path, default=Path.cwd()); learning_review.add_argument("--json", action="store_true", dest="as_json")

    workbench = subparsers.add_parser("workbench", help="重建只读本地 HTML 工作台")
    workbench_commands = workbench.add_subparsers(dest="workbench_command", required=True)
    build = workbench_commands.add_parser("build", help="从 .xhs-agent 重建全部页面")
    build.add_argument("--workspace", type=Path, default=Path.cwd())
    build.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _info_payload(workspace: Path) -> dict[str, object]:
    paths = resolve_paths(workspace)
    return {
        "name": "xhs-creator-workbench",
        "version": __version__,
        "phase": 5,
        "status": "final_archive_learning_available",
        "paths": {
            "workspace": str(paths.workspace),
            "state": str(paths.state),
            "workbench": str(paths.workbench),
            "user_config": str(paths.user_config),
        },
        "privacy": {
            "state_is_gitignored": True,
            "workbench_is_gitignored": True,
            "token_location": "environment_or_user_config",
        },
    }


def _planned_commands() -> list[str]:
    return [
        "creator analyze",
        "creator baseline-finalize",
        "creator baseline-confirm",
        "creator baseline-calibrate",
        "creator baseline-attach-history",
        "creator commercial-confirm",
        "creator playbook-generate",
        "creator playbook-finalize",
        "creator playbook-confirm",
        "project create",
        "brief import",
        "routes generate",
        "routes finalize",
        "routes select",
        "outline generate",
        "outline finalize",
        "outline feedback",
        "brand submit",
        "brand feedback",
        "brand feedback-finalize",
        "brand approve",
        "copy generate",
        "copy finalize",
        "copy feedback",
        "published archive",
        "published finalize",
        "learning review",
        "baseline promote",
        "workbench build",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "info":
        payload = _info_payload(args.workspace)
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"小红书创作工作台 {payload['version']}（阶段 5 最终归档）")
            print(f"内部状态：{payload['paths']['state']}")
            print(f"本地页面：{payload['paths']['workbench']}")
            print(f"用户配置：{payload['paths']['user_config']}")
        return 0
    if args.command == "commands":
        print("\n".join(_planned_commands()))
        return 0
    if args.command == "creator" and args.creator_command == "analyze":
        paths = resolve_paths(args.workspace)
        try:
            source = TikHubClient.from_config(paths.user_config)
            result = analyze_and_store_creator(
                source,
                args.account,
                CollectionOptions(
                    sample_size=args.sample_size,
                    comment_note_limit=args.comment_note_limit,
                    comments_per_note=args.comments_per_note,
                ),
                paths.state,
            )
        except (TikHubError, RuntimeError, ValueError, OSError) as exc:
            parser = build_parser()
            parser.error(str(exc))
        payload = {
            "status": result.run["status"],
            "run_id": result.run["run_id"],
            "creator_id": result.creator["creator_id"],
            "sample_count": result.analysis["sample_count"],
            "evidence_count": result.evidence_count,
            "creator_root": str(result.creator_root),
            "distillation_gate": result.run["outputs"]["distillation_gate"],
            "distillation_task_path": str(result.task_path),
            "candidate_output_path": result.run["outputs"]["candidate_output_path"],
        }
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("数据底稿和 AI 蒸馏任务已创建。")
            print(f"样本：{payload['sample_count']} 篇；证据：{payload['evidence_count']} 条")
            print(f"质量闸门：{payload['distillation_gate']}")
            print(f"蒸馏任务：{payload['distillation_task_path']}")
            print(f"私有数据目录：{payload['creator_root']}")
        return 0
    if args.command == "creator" and args.creator_command == "baseline-finalize":
        paths = resolve_paths(args.workspace)
        try:
            result = finalize_baseline_candidate(paths.state, args.run_id, args.candidate)
        except (BaselineCandidateError, OSError, ValueError) as exc:
            parser = build_parser()
            parser.error(str(exc))
        payload = {
            "status": "completed",
            "run_id": result.run["run_id"],
            "baseline_id": result.baseline["baseline_id"],
            "baseline_version": result.baseline["version"],
            "review_status": result.baseline["review_status"],
            "baseline_path": str(result.baseline_path),
            "validation_notes": result.baseline["validation_notes"],
        }
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"待确认 Baseline 已创建：{payload['baseline_id']}")
            print(f"文件：{payload['baseline_path']}")
        return 0
    try:
        paths = resolve_paths(getattr(args, "workspace", Path.cwd()))
        result = None
        if args.command == "creator" and args.creator_command == "baseline-confirm":
            reviewed = confirm_baseline(paths.state, args.baseline_id, note=args.note)
            payload = {"status": "completed", "baseline_id": args.baseline_id, "confirmation_id": reviewed.confirmation["confirmation_id"], "confirmation_path": str(reviewed.confirmation_path), "next_step": "project create"}
        elif args.command == "creator" and args.creator_command == "baseline-calibrate":
            calibrated = calibrate_baseline(
                paths.state,
                args.baseline_id,
                desired_positioning=args.desired_positioning,
                target_audience=args.target_audience,
                commercial_guardrail=args.commercial_guardrail,
                accepted_question_numbers=args.accepted_questions,
                rejected_question_numbers=args.rejected_questions,
                note=args.note,
            )
            payload = {
                "status": "completed",
                "baseline_id": calibrated.baseline["baseline_id"],
                "baseline_version": calibrated.baseline["version"],
                "review_status": calibrated.baseline["review_status"],
                "baseline_path": str(calibrated.baseline_path),
                "calibration_path": str(calibrated.calibration_path),
                "remaining_review_questions": calibrated.baseline["human_review_questions"],
            }
        elif args.command == "creator" and args.creator_command == "baseline-attach-history":
            attached = attach_longitudinal_analysis(paths.state, args.baseline_id, args.run_id)
            payload = {
                "status": "completed",
                "baseline_id": attached.baseline["baseline_id"],
                "baseline_version": attached.baseline["version"],
                "review_status": attached.baseline["review_status"],
                "baseline_path": str(attached.baseline_path),
                "longitudinal_link_path": str(attached.link_path),
            }
        elif args.command == "creator" and args.creator_command == "commercial-confirm":
            revised = prepare_commercial_revision(
                paths.state,
                args.source_run_id,
                args.note_ids,
                note=args.note,
            )
            payload = {
                "status": revised.run["status"],
                "run_id": revised.run["run_id"],
                "commercial_count": revised.analysis["segments"]["commercial_candidates"]["count"],
                "organic_count": revised.analysis["segments"]["organic"]["count"],
                "confirmation_path": str(revised.confirmation_path),
                "task_path": str(revised.task_path),
                "candidate_output_path": revised.run["outputs"]["candidate_output_path"],
            }
        elif args.command == "creator" and args.creator_command == "playbook-generate":
            generated = prepare_playbook(paths.state, args.baseline_id)
            payload = {
                "status": generated.run["status"], "run_id": generated.run["run_id"],
                "task_path": str(generated.task_path),
                "candidate_output_path": generated.run["outputs"]["candidate_output_path"],
            }
        elif args.command == "creator" and args.creator_command == "playbook-finalize":
            finalized = finalize_playbook(paths.state, args.run_id, args.candidate)
            payload = {
                "status": finalized.run["status"], "run_id": finalized.run["run_id"],
                "playbook_id": finalized.playbook["playbook_id"],
                "review_status": finalized.playbook["review_status"], "path": str(finalized.playbook_path),
            }
        elif args.command == "creator" and args.creator_command == "playbook-confirm":
            confirmed = confirm_playbook(paths.state, args.playbook_id, note=args.note)
            payload = {"status": "completed", "playbook_id": args.playbook_id, "review_status": "confirmed", "path": str(confirmed.playbook_path)}
        elif args.command == "project" and args.project_command == "create":
            result = create_project(paths.state, creator_id=args.creator_id, baseline_id=args.baseline_id, title=args.title, brand=args.brand, product=args.product)
        elif args.command == "brief" and args.brief_command == "import": result = import_brief(paths.state, args.project_id, args.file)
        elif args.command == "brief" and args.brief_command == "finalize": result = finalize_brief(paths.state, args.run_id, args.candidate)
        elif args.command == "routes" and args.routes_command == "generate": result = prepare_routes(paths.state, args.project_id, count=args.count, exclude_evidence_ids=args.exclude_evidence_ids)
        elif args.command == "routes" and args.routes_command == "finalize": result = finalize_routes(paths.state, args.run_id, args.candidate)
        elif args.command == "routes" and args.routes_command == "select": result = select_route(paths.state, args.project_id, args.route_id, note=args.note)
        elif args.command == "outline" and args.outline_command == "generate": result = prepare_outline(paths.state, args.project_id, feedback_id=args.feedback_id)
        elif args.command == "outline" and args.outline_command == "finalize": result = finalize_outline(paths.state, args.run_id, args.candidate)
        elif args.command == "outline" and args.outline_command == "feedback": result = record_internal_feedback(paths.state, args.project_id, args.outline_id, args.text)
        elif args.command == "brand" and args.brand_command == "submit": result = create_submission(paths.state, args.project_id, track=args.track, source_object_id=args.source_object_id, source_file=args.file)
        elif args.command == "brand" and args.brand_command == "feedback": result = prepare_brand_feedback(paths.state, args.project_id, args.submission_id, args.text)
        elif args.command == "brand" and args.brand_command == "feedback-finalize": result = finalize_brand_feedback(paths.state, args.run_id, args.candidate)
        elif args.command == "brand" and args.brand_command == "approve": result = approve_submission(paths.state, args.project_id, args.submission_id, note=args.note, confirmation_source=args.source)
        elif args.command == "copy" and args.copy_command == "generate": result = prepare_publication_copy(paths.state, args.project_id, feedback_id=args.feedback_id)
        elif args.command == "copy" and args.copy_command == "finalize": result = finalize_publication_copy(paths.state, args.run_id, args.candidate)
        elif args.command == "copy" and args.copy_command == "feedback": result = record_publication_copy_feedback(paths.state, args.project_id, args.copy_id, args.text)
        elif args.command == "published" and args.published_command == "archive":
            archived = archive_publication(paths.state, args.project_id, oral_script=args.oral_script, published_copy=args.published_copy, published_at=args.published_at, published_url=args.published_url, published_copy_screenshot=args.published_copy_screenshot)
            payload = {"status": archived.run["status"] if archived.run else "waiting_for_more_files", "run_id": archived.run["run_id"] if archived.run else None, "bundle_id": archived.bundle["bundle_id"], "completeness": archived.bundle["completeness"], "path": str(archived.bundle_path), "task_path": str(archived.task_path) if archived.task_path else None, "candidate_output_path": archived.run.get("outputs", {}).get("candidate_output_path") if archived.run else None}
        elif args.command == "published" and args.published_command == "finalize":
            archived = finalize_archive(paths.state, args.run_id, args.candidate)
            payload = {"status": archived.run["status"], "run_id": archived.run["run_id"], "bundle_id": archived.bundle["bundle_id"], "completeness": archived.bundle["completeness"], "path": str(archived.bundle_path), "learning_candidate_ids": archived.run["outputs"].get("learning_candidate_ids", [])}
        elif args.command == "learning" and args.learning_command == "review": result = review_learning(paths.state, args.project_id, args.candidate_id, args.decision, note=args.note)
        else: payload = None
        if result is not None:
            obj = result.object
            object_id = next((obj[key] for key in ("project_id", "brief_id", "route_set_id", "selection_id", "outline_id", "feedback_id", "submission_id", "approval_id", "copy_id", "extraction_id", "review_id") if key in obj), None)
            payload = {"status": result.run["status"] if result.run else "completed", "run_id": result.run["run_id"] if result.run else None, "object_id": object_id, "path": str(result.path), "task_path": str(result.task_path) if result.task_path else None, "candidate_output_path": result.run.get("outputs", {}).get("candidate_output_path") if result.run else None}
        if payload is not None:
            if args.as_json: print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"状态：{payload['status']}")
                if payload.get("path"): print(f"文件：{payload['path']}")
                if payload.get("task_path"): print(f"AI Task：{payload['task_path']}")
            return 0
    except (BaselineReviewError, PlaybookError, ExtractionError, WorkflowError, OSError, ValueError, json.JSONDecodeError) as exc:
        build_parser().error(str(exc))
    if args.command == "workbench" and args.workbench_command == "build":
        paths = resolve_paths(args.workspace)
        try:
            workbench_result = rebuild_workbench(paths.state, paths.workbench)
            result = workbench_result.build
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser = build_parser()
            parser.error(f"Workbench 构建失败：{exc}")
        payload = {
            "status": "completed",
            "run_id": workbench_result.run["run_id"],
            "index_path": str(result.index_path),
            "creator_count": result.creator_count,
            "baseline_count": result.baseline_count,
            "project_count": result.project_count,
            "page_count": result.page_count,
            "warnings": result.warnings,
        }
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Workbench 已重建：{payload['index_path']}")
            print(f"博主：{payload['creator_count']}；项目：{payload['project_count']}；Baseline：{payload['baseline_count']}；页面：{payload['page_count']}")
            if payload["warnings"]:
                print(f"警告：{len(payload['warnings'])} 条")
        return 0
    return 2
