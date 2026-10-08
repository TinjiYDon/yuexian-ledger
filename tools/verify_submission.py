"""交稿自检：验证 demo 页面的数字与规则复算一致。

`README` 与 `docs/提交清单.md` 都声称「页脚三个数由规则对全部样例复算，
不是手填的」。这个声称必须在交稿前机器验证 —— 评审现场会打开页面，
也会当场问「这些数怎么来的」。

本脚本从 `demo/index.html` 里解析出内嵌的 DATA，与 `yuexian.rules.score`
的实时复算逐项比对，任何一项漂移即退出码 1。

    python tools/verify_submission.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yuexian.rules import load_dataset, score  # noqa: E402

DEMO = ROOT / "demo" / "index.html"

# 页脚展示的统计量 -> 必须与规则复算逐字相等
CHECKED = (
    "birth_station_ratio",
    "birth_station_hit",
    "birth_station_total",
    "country_mix_count",
    "weight_hold_count",
)


def demo_data() -> dict:
    if not DEMO.exists():
        raise SystemExit(f"缺少 {DEMO}，先跑 python -m yuexian.build_demo")
    html = DEMO.read_text(encoding="utf-8")
    match = re.search(r"const DATA = (\{.*?\});\s*\n", html, re.S)
    if not match:
        raise SystemExit("demo/index.html 里找不到内嵌的 DATA")
    return json.loads(match.group(1))


def main() -> int:
    data = demo_data()
    authoritative = score(load_dataset())

    print("demo 页脚数字 vs 规则复算")
    print("-" * 52)
    failures: list[str] = []
    for key in CHECKED:
        shown, expected = data.get(key), authoritative.get(key)
        ok = shown is not None and abs(float(shown) - float(expected)) < 1e-9
        print(f"{key:24}{str(shown):>10}{str(expected):>10}  {'一致' if ok else '不一致'}")
        if not ok:
            failures.append(f"{key}: 页面 {shown!r} vs 规则 {expected!r}")

    # 主演示票必须是「先别申报」，这是清单第一条
    hero = next((s for s in data.get("shipments", []) if s.get("demo")), None)
    if hero is None:
        failures.append("没有标记 demo 的主演示票")
    elif hero.get("headline") != "先别申报":
        failures.append(f"主演示票第一眼不是「先别申报」：{hero.get('headline')!r}")

    print("-" * 52)
    if failures:
        print("交稿自检未通过：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("交稿自检通过：页脚数字全部由规则复算，主演示票为「先别申报」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())