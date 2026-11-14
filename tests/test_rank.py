import copy
import json
import tempfile
import unittest
from pathlib import Path

from si.rank import RankError, UsageError, parse_weights, read_csv, read_json, validate_scenarios

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


if __name__ == "__main__":
    unittest.main()
