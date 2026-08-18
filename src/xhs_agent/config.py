from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    workspace: Path
    state: Path
    workbench: Path
    user_config: Path


def resolve_paths(workspace: Path | None = None) -> Paths:
    root = (workspace or Path.cwd()).resolve()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return Paths(
        workspace=root,
        state=root / ".xhs-agent",
        workbench=root / "workbench",
        user_config=config_home / "xhs-agent" / "config.json",
    )
