"""申报前规则。模型不得改写这里的判定。"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

STATION_ORDER = ["booking", "packing", "bl", "manifest", "declaration"]
BIRTH_TARGETS = {"packing", "manifest"}
STATION_LABELS = {
    "booking": "订舱",
    "packing": "装箱单",
    "bl": "提单",
    "manifest": "舱单",
    "declaration": "报关草稿",
}


def load_dataset(path: Path | None = None) -> dict:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "data" / "shipments.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _rewrites(observations: list[dict]) -> list[dict]:
    return [item for item in observations if item.get("label") == "rewrite"]


def birth_station(observations: list[dict]) -> str | None:
    """第一次相对上一站发生变化的站点。抽取误差不参与。"""
    chosen = []
    for station in STATION_ORDER:
        hits = [item for item in _rewrites(observations) if item["station"] == station]
        if hits:
            chosen.append(hits[-1])
    previous = None
    for item in chosen:
        if previous is not None and item["value"] != previous:
            return item["station"]
        previous = item["value"]
    return None


def value_at(observations: list[dict], station: str):
    hits = [item for item in _rewrites(observations) if item["station"] == station]
    if not hits:
        return None
    return hits[-1]["value"]


def weight_gap(packing, bl) -> float | None:
    if packing is None or bl in (None, 0):
        return None
    return abs(packing - bl) / abs(bl)


def country_mixed(countries: dict) -> bool:
    collapsed = countries.get("collapsed_value")
    if not collapsed:
        return False
    return collapsed == countries.get("origin") and countries.get("trade") != countries.get("origin")


def field_timeline(shipment: dict, field: str) -> list[dict]:
    """按业务站点给出字段的可视化证据链，不把 OCR 误差当作业务改写。"""
    observations = shipment.get(field, [])
    previous = None
    points = []
    for station in STATION_ORDER:
        value = value_at(observations, station)
        changed = value is not None and previous is not None and value != previous
        points.append(
            {
                "station": station,
                "label": STATION_LABELS[station],
                "value": value,
                "changed": changed,
            }
        )
        if value is not None:
            previous = value
    return points


def resolution_options(judged: dict) -> list[dict]:
    """给当前未解决的阻塞项列出可选的人工确认动作。"""
    options = []
    for block in judged["blocks"]:
        kind = block["kind"]
        if kind == "gross_weight":
            options.extend(
                [
                    {"token": "gross_weight:packing", "label": "以装箱单毛重为准"},
                    {"token": "gross_weight:bl", "label": "以提单毛重为准"},
                ]
            )
        elif kind in {"container_no", "seal_no"}:
            title = block["title"]
            options.extend(
                [
                    {"token": f"{kind}:bl", "label": f"以提单{title}为准"},
                    {"token": f"{kind}:manifest", "label": f"以舱单{title}为准"},
                ]
            )
        elif kind == "countries":
            options.append({"token": "countries:split", "label": "拆分贸易国、启运国、原产国和目的国"})
    return options


def resolve_shipment(shipment: dict, token: str) -> dict:
    """返回一份整改后的副本，原始样例和其业务轨迹保持不变。"""
    try:
        kind, source = token.split(":", 1)
    except ValueError as exc:
        raise ValueError(f"无效整改动作：{token}") from exc

    resolved = deepcopy(shipment)
    if kind == "countries" and source == "split":
        resolved.setdefault("countries", {}).pop("collapsed_value", None)
        return resolved

    fields = {
        "gross_weight": ("gross_weight_kg", ("packing", "bl", "manifest", "declaration")),
        "container_no": ("container_no", ("bl", "manifest")),
        "seal_no": ("seal_no", ("bl", "manifest")),
    }
    if kind not in fields:
        raise ValueError(f"不支持的整改字段：{kind}")
    field, stations = fields[kind]
    if source not in stations:
        raise ValueError(f"{kind} 不能以 {source} 为准")
    authoritative = value_at(resolved.get(field, []), source)
    if authoritative is None:
        raise ValueError(f"{source} 没有可用的 {kind} 值")
    for station in stations:
        if station != source:
            _set_rewrite_value(resolved[field], station, authoritative)
    return resolved


def _set_rewrite_value(observations: list[dict], station: str, value) -> None:
    for item in reversed(observations):
        if item.get("station") == station and item.get("label") == "rewrite":
            item["value"] = value
            return
    observations.append({"station": station, "value": value, "label": "rewrite"})


def judge_shipment(shipment: dict, threshold: float) -> dict:
    blocks = []
    weight_obs = shipment.get("gross_weight_kg", [])
    packing = value_at(weight_obs, "packing")
    bl = value_at(weight_obs, "bl")
    gap = weight_gap(packing, bl)
    weight_birth = birth_station(weight_obs)
    if gap is not None and gap > threshold:
        blocks.append(
            {
                "kind": "gross_weight",
                "birth_station": weight_birth,
                "packing_kg": packing,
                "bl_kg": bl,
                "gap": round(gap, 4),
                "action": "改提单毛重，或改装箱单后再发",
                "if_send": "毛重偏差超过约 3%，自动比对可能退单",
            }
        )

    for field, title in (("container_no", "柜号"), ("seal_no", "封条号")):
        obs = shipment.get(field, [])
        left = value_at(obs, "bl")
        right = value_at(obs, "manifest")
        if left is not None and right is not None and left != right:
            blocks.append(
                {
                    "kind": field,
                    "birth_station": birth_station(obs),
                    "title": title,
                    "bl": left,
                    "manifest": right,
                    "action": f"先改{title}，提单和舱单必须是同一版",
                    "if_send": f"{title}不一致，自动比对可能退单",
                }
            )

    if country_mixed(shipment.get("countries", {})):
        countries = shipment["countries"]
        blocks.append(
            {
                "kind": "countries",
                "birth_station": None,
                "action": "把贸易国、启运国、原产国、最终目的国分成四栏再发",
                "if_send": "四国口径被写成原产国一格，优惠原产地可能判错",
                "detail": countries,
            }
        )

    hold = len(blocks) > 0
    return {
        "id": shipment["id"],
        "title": shipment.get("title", ""),
        "demo": bool(shipment.get("demo")),
        "verdict": "hold" if hold else "send",
        "headline": "先别申报" if hold else "可以申报",
        "blocks": blocks,
        "ocr_ignored": sum(1 for item in weight_obs if item.get("label") == "ocr_error"),
    }


def score(dataset: dict) -> dict:
    threshold = dataset["threshold_gross_weight"]
    judged = [judge_shipment(item, threshold) for item in dataset["shipments"]]
    rewrite_births = []
    for shipment in dataset["shipments"]:
        for field in ("gross_weight_kg", "container_no", "seal_no"):
            birth = birth_station(shipment.get(field, []))
            if birth:
                rewrite_births.append(birth)
    birth_hit = sum(1 for station in rewrite_births if station in BIRTH_TARGETS)
    country_errors = sum(1 for item in dataset["shipments"] if country_mixed(item.get("countries", {})))
    weight_holds = sum(
        1
        for item in judged
        if any(block["kind"] == "gross_weight" for block in item["blocks"])
    )
    ratio = (birth_hit / len(rewrite_births)) if rewrite_births else 0
    return {
        "shipments": judged,
        "birth_station_ratio": round(ratio, 4),
        "birth_station_hit": birth_hit,
        "birth_station_total": len(rewrite_births),
        "country_mix_count": country_errors,
        "weight_hold_count": weight_holds,
        "threshold_note": dataset["threshold_note"],
    }
