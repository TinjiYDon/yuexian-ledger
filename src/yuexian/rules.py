"""申报前规则。模型不得改写这里的判定。"""

from __future__ import annotations

import json
from pathlib import Path

STATION_ORDER = ["booking", "packing", "bl", "manifest", "declaration"]
BIRTH_TARGETS = {"packing", "manifest"}


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
