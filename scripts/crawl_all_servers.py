#!/usr/bin/env python3
"""全服/批量抓取 CLI：按服务器列表依次抓取每个服的角色数据。

支持账号池（--pool / --account）：某个服抓取时登录失效会自动重登/轮换账号后续抓。
业务逻辑复用 cbg.crawl.run_crawl。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg import CbgApiError, SessionTimeoutError, load_search_config, run_crawl
from cbg.servers import (
    DEFAULT_SERVERS_PATH,
    build_search_config,
    fetch_server_data,
    iter_servers,
    load_servers,
    resolve_servers_by_names,
    save_servers,
    server_key,
)
from cbg.session import ClientProvider, add_client_args

DEFAULT_PROGRESS_PATH = Path("data/crawl_progress.json")


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"completed": [], "failed": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    progress["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_targets(
    data: dict[str, Any], args: argparse.Namespace
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if args.names_file or args.names:
        name_list: list[str] = []
        if args.names_file:
            name_list.extend(
                line.strip()
                for line in Path(args.names_file).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            )
        if args.names:
            name_list.extend(part.strip() for part in args.names.split(",") if part.strip())
        targets, missing = resolve_servers_by_names(data, name_list, area_name=args.area)
        if missing:
            print("[批量] 未在服务器列表中找到:")
            for name in missing:
                print(f"  - {name}")
        return targets
    return list(iter_servers(data, area_name=args.area, serverid=args.serverid))


def main() -> None:
    parser = argparse.ArgumentParser(description="全服/批量抓取")
    parser.add_argument("-s", "--search", default="search.json", help="搜索条件模板")
    add_client_args(parser)
    parser.add_argument("--servers", default=str(DEFAULT_SERVERS_PATH), help="服务器列表文件")
    parser.add_argument("--progress", default=str(DEFAULT_PROGRESS_PATH), help="进度文件")
    parser.add_argument("--fetch", action="store_true", help="抓取前先更新服务器列表")
    parser.add_argument("--area", help="只抓取指定大区，如 时空区")
    parser.add_argument("--serverid", type=int, help="只抓取指定 serverid")
    parser.add_argument("--names-file", help="按服名抓取，文件每行一个服名")
    parser.add_argument("--names", help="按服名抓取，逗号分隔")
    parser.add_argument("--limit", type=int, help="最多抓取几个服务器（调试用）")
    parser.add_argument("--skip-completed", action="store_true", help="跳过 progress 里已完成的服")
    parser.add_argument("--reset-progress", action="store_true", help="清空进度后重新开始")
    parser.add_argument(
        "--delay-between-servers", type=float, default=2.0, help="每服之间的间隔秒数（默认 2）"
    )
    parser.add_argument("--list-only", action="store_true", help="只拉列表，不抓详情")
    parser.add_argument("--max-pages", type=int, help="每服最多拉几页列表")
    parser.add_argument("--pg", action="store_true", help="每抓完一个服直接写入 Vercel Postgres")
    args = parser.parse_args()

    servers_path = Path(args.servers)
    if args.fetch or not servers_path.exists():
        print(f"[服务器] 拉取列表 -> {servers_path}")
        data = fetch_server_data()
        save_servers(data, servers_path)
        print(f"[服务器] {data['total_areas']} 个大区, {data['total_servers']} 个服务器")
    else:
        data = load_servers(servers_path)

    template = load_search_config(Path(args.search))
    progress_path = Path(args.progress)
    if args.reset_progress and progress_path.exists():
        progress_path.unlink()

    progress = load_progress(progress_path)
    completed = set(progress.get("completed") or [])
    failed: dict[str, str] = dict(progress.get("failed") or {})

    targets = resolve_targets(data, args)
    if args.skip_completed:
        targets = [(a, s) for a, s in targets if server_key(s) not in completed]
    if args.limit is not None:
        targets = targets[: args.limit]

    total = len(targets)
    if total == 0:
        print("没有需要抓取的服务器")
        return

    print(f"[批量] 共 {total} 个服务器待抓取")
    if args.area:
        print(f"[批量] 大区过滤: {args.area}")

    provider = ClientProvider.from_args(args)
    exit_code = 0

    def persist() -> None:
        progress["completed"] = sorted(completed)
        progress["failed"] = failed
        save_progress(progress_path, progress)

    try:
        with provider:
            idx = 0
            while idx < total:
                area, server = targets[idx]
                key = server_key(server)
                label = f"{area['area_name']} {server['server_name']} ({server['serverid']})"
                print(f"\n{'=' * 60}")
                print(f"[批量] ({idx + 1}/{total}) {label}")
                print(f"{'=' * 60}")

                cfg = build_search_config(template, area, server)
                try:
                    result = run_crawl(
                        cfg,
                        provider.client(),
                        list_only=args.list_only,
                        max_pages=args.max_pages,
                    )
                    completed.add(key)
                    failed.pop(key, None)
                    progress["last_server"] = {
                        "key": key,
                        "serverid": server.get("serverid"),
                        "server_name": server.get("server_name"),
                        "area_name": area.get("area_name"),
                        "items": len(result["items"]),
                    }
                    persist()
                    if args.pg:
                        try:
                            from cbg.pg import sync_crawl_result_to_pg

                            info = sync_crawl_result_to_pg(result)
                            print(
                                f"[Postgres] 已写入 {info['total_roles']} 个角色 -> {info['server']}"
                                + (f"，标记已售 {info['marked_sold']} 个" if info.get("marked_sold") else "")
                            )
                        except Exception as pg_exc:
                            print(f"[Postgres] 写入失败: {pg_exc}")
                except SessionTimeoutError as exc:
                    print(f"[批量] 登录失效: {exc}")
                    if provider.rotate():
                        print("[批量] 已重登/切换账号，重试当前服...")
                        continue  # 不推进 idx，重试同一个服
                    failed[key] = f"登录失效且无可用账号: {exc}"
                    persist()
                    exit_code = 2
                    break
                except CbgApiError as exc:
                    failed[key] = str(exc)
                    persist()
                    print(f"[批量] 失败: {exc}")

                idx += 1
                if args.delay_between_servers > 0 and idx < total:
                    time.sleep(args.delay_between_servers)

    except KeyboardInterrupt:
        print("\n[批量] 用户中断，进度已保存")
        persist()
        sys.exit(130)

    persist()
    print(f"\n[批量] 完成: 成功 {len(completed)} 个, 失败 {len(failed)} 个")
    print(f"[批量] 进度文件: {progress_path}")
    if failed:
        print("[批量] 失败列表:")
        for key, message in sorted(failed.items()):
            print(f"  - {key}: {message}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
