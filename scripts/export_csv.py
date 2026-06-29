#!/usr/bin/env python3
"""将 output/ 下已有 JSON 详情导出为 CSV。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg import export_profiles_to_csv, load_profiles_from_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="JSON 详情 → CSV")
    parser.add_argument(
        "-d",
        "--dir",
        default="output",
        help="包含 *.json 详情的目录",
    )
    args = parser.parse_args()

    output_dir = Path(args.dir)
    profiles = load_profiles_from_dir(output_dir)
    if not profiles:
        print(f"{output_dir} 下没有详情 JSON 文件")
        sys.exit(1)

    paths = export_profiles_to_csv(output_dir, profiles)
    print(f"导出 {len(profiles)} 个角色")
    print(f"  汇总: {paths['roles']}")
    print(f"  明细: {paths['detail']}")


if __name__ == "__main__":
    main()
