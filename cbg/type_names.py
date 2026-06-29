from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

CONFIG_URL = "https://cbg-my.res.netease.com/js/game_auto_config.js"
DEFAULT_CACHE = Path("data/type_names.json")

# (config_key, name_field, category) — 按优先级排列
_NAME_SOURCES: list[tuple[str, str | None, str]] = [
    ("infoitem", "cName", "物品"),
    ("infobeast", "name", "召唤灵"),
    ("infopetequipitem", "cName", "召唤灵装备"),
    ("infomount", "cName", "坐骑"),
    ("infofashion", "name", "时装"),
    ("infofashion_cloth", "name", "时装"),
    ("infoequip_xingyin_green", "cName", "星印"),
    ("infoequip_rune_raw", "cName", "星盘胚"),
    ("infoequip_special", "cName", "特技"),
    ("info_fb_basic_info", "name", "法宝"),
    ("infochildskill", "cName", "子女技能"),
    ("infobeastskill", "cName", "技能"),
    ("info_advanced_pet_skills", None, "技能"),
    ("advanced_pet_phy_skill_from_cbg", "skill_name", "技能"),
    ("advanced_pet_mag_skill_from_cbg", "skill_name", "技能"),
    ("inforuneskill", "cName", "星盘技能"),
    ("infoxingyinskill", "cName", "星印技能"),
]


def _extract_name(entry: Any, field: str | None) -> str | None:
    if entry is None:
        return None
    if field is None:
        return str(entry) if entry else None
    if isinstance(entry, dict):
        name = entry.get(field)
        return str(name) if name else None
    return None


def _parse_config_js(text: str) -> dict[str, Any]:
    match = re.search(r"var CBG_GAME_CONFIG=(\{.*\});?\s*$", text, re.S)
    if not match:
        raise ValueError("无法解析 game_auto_config.js")
    return json.loads(match.group(1))


def build_type_name_map(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    """构建 type_id -> {name, category} 映射。"""
    result: dict[str, dict[str, str]] = {}
    for key, field, category in _NAME_SOURCES:
        table = config.get(key)
        if not isinstance(table, dict):
            continue
        for type_id, entry in table.items():
            sid = str(type_id)
            if sid in result:
                continue
            name = _extract_name(entry, field)
            if name:
                result[sid] = {"name": name, "category": category}
    return result


def download_type_name_map(url: str = CONFIG_URL) -> dict[str, dict[str, str]]:
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    config = _parse_config_js(resp.text)
    return build_type_name_map(config)


class TypeNameRegistry:
    def __init__(self, cache_path: str | Path = DEFAULT_CACHE):
        self.cache_path = Path(cache_path)
        self._map: dict[str, dict[str, str]] = {}
        self.load()

    def load(self) -> None:
        if self.cache_path.exists():
            self._map = json.loads(self.cache_path.read_text(encoding="utf-8"))
        else:
            self.refresh()

    def refresh(self) -> int:
        self._map = download_type_name_map()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return len(self._map)

    def lookup(self, type_id: Any) -> str | None:
        if type_id is None or type_id == "":
            return None
        key = str(type_id).lstrip("#")
        entry = self._map.get(key)
        return entry["name"] if entry else None

    def lookup_skill(self, skill: str) -> str:
        """将 #526 或 526 转为技能名。"""
        raw = str(skill).lstrip("#")
        name = self.lookup(raw)
        return name or skill

    def format_type(self, type_id: Any, amount: int | None = None) -> str:
        name = self.lookup(type_id) or str(type_id)
        if amount is not None and amount != 1:
            return f"{name}×{amount}"
        return name


_default_registry: TypeNameRegistry | None = None


def get_registry(cache_path: str | Path = DEFAULT_CACHE) -> TypeNameRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = TypeNameRegistry(cache_path)
    return _default_registry
