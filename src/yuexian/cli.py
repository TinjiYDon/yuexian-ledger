import argparse
import json
from pathlib import Path

from yuexian.documents import render_shipment
from yuexian.rules import load_dataset, score


def main() -> None:
    parser = argparse.ArgumentParser(description="先别申报")
    parser.add_argument("command", nargs="?", default="score", choices=["score", "docs"])
    args = parser.parse_args()
    dataset = load_dataset()
    if args.command == "docs":
        _write_docs(dataset)
        return
    print(json.dumps(score(dataset), ensure_ascii=False, indent=2))


def _write_docs(dataset: dict) -> None:
    root = Path(__file__).resolve().parents[2] / "artifacts" / "documents"
    root.mkdir(parents=True, exist_ok=True)
    for shipment in dataset["shipments"]:
        folder = root / shipment["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in render_shipment(shipment).items():
            (folder / f"{name}.txt").write_text(text, encoding="utf-8")
    print(root)
