from __future__ import annotations

from pathlib import Path
from typing import Any


def build_distillation_task(
    *,
    creator_id: str,
    run_id: str,
    profile: dict[str, Any],
    analysis: dict[str, Any],
    evidence: list[dict[str, Any]],
    notes_path: Path,
    evidence_path: Path,
    protocol_path: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_type": "creator_baseline_distillation",
        "creator_id": creator_id,
        "run_id": run_id,
        "status": "ready" if analysis["distillation_gate"]["eligible"] else "blocked_by_quality_gate",
        "profile": profile,
        "deterministic_analysis": analysis,
        "materials": {
            "normalized_notes_path": str(notes_path),
            "evidence_path": str(evidence_path),
            "note_evidence_count": sum(item["kind"] == "note" for item in evidence),
            "comment_evidence_count": sum(item["kind"] == "comment" for item in evidence),
        },
        "protocol": protocol_path,
        "candidate_output": str(notes_path.parent / "baseline-candidate.json"),
        "instructions": [
            "Read the protocol completely before producing the candidate.",
            "Read normalized notes and Evidence; do not infer from aggregate metrics alone.",
            "Use the longitudinal current window for current identity; keep historical capabilities and transition signals explicitly time-scoped.",
            "Return only a JSON object matching baseline-candidate.schema.json.",
            "Use Evidence IDs exactly as stored; never invent an Evidence ID.",
            "Do not produce a core_belief without at least three distinct note Evidence items.",
            "Mark uncertain or uncovered dimensions in missing_dimensions instead of guessing.",
        ],
    }
