#!/usr/bin/env python3
"""按 search.json 搜索条件分页拉列表，并抓取每个角色的三部分详情。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg import (
    CbgApiError,
    CbgClient,
    SessionTimeoutError,
    export_list_to_csv,
    export_profiles_to_csv,
    fetch_role_profile,
    load_profiles_from_dir,
    to_yuan,
)


def load_search_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"未找到 {path}，请先: cp search.example.json search.json"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def extract_list_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("equip_list", "result"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def list_item_brief(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "ordersn": item.get("game_ordersn") or item.get("ordersn"),
        "eid": item.get("eid"),
        "serverid": item.get("serverid"),
        "role_name": item.get("format_equip_name") or item.get("equip_name"),
        "school": item.get("school") or item.get("subtitle"),
        "level": item.get("equip_level"),
        "price": to_yuan(item.get("price")),
        "price_raw": item.get("price"),
        "server_name": item.get("server_name"),
        "desc_sumup": item.get("desc_sumup_short"),
        "detail_url": item.get("equip_detail_url"),
    }


def ordersn_csv(items: list[dict[str, Any]]) -> str:
    return ",".join(
        sn
        for item in items
        if (sn := item.get("game_ordersn") or item.get("ordersn"))
    )


def crawl_list_pages(
    client: CbgClient,
    search_params: dict[str, Any],
    *,
    max_pages: int | None = None,
    delay_seconds: float = 1.0,
) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    seen_ordersn: set[str] = set()
    prev_exposed = ""
    page = 1

    while True:
        body = dict(search_params)
        body["page"] = page
        if page > 1 and prev_exposed:
            body["exposed_game_ordersn"] = prev_exposed

        print(f"[列表] 第 {page} 页...", flush=True)
        data = client.recommend(body)
        items = extract_list_items(data)
        if not items:
            print(f"[列表] 第 {page} 页无数据，结束")
            break

        new_count = 0
        for item in items:
            brief = list_item_brief(item)
            sn = brief.get("ordersn")
            if sn and sn not in seen_ordersn:
                seen_ordersn.add(sn)
                all_items.append({**brief, "list_raw": item})
                new_count += 1

        paging = data.get("paging") or {}
        is_last = paging.get("is_last_page")
        print(
            f"[列表] 第 {page} 页 {len(items)} 条，新增 {new_count} 条，累计 {len(all_items)} 条"
            + (", 最后一页" if is_last else "")
        )

        prev_exposed = ordersn_csv(items)

        if is_last or (max_pages is not None and page >= max_pages):
            break

        page += 1
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return all_items


def save_profile(
    output_dir: Path,
    profile: dict[str, Any],
    *,
    skip_existing: bool,
) -> Path:
    ordersn = profile["meta"]["ordersn"] or "unknown"
    safe_name = ordersn.replace("/", "_")
    path = output_dir / f"{safe_name}.json"
    if skip_existing and path.exists():
        return path
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="搜索列表 + 抓取详情")
    parser.add_argument(
        "-s",
        "--search",
        default="search.json",
        help="搜索条件文件（默认 search.json）",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="登录配置（Cookie）",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="只拉列表，不抓详情",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="最多拉几页（覆盖 search.json 里的设置）",
    )
    args = parser.parse_args()

    cfg = load_search_config(Path(args.search))
    search_params = cfg.get("search") or cfg
    crawl_cfg = cfg.get("crawl", {})
    delay_seconds = float(crawl_cfg.get("delay_seconds", 1.0))
    max_pages = args.max_pages if args.max_pages is not None else crawl_cfg.get("max_pages")
    output_dir = Path(crawl_cfg.get("output_dir", "output"))
    fetch_detail = not args.list_only and crawl_cfg.get("fetch_detail", True)
    skip_existing = crawl_cfg.get("skip_existing", True)

    if not Path(args.config).exists():
        print("未找到 config.json")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with CbgClient(args.config) as client:
            items = crawl_list_pages(
                client,
                search_params,
                max_pages=max_pages,
                delay_seconds=delay_seconds,
            )

            index = {
                "total": len(items),
                "search": search_params,
                "items": [{k: v for k, v in item.items() if k != "list_raw"} for item in items],
            }

            if fetch_detail:
                print(f"\n[详情] 开始抓取 {len(items)} 个角色...", flush=True)
                for i, item in enumerate(items, 1):
                    ordersn = item.get("ordersn")
                    serverid = item.get("serverid") or search_params.get("serverid")
                    if not ordersn:
                        continue

                    out_path = output_dir / f"{ordersn.replace('/', '_')}.json"
                    if skip_existing and out_path.exists():
                        print(f"[详情] ({i}/{len(items)}) 跳过已存在 {ordersn}")
                        item["profile_file"] = str(out_path)
                        item["profile"] = json.loads(
                            out_path.read_text(encoding="utf-8")
                        )
                        continue

                    print(
                        f"[详情] ({i}/{len(items)}) {item.get('role_name')} "
                        f"¥{item.get('price'):g} {ordersn}",
                        flush=True,
                    )
                    try:
                        profile = fetch_role_profile(
                            client,
                            serverid=serverid,
                            ordersn=ordersn,
                        )
                        path = save_profile(
                            output_dir,
                            profile,
                            skip_existing=False,
                        )
                        item["profile_file"] = str(path)
                        item["profile"] = profile
                    except CbgApiError as exc:
                        item["detail_error"] = str(exc)
                        print(f"  失败: {exc}")

                    if delay_seconds > 0 and i < len(items):
                        time.sleep(delay_seconds)

            index_path = output_dir / "index.json"
            index_path.write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            profiles = [item["profile"] for item in items if item.get("profile")]
            if profiles:
                csv_paths = export_profiles_to_csv(output_dir, profiles)
                print(f"CSV 汇总: {csv_paths['roles']}")
                print(f"CSV 明细: {csv_paths['detail']}")
            elif not fetch_detail:
                list_csv = export_list_to_csv(output_dir, items)
                print(f"CSV 列表: {list_csv}")

            print(f"\n完成: 列表 {len(items)} 条")
            print(f"索引: {index_path}")
            if fetch_detail:
                print(f"详情目录: {output_dir}/")

    except SessionTimeoutError as exc:
        print(f"登录失效: {exc}")
        sys.exit(2)
    except CbgApiError as exc:
        print(f"API 错误: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
