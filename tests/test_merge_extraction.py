import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from pipeline import merge_extraction

ROOT = Path(__file__).resolve().parent.parent


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class MergeTests(unittest.TestCase):
    def run_merge(self, investigations, extracted, tags=None, seed=None):
        tmp = Path(tempfile.mkdtemp())
        processed, domain = tmp / "processed", tmp / "domain"
        write(processed / "investigations.json", investigations)
        write(processed / "extracted.json", extracted)
        if tags is not None:
            write(domain / "tags.json", {"investigations": tags})
        if seed is not None:
            write(domain / "seed_pillars.json", seed)
        domain.mkdir(parents=True, exist_ok=True)
        argv = ["merge_extraction.py", "--processed", str(processed), "--domain", str(domain)]
        with mock.patch("sys.argv", argv), redirect_stdout(io.StringIO()) as out:
            merge_extraction.main()
        return json.loads((processed / "investigations.json").read_text(encoding="utf-8")), out.getvalue(), processed

    def test_tags_beat_the_model_and_fields_are_copied(self):
        merged, _, _ = self.run_merge(
            [{"accession": "PSI-1", "pillars": None}],
            [{"accession": "PSI-1", "summary": "S", "variables_varied": ["o2"], "variables_fixed": [], "sensors": ["cam"],
              "pillars": ["suppression"]}],
            tags=[{"accession": "PSI-1", "pillars": ["prevention"]}],
        )
        self.assertEqual(merged[0]["pillars"], ["prevention"])
        self.assertEqual((merged[0]["summary"], merged[0]["sensors"]), ("S", ["cam"]))

    def test_a_hand_checked_platform_replaces_the_catalog_value(self):
        merged, _, _ = self.run_merge(
            [{"accession": "PSI-1", "platform": "ISS"}, {"accession": "PSI-2", "platform": "ISS"}],
            [{"accession": "PSI-1"}, {"accession": "PSI-2"}],
            tags=[{"accession": "PSI-1", "pillars": [], "platform": "Cygnus"}, {"accession": "PSI-2", "pillars": []}],
        )
        self.assertEqual([m["platform"] for m in merged], ["Cygnus", "ISS"])

    def test_model_pillars_are_the_fallback_without_tags(self):
        merged, out, _ = self.run_merge(
            [{"accession": "PSI-1"}],
            [{"accession": "PSI-1", "summary": "S", "pillars": ["detection"]}],
        )
        self.assertEqual(merged[0]["pillars"], ["detection"])
        self.assertIn("tags.json does not exist yet", out)

    def test_missing_extraction_is_reported_and_left_alone(self):
        merged, out, _ = self.run_merge([{"accession": "PSI-1", "summary": None}], [])
        self.assertIsNone(merged[0]["summary"])
        self.assertIn("no extracted.json record for PSI-1", out)

    def test_running_twice_gives_the_same_file(self):
        _, _, processed = self.run_merge([{"accession": "PSI-1"}], [{"accession": "PSI-1", "summary": "S", "pillars": []}],
                                         tags=[{"accession": "PSI-1", "pillars": []}])
        first = (processed / "investigations.json").read_text(encoding="utf-8")
        argv = ["merge_extraction.py", "--processed", str(processed), "--domain", str(processed.parent / "domain")]
        with mock.patch("sys.argv", argv), redirect_stdout(io.StringIO()):
            merge_extraction.main()
        self.assertEqual((processed / "investigations.json").read_text(encoding="utf-8"), first)


class RealDataTests(unittest.TestCase):
    def test_committed_pillars_match_the_ranking_engine(self):
        investigations = json.loads((ROOT / "data/processed/investigations.json").read_text(encoding="utf-8"))
        rankings = json.loads((ROOT / "data/processed/rankings.json").read_text(encoding="utf-8"))
        ranked = {e["accession"]: e["pillars"] for e in rankings["scenarios"]["lunar_base"]["ranking"]}
        self.assertEqual({i["accession"]: i["pillars"] for i in investigations}, ranked)

    def test_all_three_saffire_flights_are_on_cygnus(self):
        records = {i["accession"]: i for i in json.loads((ROOT / "data/processed/investigations.json").read_text(encoding="utf-8"))}
        self.assertEqual({records[a]["platform"] for a in ("PSI-98", "PSI-99", "PSI-100")}, {"Cygnus"})

    def test_every_investigation_has_a_hand_checked_tag(self):
        tags = json.loads((ROOT / "data/domain/tags.json").read_text(encoding="utf-8"))["investigations"]
        investigations = json.loads((ROOT / "data/processed/investigations.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(t["accession"] for t in tags), sorted(i["accession"] for i in investigations))
        allowed = {"prevention", "detection", "suppression"}
        self.assertEqual([t["accession"] for t in tags if not set(t["pillars"]) <= allowed], [])


if __name__ == "__main__":
    unittest.main()
