"""把抓取结果直接写入 Vercel Postgres（Neon），跳过本地 MySQL。

连接串来源（优先级从高到低）：
1. 环境变量 POSTGRES_URL_NON_POOLING（批量写入优先用直连）
2. 环境变量 POSTGRES_URL / DATABASE_URL
3. postgres.config.json 文件：{"url": "...", "url_non_pooling": "..."}

表结构与 cbg_query/postgres/init.sql 一致，首次写入会自动建表（IF NOT EXISTS）。
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import psycopg
    from psycopg.types.json import Jsonb
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "写入 Postgres 需要 psycopg，请先安装：\n  pip install 'psycopg[binary]'"
    ) from exc

from .payload import build_compact_role

ROOT = Path(__file__).resolve().parents[1]

SOLD_STATUS = "sold"

ROLE_DETAIL_KEYS = frozenset(
    {
        "ordersn",
        "serverid",
        "server_name",
        "area_name",
        "role_name",
        "school",
        "level",
        "price",
        "金币",
        "冻结金币",
        "sale_status",
        "sale_status_label",
        "selling_time",
        "pass_fair_show",
        "create_time",
        "sale_time_text",
    }
)

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS servers (
  id SERIAL PRIMARY KEY,
  server_key VARCHAR(64) NOT NULL UNIQUE,
  serverid INTEGER,
  server_name VARCHAR(64) NOT NULL DEFAULT '',
  area_name VARCHAR(64) NOT NULL DEFAULT '',
  gold_min_wan INTEGER,
  synced_at TIMESTAMP(6) NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
  id BIGSERIAL PRIMARY KEY,
  server_id INTEGER NOT NULL REFERENCES servers (id) ON DELETE CASCADE,
  ordersn VARCHAR(128) NOT NULL,
  area_name VARCHAR(64) NOT NULL DEFAULT '',
  server_name VARCHAR(64) NOT NULL DEFAULT '',
  role_name VARCHAR(64) NOT NULL DEFAULT '',
  school VARCHAR(32) NOT NULL DEFAULT '',
  level INTEGER,
  price NUMERIC(12, 2),
  gold BIGINT,
  frozen_gold_wan INTEGER,
  sale_status VARCHAR(16),
  selling_time BIGINT,
  payload JSONB NOT NULL,
  synced_at TIMESTAMP(6) NOT NULL,
  UNIQUE (server_id, ordersn)
);

CREATE INDEX IF NOT EXISTS idx_roles_area ON roles (area_name);
CREATE INDEX IF NOT EXISTS idx_roles_school ON roles (school);
CREATE INDEX IF NOT EXISTS idx_roles_price ON roles (price);
CREATE INDEX IF NOT EXISTS idx_roles_gold ON roles (gold);
CREATE INDEX IF NOT EXISTS idx_roles_sale_status ON roles (sale_status);
CREATE INDEX IF NOT EXISTS idx_roles_server_id ON roles (server_id);
"""


def _load_config_file() -> dict[str, Any]:
    path = ROOT / "postgres.config.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def get_pg_url(*, prefer_non_pooling: bool = True) -> str:
    cfg = _load_config_file()
    if prefer_non_pooling:
        url = os.environ.get("POSTGRES_URL_NON_POOLING") or cfg.get("url_non_pooling")
        if url:
            return url
    for env_key in ("POSTGRES_URL", "DATABASE_URL"):
        url = os.environ.get(env_key)
        if url:
            return url
    url = cfg.get("url") or cfg.get("url_non_pooling")
    if url:
        return url
    raise RuntimeError(
        "未找到 Postgres 连接串。请设置环境变量 POSTGRES_URL(_NON_POOLING)，"
        "或复制 postgres.config.example.json 为 postgres.config.json 并填入 Neon 连接串。"
    )


@contextmanager
def pg_conn(*, prefer_non_pooling: bool = True) -> Iterator["psycopg.Connection"]:
    conn = psycopg.connect(get_pg_url(prefer_non_pooling=prefer_non_pooling))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_schema(conn: "psycopg.Connection") -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)


def upsert_server(conn: "psycopg.Connection", server: dict[str, Any]) -> int:
    now = _utc_now()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO servers (server_key, serverid, server_name, area_name, gold_min_wan, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (server_key) DO UPDATE SET
              serverid = EXCLUDED.serverid,
              server_name = EXCLUDED.server_name,
              area_name = EXCLUDED.area_name,
              gold_min_wan = EXCLUDED.gold_min_wan,
              synced_at = EXCLUDED.synced_at
            RETURNING id
            """,
            (
                server["key"],
                server.get("serverid"),
                server.get("server_name") or server["key"],
                server.get("area_name") or "",
                server.get("gold_min_wan"),
                now,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"无法写入服务器记录: {server['key']}")
        return int(row[0])


def upsert_role(conn: "psycopg.Connection", server_id: int, role: dict[str, Any]) -> None:
    now = _utc_now()
    detail = {k: v for k, v in role.items() if k not in ROLE_DETAIL_KEYS}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO roles (
              server_id, ordersn, area_name, server_name, role_name, school, level,
              price, gold, frozen_gold_wan, sale_status, selling_time, payload, synced_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (server_id, ordersn) DO UPDATE SET
              area_name = EXCLUDED.area_name,
              server_name = EXCLUDED.server_name,
              role_name = EXCLUDED.role_name,
              school = EXCLUDED.school,
              level = EXCLUDED.level,
              price = EXCLUDED.price,
              gold = EXCLUDED.gold,
              frozen_gold_wan = EXCLUDED.frozen_gold_wan,
              sale_status = EXCLUDED.sale_status,
              selling_time = EXCLUDED.selling_time,
              payload = EXCLUDED.payload,
              synced_at = EXCLUDED.synced_at
            """,
            (
                server_id,
                role.get("ordersn"),
                role.get("area_name") or "",
                role.get("server_name") or "",
                role.get("role_name") or "",
                role.get("school") or "",
                role.get("level"),
                role.get("price"),
                role.get("金币"),
                role.get("冻结金币"),
                role.get("sale_status"),
                role.get("selling_time"),
                Jsonb(detail),
                now,
            ),
        )


def mark_missing_as_sold(
    conn: "psycopg.Connection",
    server_id: int,
    current_ordersns: list[str],
) -> int:
    """把该服下「不在本次最新列表里」的角色标记为已售出（sold）。

    只标记、不删除，保留历史数据。current_ordersns 为空时不做任何操作，
    避免误把整个服清成 sold。返回被标记的行数。
    """
    ordersns = [sn for sn in current_ordersns if sn]
    if not ordersns:
        return 0
    now = _utc_now()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE roles
            SET sale_status = %s, synced_at = %s
            WHERE server_id = %s
              AND ordersn <> ALL(%s)
              AND sale_status IS DISTINCT FROM %s
            """,
            (SOLD_STATUS, now, server_id, ordersns, SOLD_STATUS),
        )
        return cur.rowcount or 0


def sync_profiles_to_pg(
    profiles: list[dict[str, Any]],
    *,
    server: dict[str, Any],
    ensure: bool = True,
    conn: "psycopg.Connection | None" = None,
    mark_missing_sold: bool = False,
) -> dict[str, Any]:
    """把角色 profile 列表直接 upsert 到 Postgres。

    server: 至少含 key，最好含 serverid/server_name/area_name/gold_min_wan。
    conn: 传入已有连接则复用（批量抓取时避免频繁重连）；否则自建连接。
    mark_missing_sold: 为 True 时把该服下未在本批 profiles 出现的角色标记为 sold
        （仅用于「全量列表」抓取，profiles 必须覆盖当前在售全集）。
    """
    from .type_names import get_registry

    reg = get_registry()
    roles = [build_compact_role(p, reg) for p in profiles]
    stats = {"marked_sold": 0}

    def _write(c: "psycopg.Connection") -> int:
        if ensure:
            ensure_schema(c)
        server_id = upsert_server(c, server)
        for role in roles:
            upsert_role(c, server_id, role)
        if mark_missing_sold:
            current = [role.get("ordersn") for role in roles]
            stats["marked_sold"] = mark_missing_as_sold(c, server_id, current)
        return server_id

    if conn is not None:
        _write(conn)
    else:
        with pg_conn(prefer_non_pooling=True) as c:
            _write(c)

    return {
        "server": server.get("key"),
        "total_roles": len(roles),
        "marked_sold": stats["marked_sold"],
    }


def sync_crawl_result_to_pg(
    result: dict[str, Any],
    *,
    ensure: bool = True,
    conn: "psycopg.Connection | None" = None,
    mark_missing_sold: bool = True,
) -> dict[str, Any]:
    """把 run_crawl 的返回结果（含 items[].profile）写入 Postgres。

    默认把该服下未在本次列表出现的角色标记为已售出（差集）。
    """
    server = result.get("server") or {}
    if not server.get("key"):
        raise ValueError("缺少 server.key，无法写入 Postgres")
    profiles = [
        item["profile"]
        for item in result.get("items", [])
        if item.get("profile")
    ]
    if not profiles:
        return {"server": server.get("key"), "total_roles": 0, "marked_sold": 0}
    return sync_profiles_to_pg(
        profiles,
        server=server,
        ensure=ensure,
        conn=conn,
        mark_missing_sold=mark_missing_sold,
    )
