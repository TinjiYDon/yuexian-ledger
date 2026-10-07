"""把金标准样例渲染成可抽取的单证文本。

版式参考报关台对单时并排看的装箱单和提单，不使用企业真实单据。
"""

from __future__ import annotations

from yuexian.rules import value_at


def render_shipment(shipment: dict) -> dict[str, str]:
    docs = {
        "packing": _doc(shipment, "packing", "PACKING_LIST"),
        "bl": _doc(shipment, "bl", "BILL_OF_LADING"),
    }
    manifest = _manifest(shipment)
    if manifest:
        docs["manifest"] = manifest
    return docs


def _doc(shipment: dict, station: str, doc_type: str) -> str:
    weight = value_at(shipment.get("gross_weight_kg", []), station)
    container = value_at(shipment.get("container_no", []), "bl")
    seal = value_at(shipment.get("seal_no", []), station if station != "packing" else "bl")
    lines = [
        f"DOC_TYPE: {doc_type}",
        f"DOC_STATION: {station}",
        f"SHIPMENT: {shipment['id']}",
        f"TITLE: {shipment.get('title', '')}",
    ]
    if weight is not None:
        lines.append(f"GROSS_WEIGHT_KG: {weight}")
    noisy = _ocr_noise(shipment.get("gross_weight_kg", []), station)
    if noisy is not None:
        lines.append(f"OCR GROSS_WEIGHT_KG: {noisy}")
    if container:
        lines.append(f"CONTAINER_NO: {container}")
    if seal:
        lines.append(f"SEAL_NO: {seal}")
    lines.extend(_country_lines(shipment))
    return "\n".join(lines) + "\n"


def _manifest(shipment: dict) -> str | None:
    seal = value_at(shipment.get("seal_no", []), "manifest")
    bl_seal = value_at(shipment.get("seal_no", []), "bl")
    container = value_at(shipment.get("container_no", []), "manifest")
    if seal is None and container is None:
        return None
    if seal == bl_seal and container == value_at(shipment.get("container_no", []), "bl"):
        return None
    lines = [
        "DOC_TYPE: MANIFEST",
        "DOC_STATION: manifest",
        f"SHIPMENT: {shipment['id']}",
    ]
    if container:
        lines.append(f"CONTAINER_NO: {container}")
    if seal:
        lines.append(f"SEAL_NO: {seal}")
    return "\n".join(lines) + "\n"


def _ocr_noise(observations: list[dict], station: str):
    hits = [
        item
        for item in observations
        if item.get("station") == station and item.get("label") == "ocr_error"
    ]
    if not hits:
        return None
    return hits[-1]["value"]


def _country_lines(shipment: dict) -> list[str]:
    countries = shipment.get("countries") or {}
    if not countries:
        return []
    collapsed = countries.get("collapsed_value")
    if collapsed:
        return [
            f"COUNTRY: {collapsed}",
            f"TRADE_COUNTRY: {countries.get('trade', '')}",
            f"ORIGIN_COUNTRY: {countries.get('origin', '')}",
        ]
    return [
        f"TRADE_COUNTRY: {countries.get('trade', '')}",
        f"DEPARTURE_COUNTRY: {countries.get('departure', '')}",
        f"ORIGIN_COUNTRY: {countries.get('origin', '')}",
        f"DESTINATION_COUNTRY: {countries.get('destination', '')}",
    ]
