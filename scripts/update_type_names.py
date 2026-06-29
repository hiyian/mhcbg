#!/usr/bin/env python3
"""下载并缓存 type_id → 中文名 映射表。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg.type_names import TypeNameRegistry


def main() -> None:
    registry = TypeNameRegistry()
    count = registry.refresh()
    print(f"已更新 {registry.cache_path}，共 {count} 条映射")

    for tid in ["3107", "5034", "31004", "2031", "301", "526"]:
        print(f"  {tid} -> {registry.lookup(tid)}")


if __name__ == "__main__":
    main()
