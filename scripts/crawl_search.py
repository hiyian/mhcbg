#!/usr/bin/env python3
"""单服抓取 CLI：按 search.json 搜索列表并抓取每个角色的详情。

业务逻辑在 cbg.crawl，登录源在 cbg.session，本文件只做参数解析与调度。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg import CbgApiError, SessionTimeoutError, load_search_config, run_crawl
from cbg.session import ClientProvider, add_client_args


def main() -> None:
    parser = argparse.ArgumentParser(description="单服搜索列表 + 抓取详情")
    parser.add_argument("-s", "--search", default="search.json", help="搜索条件文件")
    add_client_args(parser)
    parser.add_argument("--list-only", action="store_true", help="只拉列表，不抓详情")
    parser.add_argument("--max-pages", type=int, help="最多拉几页（覆盖 search.json）")
    parser.add_argument("--pg", action="store_true", help="抓完直接写入 Vercel Postgres")
    args = parser.parse_args()

    cfg = load_search_config(Path(args.search))
    provider = ClientProvider.from_args(args)

    max_attempts = 3
    with provider:
        for attempt in range(1, max_attempts + 1):
            try:
                result = run_crawl(
                    cfg,
                    provider.client(),
                    list_only=args.list_only,
                    max_pages=args.max_pages,
                )
                if args.pg:
                    from cbg.pg import sync_crawl_result_to_pg

                    info = sync_crawl_result_to_pg(result)
                    print(
                        f"[Postgres] 已写入 {info['total_roles']} 个角色 -> {info['server']}"
                        + (f"，标记已售 {info['marked_sold']} 个" if info.get("marked_sold") else "")
                    )
                return
            except SessionTimeoutError as exc:
                print(f"登录失效: {exc}")
                if provider.rotate():
                    print("已重登/切换账号，重试...")
                    continue
                sys.exit(2)
            except CbgApiError as exc:
                print(f"API 错误: {exc}")
                sys.exit(1)
        print("多次尝试后仍登录失效，退出。")
        sys.exit(2)


if __name__ == "__main__":
    main()
