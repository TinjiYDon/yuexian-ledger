"""把规则结果写进可离线打开的申报台页面。"""

import json
from pathlib import Path

from yuexian.rules import load_dataset, score

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "demo" / "index.html"

STATION = {
    "booking": "订舱",
    "packing": "装箱",
    "bl": "提单",
    "manifest": "舱单",
    "declaration": "报关单",
}


def main() -> None:
    payload = score(load_dataset())
    html = _page(payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(OUT)


def _page(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    stations = json.dumps(STATION, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>先别申报</title>
<style>
  body {{ margin: 0; font-family: "Microsoft YaHei", sans-serif; background: #f6f3ee; color: #1a1a1a; }}
  header {{ padding: 20px 28px 0; }}
  h1 {{ margin: 0; font-size: 28px; }}
  .sub {{ color: #5c6b73; margin-top: 6px; }}
  main {{ display: grid; grid-template-columns: 280px 1fr; gap: 16px; padding: 16px 28px 28px; }}
  ul {{ list-style: none; padding: 0; margin: 0; }}
  li {{ background: #fff; border: 1px solid #d9d3cb; padding: 12px; margin-bottom: 8px; cursor: pointer; }}
  li.hold {{ border-color: #b42318; }}
  .panel {{ background: #fff; border: 1px solid #d9d3cb; padding: 20px; min-height: 420px; }}
  .banner {{ background: #b42318; color: #fff; padding: 14px 16px; font-size: 28px; font-weight: 700; }}
  .banner.ok {{ background: #1f6b4a; }}
  .docs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }}
  .doc {{ border: 2px solid #b42318; background: #fff4f2; padding: 12px; }}
  .doc strong {{ font-size: 22px; color: #b42318; }}
  button {{ margin-top: 16px; background: #1b3a4b; color: #fff; border: 0; padding: 10px 14px; font-size: 16px; cursor: pointer; }}
  .note {{ margin-top: 12px; }}
  footer {{ padding: 0 28px 24px; color: #5c6b73; }}
</style>
</head>
<body>
<header>
  <h1>待申报</h1>
  <p class="sub">合成样例。规则判定。抽取看错的数字不参与结论。</p>
</header>
<main>
  <ul id="list"></ul>
  <section class="panel" id="panel"></section>
</main>
<footer id="foot"></footer>
<script>
const DATA = {data};
const STATION = {stations};
const list = document.getElementById("list");
const panel = document.getElementById("panel");
function show(item) {{
  const weight = item.blocks.find(b => b.kind === "gross_weight");
  const country = item.blocks.find(b => b.kind === "countries");
  const seal = item.blocks.find(b => b.kind === "seal_no" || b.kind === "container_no");
  const banner = item.verdict === "hold" ? "先别申报" : "可以申报";
  let body = `<div class="banner ${{item.verdict === "hold" ? "" : "ok"}}">${{banner}}</div>`;
  body += `<p>${{item.id}} · ${{item.title}}</p>`;
  if (weight) {{
    const pct = Math.round(weight.gap * 1000) / 10;
    const where = STATION[weight.birth_station] || "未知站点";
    body += `<div class="docs">
      <div class="doc"><div>装箱单</div><strong>${{weight.packing_kg}} kg</strong></div>
      <div class="doc"><div>提单</div><strong>${{weight.bl_kg}} kg</strong></div>
    </div>`;
    body += `<p>相差 ${{pct}}%。${{weight.if_send}}。</p>`;
    body += `<p>依据：这个数是在${{where}}改过的，不是模型看漏。</p>`;
    body += `<button type="button" id="send">${{weight.action}}</button>`;
    body += `<p class="note" id="sendNote" hidden>若现在发送：${{weight.if_send}}。海关接受申报之后不能随意改单。</p>`;
  }} else if (seal) {{
    body += `<p>${{seal.if_send}}。提单 ${{seal.bl}}，舱单 ${{seal.manifest}}。</p>`;
    body += `<p>${{seal.action}}</p>`;
  }} else if (!item.blocks.length) {{
    body += `<p>装箱毛重与提单一致，柜号和封条只有一版，四国口径没有被写成一格。</p>`;
  }}
  if (country) {{
    body += `<p>第二条：${{country.if_send}}。</p><p>${{country.action}}。</p>`;
  }}
  panel.innerHTML = body;
  const btn = document.getElementById("send");
  if (btn) btn.onclick = () => {{ document.getElementById("sendNote").hidden = false; }};
}}
DATA.shipments.forEach(item => {{
  const li = document.createElement("li");
  li.className = item.verdict === "hold" ? "hold" : "";
  li.textContent = `${{item.headline}} · ${{item.id}}`;
  li.onclick = () => show(item);
  list.appendChild(li);
}});
const demo = DATA.shipments.find(item => item.demo) || DATA.shipments[0];
show(demo);
const ratio = Math.round(DATA.birth_station_ratio * 100);
document.getElementById("foot").textContent =
  `页脚：站点改写落在装箱或舱单 ${{DATA.birth_station_hit}}/${{DATA.birth_station_total}}（${{ratio}}%） · 四国混填判错 ${{DATA.country_mix_count}} 票 · 毛重越过约 3% ${{DATA.weight_hold_count}} 票。${{DATA.threshold_note}}`;
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
