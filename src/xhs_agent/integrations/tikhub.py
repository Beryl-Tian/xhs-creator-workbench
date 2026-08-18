from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


DEFAULT_BASE_URL = "https://api.tikhub.io"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_RPS = 5
APP_V2_PREFIX = "/api/v1/xiaohongshu/app_v2"


class TikHubError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def load_tikhub_token(user_config: Path, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    environment_token = os.environ.get("TIKHUB_API_TOKEN", "").strip()
    if environment_token:
        return environment_token
    if not user_config.is_file():
        return ""
    try:
        payload = json.loads(user_config.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TikHubError(f"无法读取用户级 TikHub 配置：{user_config}") from exc
    for key in ("tikhub_api_token", "api_token", "token"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def account_params(account: str) -> dict[str, str]:
    value = account.strip()
    if not value:
        raise ValueError("account cannot be empty")
    if "http://" in value or "https://" in value or "xhslink.com" in value:
        return {"share_text": value}
    return {"user_id": value}


Transport = Callable[[str, Mapping[str, object], str, float], dict]


@dataclass
class TikHubClient:
    token: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    rps: int = DEFAULT_RPS
    transport: Transport | None = None

    def __post_init__(self) -> None:
        self.token = self.token.strip()
        if not self.token:
            raise TikHubError(
                "未配置 TikHub Token。请设置 TIKHUB_API_TOKEN，或写入用户级配置。"
            )
        self.base_url = self.base_url.rstrip("/")
        if self.rps <= 0:
            raise ValueError("rps must be positive")
        self._last_call_at = 0.0

    @classmethod
    def from_config(cls, user_config: Path, *, token: str | None = None) -> "TikHubClient":
        resolved = load_tikhub_token(user_config, token)
        base_url = os.environ.get("TIKHUB_BASE_URL", DEFAULT_BASE_URL)
        try:
            rps = int(os.environ.get("TIKHUB_RPS", DEFAULT_RPS))
        except ValueError:
            rps = DEFAULT_RPS
        return cls(token=resolved, base_url=base_url, rps=max(rps, 1))

    def _throttle(self) -> None:
        interval = 1.0 / self.rps
        elapsed = time.monotonic() - self._last_call_at
        if self._last_call_at and elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_call_at = time.monotonic()

    def _urllib_transport(
        self,
        path: str,
        params: Mapping[str, object],
        token: str,
        timeout: float,
    ) -> dict:
        query = urllib.parse.urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "xhs-creator-workbench/0.1",
            },
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get(self, path: str, params: Mapping[str, object], *, retries: int = 2) -> dict:
        transport = self.transport or self._urllib_transport
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            self._throttle()
            try:
                payload = transport(path, params, self.token, self.timeout)
                if not isinstance(payload, dict):
                    raise TikHubError("TikHub 返回的响应不是 JSON 对象")
                code = payload.get("code")
                if code not in (None, 0, 200):
                    message = payload.get("message_zh") or payload.get("message") or "未知错误"
                    last_error = TikHubError(f"TikHub API 错误（code={code}）：{message}")
                    if code in (429, 500, 502, 503, 504) and attempt < retries:
                        time.sleep(2**attempt)
                        continue
                    raise last_error
                return payload
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    label = "Token 无效或已过期" if exc.code == 401 else "Token 缺少接口权限"
                    raise TikHubError(label, status_code=exc.code) from exc
                last_error = TikHubError(f"TikHub HTTP 错误：{exc.code}", status_code=exc.code)
                if exc.code != 429 and exc.code < 500:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = TikHubError("TikHub 网络请求或响应解析失败")
            except TikHubError:
                raise
            if attempt < retries:
                time.sleep(2**attempt)
        raise last_error or TikHubError("TikHub 请求失败")

    def get_user_info(self, account: str) -> dict:
        return self._get(f"{APP_V2_PREFIX}/get_user_info", account_params(account))

    def get_user_posted_notes(self, account: str, *, cursor: str = "") -> dict:
        params: dict[str, object] = {**account_params(account), "cursor": cursor}
        return self._get(f"{APP_V2_PREFIX}/get_user_posted_notes", params)

    def get_note_detail(self, note_id: str, *, note_type: str = "normal") -> dict:
        endpoint = "get_video_note_detail" if "video" in note_type.lower() else "get_image_note_detail"
        return self._get(f"{APP_V2_PREFIX}/{endpoint}", {"note_id": note_id})

    def get_note_comments(
        self,
        note_id: str,
        *,
        cursor: str = "",
        index: int = 0,
        page_area: str = "UNFOLDED",
        sort_strategy: str = "like_count",
    ) -> dict:
        return self._get(
            f"{APP_V2_PREFIX}/get_note_comments",
            {
                "note_id": note_id,
                "cursor": cursor,
                "index": index,
                "pageArea": page_area,
                "sort_strategy": sort_strategy,
            },
        )
