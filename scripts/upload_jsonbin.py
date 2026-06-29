#!/usr/bin/env python3
"""将 output/ 详情上传到 JSONBin，并更新 web/config.js。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg.csv_export import load_profiles_from_dir
from cbg.jsonbin import (
    JsonBinClient,
    build_payload,
    load_bin_id,
    load_master_key,
    save_bin_id,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="上传数据到 JSONBin")
    parser.add_argument("-d", "--dir", default="output", help="详情 JSON 目录")
    parser.add_argument("--create", action="store_true", help="创建新 bin（首次）")
    args = parser.parse_args()

    profiles = load_profiles_from_dir(Path(args.dir))
    if not profiles:
        print(f"{args.dir} 下没有详情 JSON")
        sys.exit(1)

    master_key = load_master_key()
    bin_id = load_bin_id()
    client = JsonBinClient(master_key, bin_id)
    payload = build_payload(profiles)

    if args.create or not bin_id:
        new_id = client.create(payload)
        save_bin_id(new_id)
        print(f"已创建 bin: {new_id}")
    else:
        client.update(payload)
        print(f"已更新 bin: {bin_id}")

    print(f"角色: {payload['total_roles']}，明细: {payload['total_details']}")
    print(f"web/config.js 已更新")


if __name__ == "__main__":
    main()
