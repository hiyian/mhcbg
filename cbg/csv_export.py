from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .price import to_yuan
from .type_names import TypeNameRegistry, get_registry


def _price_yuan(summary: dict[str, Any], meta: dict[str, Any]) -> float | None:
    raw = summary.get("price_raw") or meta.get("price_raw")
    if raw is not None:
        return to_yuan(raw)
    price = summary.get("price") if summary.get("price") is not None else meta.get("price")
    if price is None:
        return None
    if isinstance(price, (int, float)) and price >= 1000:
        return to_yuan(price)
    return float(price)


def _join_list(value: Any, sep: str = "|") -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return sep.join(str(x) for x in value)
    return str(value)


def _total_amount(items: list[dict[str, Any]] | None) -> int:
    return sum(int(item.get("amount") or 1) for item in (items or []))


def _format_items_detail(
    items: list[dict[str, Any]] | None,
    registry: TypeNameRegistry | None = None,
) -> str:
    reg = registry or get_registry()
    parts: list[str] = []
    for item in items or []:
        raw = item.get("raw") or {}
        exinfo = raw.get("exinfo") or {}
        type_id = item.get("type_id") or raw.get("iType")
        amount = item.get("amount") or raw.get("iAmount") or 1
        note = exinfo.get("ymsg") or exinfo.get("cName") or ""
        level = exinfo.get("iLevel")
        name = reg.lookup(type_id) or type_id
        text = f"{name}×{amount}" if amount != 1 else str(name)
        if level:
            text += f" Lv{level}"
        if note and note not in str(name):
            text += f"({note})"
        parts.append(str(text))
    return "|".join(parts)


def _format_summons_detail(
    summons: list[dict[str, Any]] | None,
    registry: TypeNameRegistry | None = None,
) -> str:
    reg = registry or get_registry()
    parts: list[str] = []
    for pet in summons or []:
        name = pet.get("name") or reg.lookup(pet.get("type_id")) or pet.get("type_id") or "?"
        level = pet.get("level")
        speed = pet.get("speed")
        fight = pet.get("fight_status")
        skills = [reg.lookup_skill(s) for s in (pet.get("skills") or [])]
        text = f"{name} Lv{level}" if level is not None else str(name)
        if speed is not None:
            text += f" 速{speed}"
        if fight:
            text += "(参战)"
        if skills:
            text += f"[{','.join(skills[:4])}]"
        parts.append(text)
    return "|".join(parts)


def _item_extra_fields(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("raw") or {}
    exinfo = raw.get("exinfo") or {}
    return {
        "备注": exinfo.get("ymsg") or "",
        "等级": exinfo.get("iLevel") or "",
    }


def profile_to_role_row(
    profile: dict[str, Any],
    registry: TypeNameRegistry | None = None,
) -> dict[str, Any]:
    meta = profile.get("meta") or {}
    summary = (profile.get("character") or {}).get("summary") or {}
    basic = (profile.get("character") or {}).get("basic_attrs") or {}
    items = profile.get("items") or {}
    summons = profile.get("summons") or {}

    warehouse_items = items.get("warehouse_items") or []
    bag_items = items.get("bag_items") or []
    summon_list = summons.get("summon_list") or []

    return {
        "ordersn": meta.get("ordersn"),
        "eid": meta.get("eid"),
        "serverid": meta.get("serverid"),
        "server_name": summary.get("server_name") or meta.get("server_name"),
        "area_name": summary.get("area_name"),
        "role_name": summary.get("role_name") or meta.get("equip_name"),
        "school": summary.get("school"),
        "level": summary.get("level"),
        "price": _price_yuan(summary, meta),
        "desc_sumup": summary.get("desc_sumup"),
        "highlights": _join_list(summary.get("highlights")),
        "气血": basic.get("iHp_Max"),
        "魔法": basic.get("iMp_Max"),
        "物伤": basic.get("iDamage"),
        "法伤": basic.get("iMagDam"),
        "速度": basic.get("iSpeed"),
        "防御": basic.get("iDefense"),
        "法防": basic.get("iMagDef"),
        "金币": basic.get("iGold"),
        "银币": basic.get("iSilver"),
        "仙玉": basic.get("iXianYu"),
        "人物评分": basic.get("iScore"),
        "召唤灵评分": basic.get("iBeastScore"),
        "装备评分": basic.get("iEquipScore"),
        "修炼评分": basic.get("iXiuScore"),
        "身上装备数": len(items.get("equipped") or []),
        "仓库物品种类": len(warehouse_items),
        "仓库物品总数": _total_amount(warehouse_items),
        "仓库物品明细": _format_items_detail(warehouse_items, registry),
        "背包物品种类": len(bag_items),
        "背包物品总数": _total_amount(bag_items),
        "背包物品明细": _format_items_detail(bag_items, registry),
        "召唤灵数": len(summon_list),
        "召唤灵明细": _format_summons_detail(summon_list, registry),
    }


def _role_context(profile: dict[str, Any]) -> dict[str, Any]:
    meta = profile.get("meta") or {}
    summary = (profile.get("character") or {}).get("summary") or {}
    basic = (profile.get("character") or {}).get("basic_attrs") or {}
    return {
        "ordersn": meta.get("ordersn"),
        "role_name": summary.get("role_name") or meta.get("equip_name"),
        "school": summary.get("school"),
        "level": summary.get("level"),
        "price": _price_yuan(summary, meta),
        "server_name": summary.get("server_name") or meta.get("server_name"),
        "desc_sumup": summary.get("desc_sumup"),
        "人物评分": basic.get("iScore"),
        "召唤灵评分": basic.get("iBeastScore"),
        "装备评分": basic.get("iEquipScore"),
    }


def _empty_detail_row(context: dict[str, Any]) -> dict[str, Any]:
    return {
        **context,
        "明细类型": "",
        "名称": "",
        "type_id": "",
        "数量": "",
        "穿戴": "",
        "属性": "",
        "特效": "",
        "单项评分": "",
        "备注": "",
        "召唤等级": "",
        "气血": "",
        "速度": "",
        "成长": "",
        "宠物评分": "",
        "参战等级": "",
        "技能": "",
        "参战": "",
    }


def profile_to_unified_detail_rows(
    profile: dict[str, Any],
    registry: TypeNameRegistry | None = None,
) -> list[dict[str, Any]]:
    """一个角色展开为多行明细，合并装备/道具/召唤灵。"""
    reg = registry or get_registry()
    ctx = _role_context(profile)
    items = profile.get("items") or {}
    summons = profile.get("summons") or {}
    rows: list[dict[str, Any]] = []

    item_categories = [
        ("身上装备", "equipped"),
        ("仓库装备", "warehouse_equips"),
        ("仓库物品", "warehouse_items"),
        ("背包物品", "bag_items"),
    ]
    for label, key in item_categories:
        for item in items.get(key) or []:
            extra = _item_extra_fields(item)
            rows.append(
                {
                    **ctx,
                    "明细类型": label,
                    "名称": reg.lookup(item.get("type_id")) or "",
                    "type_id": item.get("type_id"),
                    "数量": item.get("amount"),
                    "穿戴": item.get("wearing"),
                    "属性": item.get("props"),
                    "特效": item.get("special"),
                    "单项评分": item.get("score"),
                    "备注": extra.get("备注"),
                    "召唤等级": extra.get("等级"),
                    "气血": "",
                    "速度": "",
                    "成长": "",
                    "宠物评分": "",
                    "参战等级": "",
                    "技能": "",
                    "参战": "",
                }
            )

    summon_categories = [
        ("召唤灵", "summon_list"),
        ("仓库召唤灵", "warehouse_summons"),
        ("子女", "child_list"),
    ]
    for label, key in summon_categories:
        for pet in summons.get(key) or []:
            raw = pet.get("raw") or {}
            score = pet.get("score") if pet.get("score") is not None else raw.get("mark")
            fight_grade = pet.get("fight_grade") if pet.get("fight_grade") is not None else raw.get("fight_grade")
            rows.append(
                {
                    **ctx,
                    "明细类型": label,
                    "名称": pet.get("name") or reg.lookup(pet.get("type_id")) or "",
                    "type_id": pet.get("type_id"),
                    "数量": "",
                    "穿戴": "",
                    "属性": "",
                    "特效": "",
                    "单项评分": "",
                    "备注": "",
                    "召唤等级": pet.get("level"),
                    "气血": pet.get("hp_max"),
                    "速度": pet.get("speed"),
                    "成长": pet.get("growth"),
                    "宠物评分": score,
                    "参战等级": fight_grade,
                    "技能": _join_list([reg.lookup_skill(s) for s in (pet.get("skills") or [])]),
                    "参战": pet.get("fight_status"),
                }
            )

    if not rows:
        summary_row = _empty_detail_row(ctx)
        summary_row["明细类型"] = "无明细"
        rows.append(summary_row)

    return rows


def profile_to_equip_rows(
    profile: dict[str, Any],
    registry: TypeNameRegistry | None = None,
) -> list[dict[str, Any]]:
    reg = registry or get_registry()
    meta = profile.get("meta") or {}
    summary = (profile.get("character") or {}).get("summary") or {}
    items = profile.get("items") or {}
    base = {
        "ordersn": meta.get("ordersn"),
        "role_name": summary.get("role_name") or meta.get("equip_name"),
    }

    rows: list[dict[str, Any]] = []
    categories = [
        ("身上装备", "equipped"),
        ("仓库装备", "warehouse_equips"),
        ("背包物品", "bag_items"),
        ("仓库物品", "warehouse_items"),
    ]
    for label, key in categories:
        for item in items.get(key) or []:
            extra = _item_extra_fields(item)
            rows.append(
                {
                    **base,
                    "类别": label,
                    "type_id": item.get("type_id"),
                    "名称": reg.lookup(item.get("type_id")) or "",
                    "穿戴": item.get("wearing"),
                    "数量": item.get("amount"),
                    "属性": item.get("props"),
                    "特效": item.get("special"),
                    "评分": item.get("score"),
                    **extra,
                }
            )
    return rows


def profile_to_summon_rows(
    profile: dict[str, Any],
    registry: TypeNameRegistry | None = None,
) -> list[dict[str, Any]]:
    reg = registry or get_registry()
    meta = profile.get("meta") or {}
    summary = (profile.get("character") or {}).get("summary") or {}
    summons = profile.get("summons") or {}
    base = {
        "ordersn": meta.get("ordersn"),
        "role_name": summary.get("role_name") or meta.get("equip_name"),
    }

    rows: list[dict[str, Any]] = []
    for label, key in [("召唤灵", "summon_list"), ("仓库召唤灵", "warehouse_summons"), ("子女", "child_list")]:
        for pet in summons.get(key) or []:
            rows.append(
                {
                    **base,
                    "类别": label,
                    "名称": pet.get("name") or reg.lookup(pet.get("type_id")) or "",
                    "type_id": pet.get("type_id"),
                    "等级": pet.get("level"),
                    "气血": pet.get("hp_max"),
                    "速度": pet.get("speed"),
                    "成长": pet.get("growth"),
                    "技能": _join_list([reg.lookup_skill(s) for s in (pet.get("skills") or [])]),
                    "参战": pet.get("fight_status"),
                }
            )
    return rows


def list_item_to_role_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "ordersn": item.get("ordersn"),
        "eid": item.get("eid"),
        "serverid": item.get("serverid"),
        "server_name": item.get("server_name"),
        "role_name": item.get("role_name"),
        "school": item.get("school"),
        "level": item.get("level"),
        "price": item.get("price") if (item.get("price") is not None and item.get("price") < 1000) else to_yuan(item.get("price_raw") or item.get("price")),
        "desc_sumup": item.get("desc_sumup"),
        "detail_url": item.get("detail_url"),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_profiles_to_csv(
    output_dir: Path,
    profiles: Iterable[dict[str, Any]],
    *,
    prefix: str = "",
    registry: TypeNameRegistry | None = None,
) -> dict[str, Path]:
    reg = registry or get_registry()
    output_dir.mkdir(parents=True, exist_ok=True)
    role_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    for profile in profiles:
        role_rows.append(profile_to_role_row(profile, reg))
        detail_rows.extend(profile_to_unified_detail_rows(profile, reg))

    paths = {
        "roles": output_dir / f"{prefix}roles.csv",
        "detail": output_dir / f"{prefix}detail.csv",
    }
    _write_csv(paths["roles"], role_rows)
    _write_csv(paths["detail"], detail_rows)
    return paths


def export_list_to_csv(output_dir: Path, items: list[dict[str, Any]]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "roles.csv"
    _write_csv(path, [list_item_to_role_row(item) for item in items])
    return path


def load_profiles_from_dir(output_dir: Path) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for path in sorted(output_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        profiles.append(json.loads(path.read_text(encoding="utf-8")))
    return profiles
