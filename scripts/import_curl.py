#!/usr/bin/env python3
"""从 Chrome DevTools「Copy as cURL」导入 Cookie 与请求参数。"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def parse_curl(curl_text: str) -> dict[str, Any]:
    text = curl_text.strip()
    if text.startswith("curl"):
        text = text[4:].strip()

    tokens = shlex.split(text, posix=True)
    url = ""
    headers: dict[str, str] = {}
    cookie = ""
    params: dict[str, str] = {}

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-H", "--header") and i + 1 < len(tokens):
            header = tokens[i + 1]
            if ":" in header:
                key, value = header.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key.lower() == "cookie":
                    cookie = value
                else:
                    headers[key] = value
            i += 2
            continue
        if tok in ("-b", "--cookie") and i + 1 < len(tokens):
            cookie = tokens[i + 1]
            i += 2
            continue
        if tok.startswith("http://") or tok.startswith("https://"):
            url = tok.strip("'\"")
            i += 1
            continue
        i += 1

    if not url:
        raise ValueError("未能从 cURL 中解析 URL")

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    for key, values in parse_qs(parsed.query, keep_blank_values=True).items():
        params[key] = values[-1]

    action = "query"
    mode = "query"
    if "/cgi-bin/recommend.py" in parsed.path:
        mode = "recommend"
        action = "recommd_by_role"
    elif parsed.path.startswith("/cgi/api/"):
        action = parsed.path.removeprefix("/cgi/api/").strip("/") or "query"

    defaults = {
        "client_type": params.pop("client_type", "h5"),
        "view_loc": params.pop("view_loc", "equip_list"),
        "tfid": "",
        "count": int(params.pop("count", "15") or 15),
    }
    traffic = params.pop("traffic_trace", "")
    if traffic:
        try:
            trace = json.loads(traffic)
            defaults["tfid"] = trace.get("field_id", "")
        except json.JSONDecodeError:
            pass

    if "search_type" in params:
        defaults["search_type"] = params["search_type"]

    return {
        "base_url": base_url,
        "cookies": cookie,
        "headers": headers,
        "defaults": defaults,
        "list_api": {
            "mode": mode,
            "action": action,
            "extra_params": params,
        },
        "_source_url": url,
    }


def merge_config(existing: dict[str, Any] | None, imported: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return imported
    merged = dict(existing)
    merged["base_url"] = imported.get("base_url", merged.get("base_url"))
    if imported.get("cookies"):
        merged["cookies"] = imported["cookies"]
    merged_headers = dict(merged.get("headers", {}))
    merged_headers.update(imported.get("headers", {}))
    merged["headers"] = merged_headers
    merged_defaults = dict(merged.get("defaults", {}))
    merged_defaults.update(imported.get("defaults", {}))
    merged["defaults"] = merged_defaults
    merged["list_api"] = imported.get("list_api", merged.get("list_api"))
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="从 cURL 导入藏宝阁 API 配置")
    parser.add_argument(
        "curl_file",
        nargs="?",
        help="保存 cURL 的文本文件；省略则从 stdin 读取",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="config.json",
        help="输出配置文件路径（默认 config.json）",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="与已有 config.json 合并，而不是覆盖",
    )
    args = parser.parse_args()

    if args.curl_file:
        curl_text = Path(args.curl_file).read_text(encoding="utf-8")
    else:
        print("请粘贴 DevTools 复制的 cURL，结束后按 Ctrl+D：")
        import sys

        curl_text = sys.stdin.read()

    imported = parse_curl(curl_text)
    output_path = Path(args.output)
    existing = None
    if args.merge and output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))

    config = merge_config(existing, imported)
    config.pop("_source_url", None)
    output_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"已写入 {output_path}")
    print(f"  接口模式: {config['list_api']['mode']}")
    print(f"  action:   {config['list_api']['action']}")
    print(f"  参数数量: {len(config['list_api'].get('extra_params', {}))}")
    if imported.get("_source_url"):
        print(f"  来源 URL: {imported['_source_url'][:120]}...")


if __name__ == "__main__":
    main()
