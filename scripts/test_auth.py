#!/usr/bin/env python3
"""验证 Cookie 与 cbg-safe-code 是否有效。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg import CbgClient


def main() -> None:
    parser = argparse.ArgumentParser(description="验证藏宝阁 API 登录态")
    parser.add_argument("-c", "--config", default="config.json")
    args = parser.parse_args()

    if not Path(args.config).exists():
        print("请先: cp config.example.json config.json 并填入 cookies")
        sys.exit(1)

    with CbgClient(args.config) as client:
        data = client.ping()
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
