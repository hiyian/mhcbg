from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

JSONBIN_API = "https://api.jsonbin.io/v3/b"


class JsonBinClient:
    def __init__(self, master_key: str, bin_id: str | None = None):
        self.master_key = master_key
        self.bin_id = bin_id
        self._headers = {
            "Content-Type": "application/json",
            "X-Master-Key": master_key,
        }

    def create(self, data: dict[str, Any], *, name: str = "mhcbg-data") -> str:
        headers = {**self._headers, "X-Bin-Name": name, "X-Bin-Private": "false"}
        resp = httpx.post(JSONBIN_API, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        self.bin_id = payload["metadata"]["id"]
        return self.bin_id

    def update(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self.bin_id:
            raise ValueError("缺少 bin_id，请先 create 或在配置中指定")
        url = f"{JSONBIN_API}/{self.bin_id}"
        resp = httpx.put(url, headers=self._headers, json=data, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def read(self) -> dict[str, Any]:
        if not self.bin_id:
            raise ValueError("缺少 bin_id")
        url = f"{JSONBIN_API}/{self.bin_id}/latest"
        resp = httpx.get(url, timeout=60)
        resp.raise_for_status()
        return resp.json()["record"]


def load_master_key() -> str:
    key = os.environ.get("JSONBIN_MASTER_KEY", "")
    if key:
        return key
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("JSONBIN_MASTER_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    config_path = Path("jsonbin.config.json")
    if config_path.exists():
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        key = cfg.get("master_key") or cfg.get("masterKey")
        if key:
            return key
    raise FileNotFoundError(
        "未找到 JSONBin Master Key。请创建 .env 或 jsonbin.config.json"
    )


def load_bin_id() -> str | None:
    config_path = Path("jsonbin.config.json")
    if config_path.exists():
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        return cfg.get("bin_id") or cfg.get("binId")
    return os.environ.get("JSONBIN_BIN_ID")


def save_bin_id(bin_id: str) -> None:
    config_path = Path("jsonbin.config.json")
    cfg: dict[str, Any] = {}
    if config_path.exists():
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    cfg["bin_id"] = bin_id
    config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    js = (
        f"window.MHCBG_CONFIG = {{\n"
        f'  binId: "{bin_id}",\n'
        f'  apiUrl: "https://api.jsonbin.io/v3/b/{bin_id}/latest",\n'
        f"}};\n"
    )
    for path in (Path("docs/config.js"), Path("web/config.js")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(js, encoding="utf-8")


def build_compact_role(profile: dict[str, Any], registry: Any) -> dict[str, Any]:
    from .csv_export import profile_to_role_row, profile_to_unified_detail_rows

    row = profile_to_role_row(profile, registry)
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
    return compact


def build_payload(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    from .type_names import get_registry

    reg = get_registry()
    roles = [build_compact_role(p, reg) for p in profiles]
    detail_count = sum(len(r.get("equips", [])) + len(r.get("summons", [])) for r in roles)

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_roles": len(roles),
        "total_details": detail_count,
        "roles": roles,
    }
