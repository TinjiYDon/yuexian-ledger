import unittest
from pathlib import Path

from yuexian.cli import _write_docs
from yuexian.rules import load_dataset


class DocumentExportTests(unittest.TestCase):
    def test_hero_docs_are_written(self):
        dataset = load_dataset()
        _write_docs(dataset)
        root = Path(__file__).resolve().parents[1] / "artifacts" / "documents" / "SH-2026-014"
        packing = (root / "packing.txt").read_text(encoding="utf-8")
        bl = (root / "bl.txt").read_text(encoding="utf-8")
        self.assertIn("GROSS_WEIGHT_KG: 12480", packing)
        self.assertIn("GROSS_WEIGHT_KG: 12000", bl)


if __name__ == "__main__":
    unittest.main()
