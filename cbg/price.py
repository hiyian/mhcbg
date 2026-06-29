from __future__ import annotations

from typing import Any


def to_yuan(price: Any) -> float | None:
    """藏宝阁 API 价格为分，展示/存储为元需除以 100。"""
    if price is None or price == "":
        return None
    return float(price) / 100
