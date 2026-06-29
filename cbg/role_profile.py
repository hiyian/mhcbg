from __future__ import annotations

import json
from typing import Any

from .client import CbgClient
from .price import to_yuan


def _parse_equip_desc(raw: str | dict | None) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def _summon_brief(pet: dict[str, Any]) -> dict[str, Any]:
    skills = pet.get("skill") or []
    skill_names = []
    for s in skills:
        if not isinstance(s, dict):
            continue
        name = s.get("cName") or s.get("name")
        if name:
            skill_names.append(name)
        elif s.get("id") is not None:
            skill_names.append(f"#{s['id']}")
        elif s.get("iSkill") is not None:
            skill_names.append(f"#{s['iSkill']}")
    return {
        "name": pet.get("cName") or pet.get("stall_name") or "",
        "type_id": pet.get("iType"),
        "level": pet.get("iGrade"),
        "hp_max": pet.get("iHp_Max"),
        "speed": pet.get("iSpeed"),
        "growth": pet.get("growup"),
        "score": pet.get("mark"),
        "fight_grade": pet.get("fight_grade"),
        "skills": skill_names,
        "fight_status": pet.get("fight_status"),
        "raw": pet,
    }


def _equip_brief(item: dict[str, Any]) -> dict[str, Any]:
    exinfo = item.get("exinfo") or {}
    return {
        "type_id": item.get("iType"),
        "wearing": bool(item.get("iWear")),
        "amount": item.get("iAmount", 1),
        "props": exinfo.get("cProp") or exinfo.get("AddPoint"),
        "special": exinfo.get("cSpecial"),
        "score": exinfo.get("iScore"),
        "raw": item,
    }


def _item_brief(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "type_id": item.get("iType"),
        "amount": item.get("iAmount", 1),
        "raw": item,
    }


def _list_brief(items: list[Any] | None, mapper) -> list[dict[str, Any]]:
    if not items:
        return []
    return [mapper(x) for x in items if isinstance(x, dict)]


def build_role_profile(detail: dict[str, Any]) -> dict[str, Any]:
    """将 get_equip_detail 响应整理为人物 / 装备道具 / 召唤灵三部分。"""
    equip = detail.get("equip") or detail.get("equip_data") or {}
    other_info = equip.get("other_info") or {}
    desc = _parse_equip_desc(equip.get("equip_desc"))

    basic = desc.get("basic") or {}
    skill = desc.get("skill") or {}
    jingmai = desc.get("jingmai") or {}
    fabao = desc.get("fabao") or {}
    other = desc.get("other") or {}
    item_equip = desc.get("item_equip") or {}
    summon_child = desc.get("summon_child") or {}

    character_attrs = {
        "summary": {
            "role_name": equip.get("format_equip_name") or equip.get("equip_name"),
            "school": other_info.get("school_desc") or other_info.get("school"),
            "level": equip.get("equip_level") or basic.get("iGrade"),
            "level_desc": other_info.get("level_desc"),
            "price": to_yuan(equip.get("price")),
            "price_raw": equip.get("price"),
            "server_name": equip.get("server_name"),
            "area_name": equip.get("area_name"),
            "highlights": other_info.get("highlights") or equip.get("highlights"),
            "desc_sumup": other_info.get("desc_sumup") or equip.get("desc_sumup_short"),
        },
        "basic_attrs": basic,
        "skills": skill,
        "jingmai": jingmai,
        "fabao": fabao,
        "other": other,
        "other_info": other_info,
    }

    items_equips = {
        "equipped": _list_brief(item_equip.get("equip_list"), _equip_brief),
        "warehouse_equips": _list_brief(item_equip.get("ware_equip_list"), _equip_brief),
        "warehouse_items": _list_brief(item_equip.get("ware_item_list"), _item_brief),
        "bag_items": _list_brief(item_equip.get("item_list"), _item_brief),
        "timebag_items": _list_brief(item_equip.get("timebag_item_list"), _item_brief),
        "fashion_items": _list_brief(item_equip.get("fashion_item_list"), _item_brief),
        "mount_items": _list_brief(item_equip.get("mount_item_list"), _item_brief),
        "xingyin": _list_brief(item_equip.get("xingyin_list"), _item_brief),
        "recycle_equips": _list_brief(item_equip.get("recycle_equip_list"), _equip_brief),
        "recycle_items": _list_brief(item_equip.get("recycle_item_list"), _item_brief),
        "raw": item_equip,
    }

    summons = {
        "summon_list": _list_brief(summon_child.get("summon_list"), _summon_brief),
        "warehouse_summons": _list_brief(summon_child.get("ware_summon_list"), _summon_brief),
        "child_list": _list_brief(summon_child.get("child_list"), _summon_brief),
        "precious_summons": _list_brief(summon_child.get("precious_summon_flist"), _summon_brief),
        "recycle_summons": _list_brief(summon_child.get("recycle_summon_list"), _summon_brief),
        "raw": summon_child,
    }

    return {
        "meta": {
            "ordersn": equip.get("game_ordersn") or equip.get("ordersn"),
            "eid": equip.get("eid"),
            "serverid": equip.get("serverid"),
            "server_name": equip.get("server_name"),
            "equip_name": equip.get("format_equip_name") or equip.get("equip_name"),
            "price": to_yuan(equip.get("price")),
            "price_raw": equip.get("price"),
        },
        "character": character_attrs,
        "items": items_equips,
        "summons": summons,
    }


def fetch_role_profile(
    client: CbgClient,
    *,
    serverid: int | str,
    ordersn: str,
    **extra: Any,
) -> dict[str, Any]:
    detail = client.get_equip_detail(
        serverid=serverid,
        ordersn=ordersn,
        exclude_equip_desc=0,
        **extra,
    )
    return build_role_profile(detail)
