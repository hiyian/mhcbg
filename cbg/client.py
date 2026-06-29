from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


class CbgApiError(Exception):
    def __init__(self, message: str, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.payload = payload or {}


class SessionTimeoutError(CbgApiError):
    pass


class CbgClient:
    """梦幻西游手游藏宝阁 HTTP API 客户端（方案 C）。"""

    API_ROOT = "/cgi/api/"
    STATUS_OK = 1
    STATUS_SESSION_TIMEOUT = 2

    def __init__(self, config_path: str | Path = "config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.base_url = self.config["base_url"].rstrip("/")
        self.defaults = self.config.get("defaults", {})
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._build_headers(),
            cookies=self._parse_cookie_string(self.config.get("cookies", "")),
            timeout=30.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CbgClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @staticmethod
    def _load_config() -> dict[str, Any]:
        path = Path("config.json")
        if not path.exists():
            raise FileNotFoundError(
                "未找到 config.json。请复制 config.example.json 并填入 Cookie：\n"
                "  cp config.example.json config.json"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/144.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": (
                f"{self.base_url}/cgi/mweb/pl?"
                "search_type=role&tfid=f_kingkong&serverid=911"
            ),
        }
        headers.update(self.config.get("headers", {}))
        return headers

    def _request_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        safe_code = self.config.get("cbg_safe_code") or self.config.get("safe_code")
        if safe_code:
            headers["cbg-safe-code"] = safe_code
        headers["cbg-request-id"] = str(uuid.uuid4()).upper()
        return headers

    @staticmethod
    def _parse_cookie_string(cookie_str: str) -> httpx.Cookies:
        cookies = httpx.Cookies()
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.set(name.strip(), value.strip())
        return cookies

    def _inject_common_params(self, params: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.defaults)
        merged.update(params)
        merged.setdefault("exter", "direct")

        if "traffic_trace" not in merged:
            tfid = merged.get("tfid") or self.defaults.get("tfid")
            tcid = merged.get("tcid") or self.defaults.get("tcid") or ""
            if tfid:
                merged["traffic_trace"] = json.dumps(
                    {"field_id": tfid, "content_id": tcid},
                    ensure_ascii=False,
                )

        return merged

    def _check_response(self, data: dict[str, Any]) -> dict[str, Any]:
        status = data.get("status")
        if status == self.STATUS_SESSION_TIMEOUT:
            raise SessionTimeoutError(
                data.get("msg") or "登录超时，请更新 config.json 中的 Cookie",
                data,
            )
        if status != self.STATUS_OK:
            raise CbgApiError(data.get("msg") or "请求失败", data)
        return data

    def api_get(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        *,
        is_api_like: bool = True,
    ) -> dict[str, Any]:
        query = self._inject_common_params(params or {}) if is_api_like else (params or {})
        path = action if action.startswith("/") else f"{self.API_ROOT}{action}"
        resp = self._client.get(
            path,
            params={"client_type": "h5", **query},
            headers=self._request_headers(),
        )
        resp.raise_for_status()
        return self._check_response(resp.json())

    def api_post(
        self,
        action: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
        is_api_like: bool = True,
    ) -> dict[str, Any]:
        payload = self._inject_common_params(body or {}) if is_api_like else (body or {})
        path = action if action.startswith("/") else f"{self.API_ROOT}{action}"
        url_query = {"client_type": "h5", **(query or {})}
        resp = self._client.post(
            path,
            params=url_query,
            data=payload,
            headers=self._request_headers(),
        )
        resp.raise_for_status()
        return self._check_response(resp.json())

    def recommend(
        self,
        params: dict[str, Any] | None = None,
        *,
        act: str = "recommd_by_role",
    ) -> dict[str, Any]:
        """POST /cgi-bin/recommend.py?client_type=h5&act=recommd_by_role"""
        body = self._inject_common_params(
            {
                "search_type": self.defaults.get("search_type", "role"),
                "count": self.defaults.get("count", 15),
                **(params or {}),
            }
        )
        resp = self._client.post(
            "/cgi-bin/recommend.py",
            params={"client_type": "h5", "act": act},
            data=body,
            headers=self._request_headers(),
        )
        resp.raise_for_status()
        return self._check_response(resp.json())

    def get_equip_detail(
        self,
        *,
        serverid: int | str,
        ordersn: str | None = None,
        eid: str | None = None,
        view_loc: str | None = None,
        exclude_equip_desc: int = 1,
        **extra: Any,
    ) -> dict[str, Any]:
        """POST /cgi/api/get_equip_detail?client_type=h5"""
        params: dict[str, Any] = {
            "serverid": serverid,
            "h5_device": "other",
            "app_client": "other",
            "exclude_equip_desc": exclude_equip_desc,
            **extra,
        }
        if ordersn:
            params["ordersn"] = ordersn
        if eid:
            params["eid"] = eid
        if view_loc:
            params["view_loc"] = view_loc
        elif self.defaults.get("detail_view_loc"):
            params["view_loc"] = self.defaults["detail_view_loc"]

        detail_defaults = self.config.get("detail_defaults", {})
        for key, value in detail_defaults.items():
            params.setdefault(key, value)

        return self.api_post("get_equip_detail", params)

    def ping(self) -> dict[str, Any]:
        resp = self._client.get(
            f"{self.API_ROOT}keyword_query",
            params={"client_type": "h5", "keyword": "龙宫"},
            headers=self._request_headers(),
        )
        resp.raise_for_status()
        return resp.json()
