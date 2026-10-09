import unittest

from yuexian.extract import extract_document
from yuexian.pipeline import run_dataset, run_shipment
from yuexian.rules import judge_shipment, load_dataset


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()

    def test_document_extract_reads_weight(self):
        text = "单证站点：packing\n票号：X\n毛重（公斤）：12480\n扫描毛重（公斤）：99999\n"
        parsed = extract_document(text)
        labels = [item["label"] for item in parsed["observations"]["gross_weight_kg"]]
        self.assertEqual(labels, ["rewrite", "ocr_error"])

    def test_pipeline_verdict_matches_gold(self):
        threshold = self.dataset["threshold_gross_weight"]
        for shipment in self.dataset["shipments"]:
            gold = judge_shipment(shipment, threshold)
            ran = run_shipment(shipment, threshold)
            self.assertEqual(ran["judgement"]["verdict"], gold["verdict"], shipment["id"])
            self.assertEqual(ran["judgement"]["headline"], gold["headline"], shipment["id"])
            stages = [step["stage"] for step in ran["trace"]]
            self.assertEqual(stages, ["ingest", "extract", "structure", "decide", "explain"])

    def test_hero_explanation_keeps_hold(self):
        hero = next(item for item in self.dataset["shipments"] if item["demo"])
        ran = run_shipment(hero, 0.03)
        self.assertIn("先别申报", ran["explanation"])
        self.assertIn("装箱单", ran["documents"]["packing"])
        self.assertIn("12480", ran["documents"]["packing"])
        self.assertIn("12000", ran["documents"]["bl"])

    def test_dataset_run_covers_every_shipment(self):
        ran = run_dataset(self.dataset)
        self.assertEqual(len(ran), len(self.dataset["shipments"]))


if __name__ == "__main__":
    unittest.main()
