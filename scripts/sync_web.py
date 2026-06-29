#!/usr/bin/env python3
"""同步 docs/ 到 web/（可选）。"""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
docs = ROOT / "docs"
web = ROOT / "web"
web.mkdir(exist_ok=True)
for name in ["index.html", "style.css", "app.js"]:
    shutil.copy2(docs / name, web / name)
print("已同步 docs -> web")
