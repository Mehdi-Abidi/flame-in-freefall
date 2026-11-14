import copy
import json
import tempfile
import unittest
from pathlib import Path

from si.rank import (COMPONENT_WEIGHTS, DEFAULT_WEIGHTS, RankError, UsageError, box_distance, condition_fit, data_richness,
                     material_relevance, parse_weights, pillar_match, rank, read_csv, read_json, resolve_pillars,
                     validate_scenarios)

SCENARIOS = {
    "tolerance": {"o2_mole_fraction": 0.05, "pressure_kpa": 20.0},
    "scenarios": [
        {"id": "iss", "label": "ISS", "o2_mole_fraction": [0.2, 0.22], "pressure_kpa": [97, 105],
         "context_only": False, "source": "s", "assumptions": []},
        {"id": "lunar_base", "label": "Lunar base", "o2_mole_fraction": [0.3, 0.4], "pressure_kpa": [29.6, 70.3],
         "context_only": False, "source": "s", "assumptions": []},
    ],
}


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_names_the_command_that_creates_it(self):
        with self.assertRaises(RankError) as error:
            read_json(self.dir / "investigations.json")
        self.assertIn("python pipeline/build_investigations.py", str(error.exception))

    def test_invalid_json_reports_line_and_column(self):
        path = self.dir / "bad.json"
        path.write_text('{\n  "a": ,\n}', encoding="utf-8")
        with self.assertRaises(RankError) as error:
            read_json(path)
        self.assertIn("line 2", str(error.exception))

    def test_csv_missing_columns_is_reported(self):
        path = self.dir / "tests.csv"
        path.write_text("accession,fuel\nPSI-1,x\n", encoding="utf-8")
        with self.assertRaises(RankError) as error:
            read_csv(path, ["accession", "o2_mole_fraction"])
        self.assertIn("o2_mole_fraction", str(error.exception))
        self.assertIn("python pipeline/normalize.py", str(error.exception))

    def test_csv_reads_rows(self):
        path = self.dir / "tests.csv"
        path.write_text("accession,fuel\nPSI-1,x\n", encoding="utf-8")
        self.assertEqual(read_csv(path, ["accession"]), [{"accession": "PSI-1", "fuel": "x"}])


class ScenarioValidationTests(unittest.TestCase):
    def test_valid_document(self):
        result = validate_scenarios(SCENARIOS)
        self.assertEqual(list(result["scenarios"]), ["iss", "lunar_base"])
        self.assertEqual(result["tolerance"], {"o2": 0.05, "pressure": 20.0})

    def test_every_broken_document_is_rejected(self):
        def broken(change):
            document = copy.deepcopy(SCENARIOS)
            change(document)
            return document

        cases = {
            "empty list": broken(lambda d: d.__setitem__("scenarios", [])),
            "zero tolerance": broken(lambda d: d["tolerance"].__setitem__("pressure_kpa", 0)),
            "boolean tolerance": broken(lambda d: d["tolerance"].__setitem__("o2_mole_fraction", True)),
            "missing key": broken(lambda d: d["scenarios"][0].pop("label")),
            "duplicate id": broken(lambda d: d["scenarios"].append(copy.deepcopy(d["scenarios"][0]))),
            "reversed box": broken(lambda d: d["scenarios"][1].__setitem__("o2_mole_fraction", [0.4, 0.3])),
            "text in box": broken(lambda d: d["scenarios"][1].__setitem__("pressure_kpa", [30, "70"])),
            "three numbers": broken(lambda d: d["scenarios"][1].__setitem__("pressure_kpa", [30, 50, 70])),
            "o2 above one": broken(lambda d: d["scenarios"][1].__setitem__("o2_mole_fraction", [0.3, 1.5])),
            "negative pressure": broken(lambda d: d["scenarios"][1].__setitem__("pressure_kpa", [-5, 70])),
            "blank id": broken(lambda d: d["scenarios"][1].__setitem__("id", " ")),
            "not an object": broken(lambda d: d["scenarios"].append("lunar")),
        }
        for name, document in cases.items():
            with self.subTest(name), self.assertRaises(RankError):
                validate_scenarios(document)

    def test_repository_scenarios_file_is_valid(self):
        path = Path(__file__).resolve().parent.parent / "data" / "domain" / "scenarios.json"
        result = validate_scenarios(json.loads(path.read_text(encoding="utf-8")))
        self.assertIn("lunar_base", result["scenarios"])


class WeightTests(unittest.TestCase):
    def test_defaults_and_valid_forms(self):
        self.assertEqual(parse_weights(None), {"prevention": 1.0, "detection": 1.0, "suppression": 1.0})
        self.assertEqual(parse_weights("Prevention=2, detection=0"), {"prevention": 2.0, "detection": 0.0, "suppression": 1.0})
        self.assertEqual(parse_weights({"suppression": "3"})["suppression"], 3.0)

    def test_invalid_weights_raise_usage_errors(self):
        for bad in ["prevention", "fire=1", "prevention=abc", "prevention=-1", "prevention=nan", "prevention=inf",
                    "prevention=0,detection=0,suppression=0", 42, ["prevention"]]:
            with self.subTest(bad=bad), self.assertRaises(UsageError):
                parse_weights(bad)



def row(o2, pressure, o2_source="measured", pressure_source="measured", record_type="test"):
    return {"record_type": record_type, "o2_mole_fraction": "" if o2 is None else str(o2), "o2_source": o2_source,
            "pressure_kpa": "" if pressure is None else str(pressure), "pressure_source": pressure_source}


LUNAR = validate_scenarios(SCENARIOS)["scenarios"]["lunar_base"]
TOLERANCE = {"o2": 0.05, "pressure": 20.0}


class ComponentTests(unittest.TestCase):
    def test_box_distance(self):
        self.assertEqual(box_distance(0.35, [0.3, 0.4], 0.05), 0.0)
        self.assertAlmostEqual(box_distance(0.2, [0.3, 0.4], 0.05), 2.0)
        self.assertAlmostEqual(box_distance(90.3, [29.6, 70.3], 20.0), 1.0)

    def test_test_inside_the_box_scores_one(self):
        fit = condition_fit([row(0.35, 60)], LUNAR, TOLERANCE)
        self.assertEqual((fit["fit"], fit["n_in_target"], fit["n_near"]), (1.0, 1, 1))

    def test_far_tests_score_near_zero_and_say_so(self):
        far = condition_fit([row(0.21, 101.3)] * 5, LUNAR, TOLERANCE)
        near = condition_fit([row(0.29, 75)] * 5, LUNAR, TOLERANCE)
        self.assertAlmostEqual(far["fit"], 0.0596, places=3)
        self.assertLess(far["fit"], near["fit"])
        self.assertEqual((far["n_in_target"], far["n_near"]), (0, 0))

    def test_nominal_values_count_less_than_measured(self):
        measured = condition_fit([row(0.35, 60)], LUNAR, TOLERANCE)["fit"]
        nominal = condition_fit([row(0.35, 60, "nominal_cabin_air", "nominal_cabin")], LUNAR, TOLERANCE)
        self.assertLess(nominal["fit"], measured)
        self.assertEqual(nominal["n_in_target"], 0)

    def test_missing_pressure_is_penalised_not_ignored(self):
        fit = condition_fit([row(0.35, None, pressure_source="")], LUNAR, TOLERANCE)
        self.assertAlmostEqual(fit["fit"], 0.75)

    def test_rows_without_usable_values_are_skipped(self):
        rows = [row(None, 60), row("abc", 60), row(0.35, 60, record_type="test_day"), row(0.35, 60, o2_source="")]
        self.assertEqual(condition_fit(rows, LUNAR, TOLERANCE)["n_considered"], 0)
        self.assertEqual(condition_fit([], LUNAR, TOLERANCE)["fit"], 0.0)

    def test_material_relevance(self):
        self.assertEqual(material_relevance(["gas", "solid"]), 1.0)
        self.assertEqual(material_relevance(["liquid"]), 0.7)
        self.assertEqual(material_relevance([]), 0.0)

    def test_pillar_match_does_not_reward_extra_tags(self):
        self.assertEqual(pillar_match(["prevention"], DEFAULT_WEIGHTS), pillar_match(["prevention", "suppression"], DEFAULT_WEIGHTS))
        self.assertEqual(pillar_match(["detection"], {"prevention": 2, "detection": 1, "suppression": 0}), 0.5)
        self.assertEqual(pillar_match([], DEFAULT_WEIGHTS), 0.0)

    def test_data_richness_is_log_scaled_and_bounded(self):
        maxima = {"n_tests": 400, "n_files": 20000, "publications": 50}
        full = data_richness({"n_tests": 400, "n_files": 20000, "publications": [0] * 50}, maxima)
        empty = data_richness({"n_tests": 0, "n_files": 0, "publications": []}, maxima)
        half = data_richness({"n_tests": 20, "n_files": 141, "publications": [0] * 7}, maxima)
        self.assertEqual((full, empty), (1.0, 0.0))
        self.assertGreater(half, 0.45)

    def test_pillar_priority_tags_then_seed_then_model(self):
        tags = {"PSI-1": {"pillars": ["suppression"]}}
        seed = {"PSI-1": {"pillars": ["prevention"]}, "PSI-2": {"pillars": [], "role": "fundamentals"}}
        model = {"PSI-1": {"pillars": ["detection"]}, "PSI-2": {"pillars": ["prevention"]}, "PSI-3": {"pillars": ["detection", "fire"]}}
        self.assertEqual(resolve_pillars("PSI-1", tags, seed, model), (["suppression"], "tags"))
        self.assertEqual(resolve_pillars("PSI-2", {}, seed, model), ([], "seed"))
        self.assertEqual(resolve_pillars("PSI-3", {}, seed, model), (["detection"], "model"))
        self.assertEqual(resolve_pillars("PSI-4", {}, seed, model), ([], "none"))


def fixture_inputs():
    investigations = {
        "PSI-1": {"accession": "PSI-1", "acronym": "HIGH-O2", "fuel_phase": ["gas"], "n_tests": 10, "n_files": 100, "publications": [1], "platform": "ISS"},
        "PSI-2": {"accession": "PSI-2", "acronym": "CABIN", "fuel_phase": ["solid"], "n_tests": 10, "n_files": 100, "publications": [1], "platform": "ISS"},
        "PSI-3": {"accession": "PSI-3", "acronym": "GROUND", "fuel_phase": [], "n_tests": 0, "n_files": 1, "publications": [], "platform": "ground"},
    }
    rows = {"PSI-1": [row(0.35, 60)] * 10, "PSI-2": [row(0.21, 101.3)] * 10}
    seed = {"PSI-1": {"pillars": ["prevention"]}, "PSI-2": {"pillars": ["detection"]}, "PSI-3": {"pillars": [], "role": "fundamentals"}}
    return {"investigations": investigations, "rows": rows, "scenarios": validate_scenarios(SCENARIOS),
            "extracted": {}, "tags": {}, "seed": seed, "notes": []}


class RankTests(unittest.TestCase):
    def test_habitat_changes_the_winner(self):
        inputs = fixture_inputs()
        self.assertEqual(rank("lunar_base", None, inputs)[0]["acronym"], "HIGH-O2")
        self.assertEqual(rank("iss", None, inputs)[0]["acronym"], "CABIN")

    def test_weights_change_the_order(self):
        inputs = fixture_inputs()
        detection_first = rank("lunar_base", "prevention=0,detection=1,suppression=0", inputs)
        self.assertEqual(detection_first[0]["acronym"], "CABIN")

    def test_score_is_the_weighted_sum_and_ranks_are_sequential(self):
        results = rank("lunar_base", None, fixture_inputs())
        self.assertEqual([r["rank"] for r in results], [1, 2, 3])
        for result in results:
            expected = sum(COMPONENT_WEIGHTS[k] * v for k, v in result["components"].items())
            self.assertAlmostEqual(result["score"], expected, places=3)
        self.assertEqual(results, sorted(results, key=lambda r: -r["score"]))

    def test_reasons_explain_the_evidence(self):
        results = {r["acronym"]: r for r in rank("lunar_base", None, fixture_inputs())}
        self.assertIn("10 measured test(s) inside the Lunar base target", results["HIGH-O2"]["reasons"])
        self.assertTrue(any("none of its 10 tests" in reason for reason in results["CABIN"]["reasons"]))
        self.assertIn("ground study, no flight tests of its own", results["GROUND"]["reasons"])
        self.assertTrue(any("fundamentals only" in reason for reason in results["GROUND"]["reasons"]))

    def test_ranking_is_deterministic(self):
        inputs = fixture_inputs()
        self.assertEqual(rank("lunar_base", None, inputs), rank("lunar_base", None, inputs))

    def test_unknown_scenario_is_a_usage_error(self):
        with self.assertRaises(UsageError) as error:
            rank("moon", None, fixture_inputs())
        self.assertIn("lunar_base", str(error.exception))

if __name__ == "__main__":
    unittest.main()
