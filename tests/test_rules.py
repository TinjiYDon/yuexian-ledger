import unittest

from yuexian.rules import birth_station, country_mixed, judge_shipment, load_dataset, score


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.by_id = {item["id"]: item for item in self.dataset["shipments"]}

    def test_hero_holds_for_weight_and_country(self):
        judged = judge_shipment(self.by_id["SH-2026-014"], 0.03)
        self.assertEqual(judged["headline"], "先别申报")
        kinds = {block["kind"] for block in judged["blocks"]}
        self.assertIn("gross_weight", kinds)
        self.assertIn("countries", kinds)
        weight = next(block for block in judged["blocks"] if block["kind"] == "gross_weight")
        self.assertEqual(weight["birth_station"], "packing")
        self.assertEqual(weight["packing_kg"], 12480)
        self.assertEqual(weight["bl_kg"], 12000)

    def test_ocr_error_does_not_create_birth(self):
        shipment = self.by_id["SH-2026-033"]
        self.assertIsNone(birth_station(shipment["gross_weight_kg"]))
        judged = judge_shipment(shipment, 0.03)
        self.assertEqual(judged["headline"], "可以申报")
        self.assertEqual(judged["ocr_ignored"], 1)

    def test_seal_mismatch_holds(self):
        judged = judge_shipment(self.by_id["SH-2026-021"], 0.03)
        self.assertEqual(judged["headline"], "先别申报")
        seal = next(block for block in judged["blocks"] if block["kind"] == "seal_no")
        self.assertEqual(seal["birth_station"], "manifest")

    def test_clean_shipment_can_send(self):
        judged = judge_shipment(self.by_id["SH-2026-052"], 0.03)
        self.assertEqual(judged["blocks"], [])

    def test_country_mix_detects_collapsed_origin(self):
        self.assertTrue(country_mixed(self.by_id["SH-2026-040"]["countries"]))
        self.assertFalse(country_mixed(self.by_id["SH-2026-052"]["countries"]))

    def test_score_matches_review_numbers(self):
        result = score(self.dataset)
        self.assertEqual(result["birth_station_hit"], 2)
        self.assertEqual(result["birth_station_total"], 3)
        self.assertEqual(result["country_mix_count"], 2)
        self.assertEqual(result["weight_hold_count"], 2)


if __name__ == "__main__":
    unittest.main()
