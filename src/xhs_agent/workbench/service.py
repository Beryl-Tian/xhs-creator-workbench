from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..creator.baseline import utc_now
from ..renderers import BuildResult, build_workbench
from ..storage import write_json_atomic


@dataclass(frozen=True)
class WorkbenchRunResult:
    run: dict[str, Any]
    build: BuildResult


def rebuild_workbench(state: Path, output: Path) -> WorkbenchRunResult:
    started_at = utc_now()
    run_id = f"run_{uuid.uuid4().hex[:20]}"
    run_path = state / "runs" / f"{run_id}.json"
    run = {
        "schema_version": 1,
        "run_id": run_id,
        "operation": "workbench.build",
        "status": "running",
        "inputs": {"source": ".xhs-agent", "projection": "workbench"},
        "outputs": {},
        "steps": [{"name": "render_static_projection", "status": "running", "error": None}],
        "error_code": None,
        "recovery_hint": None,
        "started_at": started_at,
        "updated_at": started_at,
    }
    write_json_atomic(run_path, run)
    try:
        build = build_workbench(state, output)
        run["steps"][0]["status"] = "completed"
        run["status"] = "completed"
        run["outputs"] = {
            "index_path": str(build.index_path),
            "creator_count": build.creator_count,
            "baseline_count": build.baseline_count,
            "project_count": build.project_count,
            "page_count": build.page_count,
            "warnings": build.warnings,
        }
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)
        return WorkbenchRunResult(run=run, build=build)
    except Exception as exc:
        run["steps"][0]["status"] = "failed"
        run["steps"][0]["error"] = str(exc)
        run["status"] = "failed"
        run["error_code"] = "workbench_build_failed"
        run["recovery_hint"] = "检查损坏的 Creator/Baseline 文件和 workbench 写入权限后重试。"
        run["updated_at"] = utc_now()
        write_json_atomic(run_path, run)
        raise
