from __future__ import annotations

import re
from pathlib import PurePosixPath


FORBIDDEN_ROOTS = {
    ".xhs-agent",
    "workbench",
    "data",
    "output",
    "temp",
    "runs",
    "private",
    "local",
    "exports",
}

PRIVATE_ARTIFACT_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".tsv", ".ppt", ".pptx",
    ".pages", ".numbers", ".key", ".png", ".jpg", ".jpeg", ".heic", ".webp",
    ".gif", ".mp4", ".mov", ".m4v", ".mp3", ".m4a", ".wav",
}

CURATED_ARTIFACT_ROOTS = {
    ("packages", "xhs-creator-workbench", "assets"),
    ("docs", "assets"),
    ("tests", "fixtures"),
}

ALLOWED_PLACEHOLDERS = {
    "",
    "example",
    "placeholder",
    "replace-me",
    "replace-with-your-token",
    "test-token",
    "xxx",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)TIKHUB_API_TOKEN\s*=\s*([^\s#]+)"),
    re.compile(r'(?i)"(?:api_)?token"\s*:\s*"([^"\n]+)"'),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+([A-Za-z0-9._-]{12,})"),
]

SYNTHETIC_TEXT_MARKERS = (
    "synthetic", "example", "demo", "合成", "虚构", "示例", "测试",
)

TEST_PERSONA_PATTERNS = [
    re.compile(r'(?i)(?:desired_positioning|target_audience)\s*=\s*["\x27]([^"\x27\n]+)'),
    re.compile(r'(?i)["\x27]--(?:desired-positioning|target-audience)["\x27]\s*,\s*["\x27]([^"\x27\n]+)'),
    re.compile(r'(?i)["\x27](?:desired_positioning|target_audience|desired_audience)["\x27]\s*:\s*["\x27]([^"\x27\n]+)'),
]


def is_forbidden_path(path: str) -> bool:
    normalized = PurePosixPath(path.replace("\\", "/"))
    return bool(normalized.parts and normalized.parts[0] in FORBIDDEN_ROOTS)


def is_private_artifact_path(path: str) -> bool:
    normalized = PurePosixPath(path.replace("\\", "/"))
    if normalized.suffix.lower() not in PRIVATE_ARTIFACT_SUFFIXES:
        return False
    parts = normalized.parts
    return not any(parts[: len(root)] == root for root in CURATED_ARTIFACT_ROOTS)


def find_secret_values(text: str) -> list[str]:
    found: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1).strip().strip('"\'),;').lower()
            if value not in ALLOWED_PLACEHOLDERS:
                found.append(match.group(1))
    return found


def find_unmarked_test_persona_values(text: str) -> list[str]:
    """Find test persona values that are not explicitly marked as synthetic."""
    found: list[str] = []
    for pattern in TEST_PERSONA_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            lowered = value.lower()
            if not any(marker in lowered for marker in SYNTHETIC_TEXT_MARKERS):
                found.append(value)
    return found
