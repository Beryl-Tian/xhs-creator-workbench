from xhs_agent.privacy import (
    find_secret_values,
    find_unmarked_test_persona_values,
    is_forbidden_path,
    is_private_artifact_path,
)


def test_private_runtime_roots_are_forbidden() -> None:
    assert is_forbidden_path(".xhs-agent/creators/example/profile.json")
    assert is_forbidden_path("workbench/creators/example/index.html")
    assert is_forbidden_path("data/raw-profile.json")


def test_repository_sources_are_allowed() -> None:
    assert not is_forbidden_path("src/xhs_agent/privacy.py")
    assert not is_forbidden_path("tests/fixtures/synthetic.json")


def test_user_supplied_artifacts_are_private_by_default() -> None:
    assert is_private_artifact_path("briefs/real-brand-brief.xlsx")
    assert is_private_artifact_path("creator-final-script.docx")
    assert is_private_artifact_path("feedback/screenshot.png")


def test_curated_assets_and_synthetic_fixtures_are_allowed() -> None:
    assert not is_private_artifact_path("packages/xhs-creator-workbench/assets/icon.png")
    assert not is_private_artifact_path("tests/fixtures/synthetic-brief.xlsx")


def test_placeholder_token_is_allowed() -> None:
    assert find_secret_values("TIKHUB_API_TOKEN=replace-with-your-token") == []


def test_realistic_token_is_detected() -> None:
    key = "TIKHUB_API_" + "TOKEN"
    assert find_secret_values(f"{key}=live_1234567890abcdef")


def test_test_persona_values_must_be_explicitly_synthetic() -> None:
    unmarked = "面向特定" + "人群的生活方式"
    field = "desired_" + "positioning"
    assert find_unmarked_test_persona_values(
        f'{field}="{unmarked}"'
    ) == [unmarked]
    assert find_unmarked_test_persona_values(
        'desired_positioning="合成目标定位"'
    ) == []
    assert find_unmarked_test_persona_values(
        '"target_audience": "虚构测试受众"'
    ) == []
