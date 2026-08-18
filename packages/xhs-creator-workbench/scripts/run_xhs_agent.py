#!/usr/bin/env python3
"""Thin Skill entry point for the installed xhs-agent runtime."""

from __future__ import annotations

import sys
from pathlib import Path


def _load_main():
    try:
        from xhs_agent.cli import main

        return main
    except ModuleNotFoundError:
        repository_src = Path(__file__).resolve().parents[3] / "src"
        if repository_src.exists():
            sys.path.insert(0, str(repository_src))
            from xhs_agent.cli import main

            return main
        raise SystemExit(
            "xhs-agent runtime is not installed. Install this repository before using the Skill."
        )


if __name__ == "__main__":
    raise SystemExit(_load_main()())
