#!/usr/bin/env python3
"""拉取单个角色的三部分信息：人物属性 / 装备道具 / 召唤灵。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbg import CbgApiError, CbgClient, SessionTimeoutError, fetch_role_profile, to_yuan


def print_summary(profile: dict) -> None:
    meta = profile["meta"]
    char = profile["character"]
    summary = char["summary"]
    basic = char["basic_attrs"]

    print("=" * 50)
    print(f"角色: {summary.get('role_name')} | {summary.get('school')} | {summary.get('level')}级")
    price = summary.get("price")
    price_text = f"¥{price:g}" if price is not None else "-"
    print(f"区服: {summary.get('server_name')} | 价格: {price_text}")
    print(f"ordersn: {meta.get('ordersn')}")
    if summary.get("desc_sumup"):
        print(f"摘要: {summary.get('desc_sumup')}")
    if summary.get("highlights"):
        print(f"亮点: {', '.join(summary['highlights'])}")

    print("\n【人物属性】")
    attrs = [
        ("气血", basic.get("iHp_Max")),
        ("魔法", basic.get("iMp_Max")),
        ("物伤", basic.get("iDamage")),
        ("法伤", basic.get("iMagDam")),
        ("速度", basic.get("iSpeed")),
        ("防御", basic.get("iDefense")),
        ("法防", basic.get("iMagDef")),
        ("金币", basic.get("iGold")),
        ("仙玉", basic.get("iXianYu")),
    ]
    print("  " + " | ".join(f"{k}:{v}" for k, v in attrs if v is not None))

    print("\n【装备 / 道具】")
    items = profile["items"]
    print(f"  身上装备: {len(items['equipped'])} 件")
    for eq in items["equipped"]:
        wear = "穿戴" if eq["wearing"] else "未穿"
        print(f"    - [{wear}] type={eq['type_id']} 属性={eq.get('props') or '-'}")
    print(f"  仓库物品: {len(items['warehouse_items'])} 格")
    print(f"  背包物品: {len(items['bag_items'])} 格")

    print("\n【召唤灵】")
    summons = profile["summons"]["summon_list"]
    print(f"  共 {len(summons)} 只")
    for pet in summons[:10]:
        skills = ", ".join(pet["skills"][:6]) or "-"
        print(
            f"    - {pet['name']} Lv{pet['level']} "
            f"速{pet.get('speed')} 技能:{skills}"
        )
    if len(summons) > 10:
        print(f"    ... 还有 {len(summons) - 10} 只")


def main() -> None:
    parser = argparse.ArgumentParser(description="拉取角色三部分详情")
    parser.add_argument("--ordersn", required=True, help="角色 ordersn")
    parser.add_argument("--serverid", default="911", help="服务器 ID")
    parser.add_argument("-c", "--config", default="config.json")
    parser.add_argument("-o", "--output", help="保存完整 JSON 到文件")
    parser.add_argument("--raw", action="store_true", help="输出完整 JSON 到终端")
    args = parser.parse_args()

    if not Path(args.config).exists():
        print("未找到 config.json")
        sys.exit(1)

    with CbgClient(args.config) as client:
        try:
            profile = fetch_role_profile(
                client,
                serverid=args.serverid,
                ordersn=args.ordersn,
            )
        except SessionTimeoutError as exc:
            print(f"登录失效: {exc}")
            sys.exit(2)
        except CbgApiError as exc:
            print(f"API 错误: {exc}")
            sys.exit(1)

    if args.output:
        Path(args.output).write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已保存到 {args.output}")

    if args.raw:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    elif not args.output:
        print_summary(profile)


if __name__ == "__main__":
    main()
