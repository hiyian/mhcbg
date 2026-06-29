# 梦幻西游手游藏宝阁工具

爬取藏宝阁角色数据 → 导出 CSV → 上传 JSONBin → Web 查询界面。

## 目录

```
mhcbg/
├── cbg/              # API 客户端、CSV/JSONBin
├── scripts/          # 爬虫、导出、上传脚本
├── docs/             # GitHub Pages 查询界面
├── output/           # 抓取结果（gitignore）
└── data/             # type_id 映射缓存（gitignore）
```

## 本地抓取

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json      # 填入 Cookie
cp search.example.json search.json
python scripts/crawl_search.py
python scripts/update_type_names.py     # 可选：中文名映射
python scripts/export_csv.py            # 导出 detail.csv
```

## 上传 JSONBin

```bash
cp jsonbin.config.example.json jsonbin.config.json
# 填入 master_key（JSONBin API Keys 页面）

python scripts/upload_jsonbin.py --create   # 首次
python scripts/upload_jsonbin.py            # 后续更新
```

上传后会更新 `docs/config.js` 中的 binId。

## Web 查询界面

- 本地：用浏览器打开 `docs/index.html`（需联网读 JSONBin）
- 线上：GitHub Pages → `https://hiyian.github.io/mhcbg/`

功能：关键词搜索、价格筛选、角色汇总 / 明细 / 召唤灵（含**宠物评分**）三个视图。

## 数据字段

- 价格 API 值为分，展示时 **÷100** 为元
- 召唤灵评分来自 API 字段 `mark`

## 安全

- `config.json`（Cookie）、`jsonbin.config.json`（Master Key）**不要提交 Git**
- Master Key 仅用于本机上传脚本，前端通过公开 bin 读取数据
