from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_compact_role(profile: dict[str, Any], registry: Any) -> dict[str, Any]:
    from .csv_export import profile_to_role_row, profile_to_unified_detail_rows
    from .key_items import count_key_items_from_details

    row = profile_to_role_row(profile, registry)
    basic = (profile.get("character") or {}).get("basic_attrs") or {}
    details = profile_to_unified_detail_rows(profile, registry)

    equips: list[dict[str, Any]] = []
    summons: list[dict[str, Any]] = []
    for d in details:
        item = {
            "type": d.get("明细类型"),
            "name": d.get("名称"),
            "type_id": d.get("type_id"),
            "amount": d.get("数量"),
            "wearing": d.get("穿戴"),
            "props": d.get("属性"),
            "special": d.get("特效"),
            "score": d.get("单项评分"),
            "note": d.get("备注"),
            "level": d.get("召唤等级"),
            "hp": d.get("气血"),
            "speed": d.get("速度"),
            "growth": d.get("成长"),
            "pet_score": d.get("宠物评分"),
            "fight_grade": d.get("参战等级"),
            "skills": d.get("技能"),
            "fighting": d.get("参战"),
            "life": d.get("寿命"),
        }
        item = {k: v for k, v in item.items() if v not in ("", None, False)}
        if d.get("明细类型") in ("召唤灵", "仓库召唤灵", "子女"):
            summons.append(item)
        elif d.get("明细类型") != "无明细":
            equips.append(item)

    compact = dict(row)
    for key in (
        "仓库物品明细",
        "背包物品明细",
        "召唤灵明细",
        "highlights",
        "eid",
    ):
        compact.pop(key, None)
    compact["equips"] = equips
    compact["summons"] = summons
    compact["key_items"] = count_key_items_from_details(details)
    compact["冻结金币"] = None
    return compact


def build_payload(
    profiles: list[dict[str, Any]],
    *,
    server: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .type_names import get_registry

    reg = get_registry()
    roles = [build_compact_role(p, reg) for p in profiles]
    detail_count = sum(len(r.get("equips", [])) + len(r.get("summons", [])) for r in roles)

    payload: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_roles": len(roles),
        "total_details": detail_count,
        "roles": roles,
    }
    if server:
        payload["server"] = {
            "key": server.get("key"),
            "serverid": server.get("serverid"),
            "server_name": server.get("server_name"),
            "area_name": server.get("area_name"),
            "gold_min_wan": server.get("gold_min_wan"),
        }
    return payload
