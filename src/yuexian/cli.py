import json

from yuexian.rules import load_dataset, score


def main() -> None:
    print(json.dumps(score(load_dataset()), ensure_ascii=False, indent=2))
