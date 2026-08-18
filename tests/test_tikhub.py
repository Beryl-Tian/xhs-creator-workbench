from __future__ import annotations

import json
from pathlib import Path

import pytest

from xhs_agent.integrations.tikhub import APP_V2_PREFIX, TikHubClient, TikHubError, load_tikhub_token


def test_token_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"tikhub_api_token": "config-value"}), encoding="utf-8")
    monkeypatch.setenv("TIKHUB_API_TOKEN", "environment-value")
    assert load_tikhub_token(config, "explicit-value") == "explicit-value"
    assert load_tikhub_token(config) == "environment-value"
    monkeypatch.delenv("TIKHUB_API_TOKEN")
    assert load_tikhub_token(config) == "config-value"


def test_client_uses_app_v2_routes_and_account_params() -> None:
    calls = []

    def transport(path, params, token, timeout):
        calls.append((path, dict(params), token, timeout))
        return {"code": 200, "data": {}}

    client = TikHubClient(token="synthetic-token", transport=transport, rps=100_000)
    client.get_user_info("synthetic-user")
    client.get_user_posted_notes("https://example.invalid/profile")
    client.get_note_detail("note-1", note_type="video")
    client.get_note_comments("note-1", cursor="next", index=2)

    assert all(call[0].startswith(APP_V2_PREFIX) for call in calls)
    assert calls[0][1]["user_id"] == "synthetic-user"
    assert calls[1][1]["share_text"] == "https://example.invalid/profile"
    assert calls[2][0].endswith("get_video_note_detail")
    assert calls[3][1]["pageArea"] == "UNFOLDED"


def test_api_error_does_not_include_token() -> None:
    secret = "synthetic-secret-that-must-not-leak"

    def transport(path, params, token, timeout):
        return {"code": 400, "message": "bad request"}

    client = TikHubClient(token=secret, transport=transport, rps=100_000)
    with pytest.raises(TikHubError) as error:
        client.get_user_info("synthetic-user")
    assert secret not in str(error.value)
