import json
import tempfile
import unittest
from pathlib import Path

from si.extract import (PILLARS, PROMPT_VERSION, build_prompt, clean_list, clean_record, data_facts, enforce_detection_evidence,
                        extract_one, grounding_warnings, load_existing, text_context, write_records)


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []
        self.last_model = "fake/model"

    def json(self, prompt, system=None, max_tokens=None):
        self.prompts.append((system, prompt))
        return self.reply


ROWS = [
    {"record_type": "test", "fuel": "heptane", "geometry": "droplet", "diluent": "N2+CO2", "outcome": "extinction",
     "size_mm": "2.5", "flow_cm_s": "", "fuel_phase": "liquid"},
    {"record_type": "test", "fuel": "methanol", "geometry": "droplet", "diluent": "N2", "outcome": "disruption",
     "size_mm": "3.9", "flow_cm_s": "", "fuel_phase": "liquid"},
    {"record_type": "test", "fuel": "unknown", "geometry": "sample", "diluent": "", "outcome": "",
     "size_mm": "", "flow_cm_s": "", "fuel_phase": "liquid"},
]
INVESTIGATION = {"accession": "PSI-69", "acronym": "FLEX", "n_tests": 3, "fuel_phase": ["liquid"],
                 "o2_range": [0.12, 0.34], "o2_basis": "measured", "pressure_kpa_range": [70.2, 309.3],
                 "pressure_basis": "measured", "platform": "ISS", "hardware": "CIR, MDCA"}
METADATA = {"title": "Flame Extinguishment Experiment", "objective": "Burn heptane and methanol droplets.",
            "approach": "A radiometer   measured emission.", "hypothesis": "", "researchImpacts": "Better extinguishers.",
            "publications": [{"title": "Droplet extinction in microgravity"}]}


class DataFactsTests(unittest.TestCase):
    def test_facts_skip_placeholders_and_carry_ranges(self):
        facts = data_facts(INVESTIGATION, ROWS)
        self.assertEqual(facts["fuels_in_tables"], ["heptane", "methanol"])
        self.assertEqual(facts["geometries_in_tables"], ["droplet"])
        self.assertEqual(facts["size_mm_range"], [2.5, 3.9])
        self.assertIsNone(facts["flow_cm_s_range"])
        self.assertEqual((facts["o2_range"], facts["o2_basis"]), ([0.12, 0.34], "measured"))

    def test_text_context_collapses_whitespace_and_clips(self):
        context = text_context({**METADATA, "approach": "word " * 2000})
        self.assertLessEqual(len(context["approach"]), 2010)
        self.assertTrue(context["approach"].endswith("..."))
        self.assertEqual(context["publication_titles"], ["Droplet extinction in microgravity"])

    def test_prompt_contains_text_and_facts(self):
        prompt = build_prompt(text_context(METADATA), data_facts(INVESTIGATION, ROWS))
        self.assertIn("TEXT:", prompt)
        self.assertIn("DATA FACTS:", prompt)
        self.assertIn("methanol", prompt)


class CleanRecordTests(unittest.TestCase):
    def test_list_cleaning_dedupes_and_drops_non_strings(self):
        self.assertEqual(clean_list(["Heptane", "heptane", 5, " ", "methanol"]), ["Heptane", "methanol"])
        self.assertEqual(clean_list("radiometer"), ["radiometer"])
        self.assertEqual(clean_list(None), [])

    def test_only_allowed_pillars_survive(self):
        record = clean_record({"pillars": ["Suppression", "firefighting", "prevention"]}, {})
        self.assertEqual(record["pillars"], ["prevention", "suppression"])
        self.assertTrue(set(record["pillars"]) <= set(PILLARS))

    def test_table_phase_beats_model_phase(self):
        self.assertEqual(clean_record({"fuel_phase": ["gas"]}, {"fuel_phase": ["liquid"]})["fuel_phase"], ["liquid"])
        self.assertEqual(clean_record({"fuel_phase": ["Gas", "plasma"]}, {})["fuel_phase"], ["gas"])

    def test_sample_size_comes_from_data_when_available(self):
        self.assertEqual(clean_record({"sample_size": "1-4"}, {"size_mm_range": [1.1, 4.67]})["sample_size"], "1.1 to 4.67 mm")
        self.assertEqual(clean_record({"sample_size": "null"}, {})["sample_size"], None)

    def test_garbage_reply_gives_empty_schema(self):
        record = clean_record("not a dict", {})
        self.assertEqual(record["fuels"], [])
        self.assertIsNone(record["summary"])


class GroundingTests(unittest.TestCase):
    def test_invented_fuel_and_sensor_are_flagged(self):
        record = clean_record({"fuels": ["heptane", "kerosene"], "sensors": ["radiometer", "lidar"],
                               "pillars": ["suppression"], "summary": "ok"}, {})
        warnings = grounding_warnings(record, text_context(METADATA), data_facts(INVESTIGATION, ROWS))
        self.assertEqual(warnings, ["fuels not found in source: kerosene", "sensors not found in source: lidar"])

    def test_missing_pillar_and_summary_are_flagged(self):
        warnings = grounding_warnings(clean_record({}, {}), {}, {})
        self.assertEqual(warnings, ["no fire-safety pillar assigned", "no summary"])


class DetectionGuardTests(unittest.TestCase):
    def test_detection_without_evidence_is_removed_with_warning(self):
        record = clean_record({"pillars": ["prevention", "detection"]}, {})
        warnings = enforce_detection_evidence(record, {"objective": "cool flames of propane at high oxygen"})
        self.assertEqual(record["pillars"], ["prevention"])
        self.assertEqual(len(warnings), 1)

    def test_detection_with_smoke_evidence_is_kept(self):
        record = clean_record({"pillars": ["detection"]}, {})
        self.assertEqual(enforce_detection_evidence(record, {"sub_research_area": "Smoke Distribution"}), [])
        self.assertEqual(record["pillars"], ["detection"])

    def test_soot_alone_is_not_detection_evidence(self):
        record = clean_record({"pillars": ["detection"]}, {})
        enforce_detection_evidence(record, {"objective": "soot formation in coflow flames"})
        self.assertEqual(record["pillars"], [])


class ExtractOneTests(unittest.TestCase):
    def test_end_to_end_with_fake_model(self):
        reply = {"summary": "FLEX burned droplets.", "fuels": ["heptane", "methanol"], "fuel_phase": ["liquid"],
                 "sensors": ["radiometer"], "pillars": ["suppression"], "pillar_reason": "Tests diluents."}
        llm = FakeLLM(reply)
        record = extract_one(llm, INVESTIGATION, ROWS, METADATA, "droplet extinction")
        self.assertEqual((record["accession"], record["acronym"], record["model"]), ("PSI-69", "FLEX", "fake/model"))
        self.assertEqual(record["prompt_version"], PROMPT_VERSION)
        self.assertEqual(record["warnings"], [])
        self.assertEqual(record["sample_size"], "2.5 to 3.9 mm")
        system, prompt = llm.prompts[0]
        self.assertIn("Never add knowledge", system)
        self.assertIn("droplet extinction", prompt)


class OutputFileTests(unittest.TestCase):
    def test_records_are_written_in_accession_order_and_reloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "extracted.json"
            write_records(path, {"PSI-100": {"accession": "PSI-100"}, "PSI-25": {"accession": "PSI-25"}})
            self.assertEqual([r["accession"] for r in json.loads(path.read_text(encoding="utf-8"))], ["PSI-25", "PSI-100"])
            self.assertNotIn(b"\r\n", path.read_bytes())
            self.assertEqual(set(load_existing(path)), {"PSI-25", "PSI-100"})
            self.assertEqual(load_existing(Path(tmp) / "missing.json"), {})


if __name__ == "__main__":
    unittest.main()


class ExtractionReportTests(unittest.TestCase):
    def test_compare_statuses(self):
        from si.extraction_report import compare
        self.assertEqual(compare(["prevention"], ["prevention"]), "agree")
        self.assertEqual(compare(["prevention", "detection"], ["prevention"]), "partial")
        self.assertEqual(compare(["detection"], ["suppression"]), "disagree")
        self.assertEqual(compare(["prevention"], []), "seed has no pillar")

    def test_report_lists_every_investigation_and_warning(self):
        from si.extraction_report import build_rows, render
        extracted = [{"accession": "PSI-69", "acronym": "FLEX", "pillars": ["suppression"], "warnings": []},
                     {"accession": "PSI-21", "acronym": "ACME CLD Flame", "pillars": ["prevention"], "warnings": ["no summary"]}]
        seed = {"investigations": [{"accession": "PSI-69", "pillars": ["suppression"]},
                                   {"accession": "PSI-21", "pillars": [], "role": "fundamentals"}]}
        text = render(build_rows(extracted, seed), "s2-v3", "fake/model")
        self.assertIn("| PSI-69 | FLEX | suppression | suppression | agree |", text)
        self.assertIn("none (fundamentals)", text)
        self.assertIn("no summary", text)
