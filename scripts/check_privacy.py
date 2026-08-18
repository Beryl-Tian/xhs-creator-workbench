#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from xhs_agent.privacy import (
    find_secret_values,
    find_unmarked_test_persona_values,
    is_forbidden_path,
    is_private_artifact_path,
)


TEXT_SUFFIXES = {
    ".env", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml", ".sh"
}
MAX_SCAN_BYTES = 2_000_000


def candidate_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    violations: list[str] = []
    for relative in candidate_files():
        if is_forbidden_path(relative):
            violations.append(f"private path is visible to Git: {relative}")
            continue
        if is_private_artifact_path(relative):
            violations.append(f"private artifact type is visible to Git: {relative}")
            continue
        path = REPO_ROOT / relative
        if not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        secrets = find_secret_values(text)
        if secrets:
            violations.append(f"possible secret in {relative}")
        if relative.startswith("tests/") and find_unmarked_test_persona_values(text):
            violations.append(f"test persona value is not explicitly synthetic in {relative}")

    if violations:
        print("Privacy check failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print(f"Privacy check passed ({len(candidate_files())} visible files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
