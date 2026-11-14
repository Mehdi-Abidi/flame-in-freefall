import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from si.llm import LLMError
from si.rationale import (RationaleError, build_facts, conditions_on_record, field_medians, fingerprint, generate, group_scenarios,
                          is_reusable, load_rankings, run, sanitize, standout_parts, template_rationale, validate, write_one)
from si.rank import UsageError


def entry(accession="PSI-69", rank=1, score=0.78, n_in_target=0, n_near=23, reasons=None):
    return {
        "accession": accession, "acronym": "FLEX", "title": "Flame Extinguishment Experiment", "rank": rank, "score": score,
        "components": {"condition_fit": 0.58, "material_relevance": 0.7, "pillar_match": 1.0, "data_richness": 0.94},
        "pillars": ["suppression"],
        "evidence": {"n_considered": 274, "n_in_target": n_in_target, "n_near": n_near,
                     "best": {"o2_mole_fraction": 0.34, "pressure_kpa": 71.0, "closeness": 0.99}},
        "reasons": reasons or ["closest test: 34% O2 at 71 kPa", "burned liquid fuels"],
    }


SCENARIO = {"label": "Lunar base", "o2_mole_fraction": [0.3, 0.4], "pressure_kpa": [29.6, 70.3]}
FACTS = build_facts(entry(), SCENARIO, 24, {"summary": "Droplets of 1.1 to 4.7 mm."})
GOOD = "FLEX ranks first for the lunar base because its closest test reached 34% oxygen at 71 kPa. Its tests burned liquid droplets, not solid cabin materials."


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def json(self, prompt, system=None, max_tokens=None):
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class ValidationTests(unittest.TestCase):
    def test_good_rationale_passes(self):
        self.assertEqual(validate(GOOD, FACTS), [])

    def test_sanitize_removes_dashes_and_semicolons(self):
        self.assertEqual(sanitize("A — b; c – d - e."), "A, b, c, d, e.")
        self.assertEqual(sanitize("well-known"), "well-known")

    def test_each_problem_is_caught(self):
        cases = {
            "invented number": ("FLEX ranks first with 41 tests at 45% oxygen. It burned liquids.", "numbers not in the facts"),
            "false inside claim": ("FLEX ranks first on suppression. Its tests sat inside the target box.", "inside the target"),
            "wrong rank": ("FLEX ranks 3rd thanks to suppression data. It burned liquids only.", "states rank 3"),
            "one sentence": ("FLEX is first.", "needs exactly 2"),
            "too long": (" ".join(["word"] * 40) + ". " + " ".join(["word"] * 40) + ".", "limit is 70"),
            "empty": ("", "empty"),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(name):
                self.assertTrue(any(expected in p for p in validate(text, FACTS)), validate(text, FACTS))

    def test_negated_inside_statement_is_allowed(self):
        self.assertEqual(validate("FLEX ranks first on suppression. None of its tests were inside the target box.", FACTS), [])

    def test_inside_claim_allowed_when_tests_were_inside(self):
        facts = build_facts(entry(n_in_target=5), SCENARIO, 24, {})
        self.assertEqual(validate("FLEX ranks first on suppression. Its tests sat inside the target box.", facts), [])

    def test_numbers_from_facts_and_their_percent_forms_are_allowed(self):
        self.assertEqual(validate("FLEX scores 78 with a condition fit of 0.58. Its fit is 58 percent of the maximum.", FACTS), [])


class PlainLanguageTests(unittest.TestCase):
    def test_spelled_out_numbers_are_rejected(self):
        problems = validate("FLEX ranks first of twenty-four on oxygen and pressure fit. None of its tests were inside the target.", FACTS)
        self.assertTrue(any("spells out numbers" in p for p in problems))

    def test_internal_field_names_are_rejected(self):
        problems = validate("FLEX ranks first because its pillar_match is perfect. None of its tests were inside the target.", FACTS)
        self.assertTrue(any("internal field names (pillar_match)" in p for p in problems))

    def test_the_investigation_must_be_named(self):
        problems = validate("It ranks first on oxygen and pressure fit. None of its tests were inside the target.", FACTS)
        self.assertTrue(any("does not name the investigation" in p for p in problems))

    def test_odd_hyphens_are_normalized(self):
        self.assertEqual(sanitize("fire‑safety"), "fire-safety")

    def test_standout_and_weakness_are_relative_to_the_field(self):
        medians = {"condition_fit": 0.1, "material_relevance": 0.7, "pillar_match": 1.0, "data_richness": 0.5}
        strongest, weakest = standout_parts({"condition_fit": 0.58, "material_relevance": 0.7, "pillar_match": 1.0, "data_richness": 0.94}, medians)
        self.assertEqual((strongest, weakest), ("oxygen and pressure fit", None))
        strongest, weakest = standout_parts({"condition_fit": 0.0, "material_relevance": 0.7, "pillar_match": 1.0, "data_richness": 0.5}, medians)
        self.assertEqual((strongest, weakest), (None, "oxygen and pressure fit"))

    def test_field_medians(self):
        ranking = [{"components": {"condition_fit": v, "material_relevance": 0, "pillar_match": 0, "data_richness": 0}} for v in (0.1, 0.5, 0.9, 0.3)]
        self.assertAlmostEqual(field_medians(ranking)["condition_fit"], 0.4)

    def test_conditions_on_record_says_assumed_not_missing(self):
        self.assertEqual(conditions_on_record({"o2_basis": "nominal_cabin_air", "pressure_basis": "nominal_cabin"}),
                         "oxygen assumed ISS cabin air, not logged, pressure assumed ISS cabin pressure, not logged")
        self.assertEqual(conditions_on_record({"o2_basis": None, "pressure_basis": None}), "no oxygen or pressure recorded")
        self.assertEqual(conditions_on_record({"o2_basis": "measured", "pressure_basis": "measured"}), "oxygen and pressure both measured")
        self.assertEqual(conditions_on_record(None), "not known")


class TemplateTests(unittest.TestCase):
    def test_templates_always_validate(self):
        for kwargs in ({}, {"n_in_target": 29}, {"n_in_target": 0, "n_near": 0}, {"reasons": ["no O2 or pressure data to compare with this habitat"]}):
            with self.subTest(kwargs):
                facts = build_facts(entry(**kwargs), SCENARIO, 24, {})
                self.assertEqual(validate(template_rationale(facts), facts), [], template_rationale(facts))

    def test_inside_template_names_the_material_limitation(self):
        facts = build_facts(entry(n_in_target=29, reasons=["29 measured test(s) inside the Lunar base target", "burned gas fuels"]), SCENARIO, 24, {})
        self.assertIn("do not show how solid cabin materials behave", template_rationale(facts))

    def test_every_real_template_validates(self):
        rankings = load_rankings()
        for scenario in rankings.values():
            for e in scenario["ranking"]:
                facts = build_facts(e, scenario, len(scenario["ranking"]), {})
                self.assertEqual(validate(template_rationale(facts), facts), [], e["accession"])


class WriteOneTests(unittest.TestCase):
    def test_valid_first_reply_is_used(self):
        self.assertEqual(write_one(FakeLLM([{"rationale": GOOD}]), FACTS), (GOOD, "model", []))

    def test_rejected_reply_is_repaired_with_feedback(self):
        llm = FakeLLM([{"rationale": "FLEX ranks first with 41 tests. Short."}, {"rationale": GOOD}])
        text, source, problems = write_one(llm, FACTS)
        self.assertEqual((text, source, problems), (GOOD, "model", []))
        self.assertIn("rejected for these reasons", llm.prompts[1])
        self.assertIn("41", llm.prompts[1])

    def test_bad_replies_fall_back_to_template(self):
        text, source, problems = write_one(FakeLLM([{"rationale": "Bad."}, {"wrong_key": 1}, {"rationale": "Still bad."}]), FACTS)
        self.assertEqual(source, "template")
        self.assertEqual(validate(text, FACTS), [])
        self.assertTrue(problems)

    def test_model_error_is_retried_before_falling_back(self):
        llm = FakeLLM([LLMError("HTTP 400 Failed to generate JSON"), {"rationale": GOOD}])
        self.assertEqual(write_one(llm, FACTS), (GOOD, "model", []))
        self.assertEqual(len(llm.prompts), 2)

    def test_repeated_model_errors_fall_back_without_crashing(self):
        llm = FakeLLM([LLMError("HTTP 400"), LLMError("HTTP 400"), LLMError("HTTP 400")])
        text, source, problems = write_one(llm, FACTS)
        self.assertEqual(source, "template")
        self.assertIn("model error", problems[0])
        self.assertEqual(validate(text, FACTS), [])

    def test_attempts_are_capped(self):
        llm = FakeLLM([{"rationale": "Bad."}] * 3)
        self.assertEqual(write_one(llm, FACTS)[1], "template")
        self.assertEqual(len(llm.prompts), 3)


class GenerateTests(unittest.TestCase):
    def rankings(self):
        def scenario(label, box):
            return {"label": label, "o2_mole_fraction": box, "pressure_kpa": [29.6, 70.3],
                    "ranking": [entry("PSI-69", 1), entry("PSI-68", 2, 0.6)]}
        return {"iss": scenario("ISS", [0.2, 0.22]), "lunar_base": scenario("Lunar base", [0.3, 0.4]),
                "pressurized_rover": scenario("Pressurized rover", [0.3, 0.4])}

    def test_grouping_writes_shared_box_once(self):
        self.assertEqual(group_scenarios(self.rankings()), [["iss"], ["lunar_base", "pressurized_rover"]])
        calls = []
        output, stats = generate(self.rankings(), {}, lambda f: (calls.append(f) or ("T. U.", "template", [])))
        self.assertEqual(len(calls), 4)
        self.assertEqual(stats, {"model": 0, "template": 4, "kept": 0})
        self.assertEqual(output["pressurized_rover"]["PSI-69"]["text"], output["lunar_base"]["PSI-69"]["text"])

    def test_unchanged_facts_are_kept_and_force_rewrites(self):
        first, _ = generate(self.rankings(), {}, lambda f: ("A. B.", "model", []), model_id="m")
        _, stats = generate(self.rankings(), {}, lambda f: ("C. D.", "model", []), existing=first, model_id="m")
        self.assertEqual(stats["kept"], 4)
        _, forced = generate(self.rankings(), {}, lambda f: ("C. D.", "model", []), existing=first, model_id="m", force=True)
        self.assertEqual(forced["model"], 4)

    def test_templates_are_upgraded_when_a_model_is_available(self):
        self.assertFalse(is_reusable({"fingerprint": "x", "source": "template"}, "x", "openai/gpt-oss-120b", False))
        self.assertTrue(is_reusable({"fingerprint": "x", "source": "template"}, "x", "template", False))
        self.assertFalse(is_reusable({"fingerprint": "old", "source": "model"}, "x", "m", False))

    def test_filters_limit_the_work(self):
        calls = []
        generate(self.rankings(), {}, lambda f: (calls.append(f) or ("A. B.", "model", [])), scenario_filter="iss", only=["psi-68"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(fingerprint({"a": 1}), fingerprint({"a": 1}))


class CommandLineTests(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = run(argv)
        return code, out.getvalue(), err.getvalue()

    def test_usage_errors_exit_2(self):
        self.assertEqual(self.run_cli(["--scenario", "moon", "--templates-only"])[0], 2)
        self.assertEqual(self.run_cli(["--only", "PSI-999", "--templates-only"])[0], 2)

    def test_templates_only_writes_every_habitat_and_strict_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "r.json")
            self.assertEqual(self.run_cli(["--templates-only", "--out", out])[0], 0)
            rationales = json.loads(Path(out).read_text(encoding="utf-8"))["rationales"]
            self.assertTrue(all(len(v) == 24 for v in rationales.values()))
            self.assertEqual(self.run_cli(["--templates-only", "--strict", "--force", "--out", out])[0], 1)

    def test_missing_key_gives_a_clear_data_error(self):
        with mock.patch("si.llm.LLM", side_effect=LLMError("LLM_API_KEY is not set")):
            code, _, err = self.run_cli(["--only", "PSI-69"])
        self.assertEqual(code, 1)
        self.assertIn("--templates-only", err)
        self.assertNotIn("Traceback", err)

    def test_corrupt_existing_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.json"
            out.write_text('{"version": 1}', encoding="utf-8")
            code, _, err = self.run_cli(["--templates-only", "--out", str(out)])
        self.assertEqual(code, 1)
        self.assertIn("not a rationale file", err)

    def test_errors_are_rank_errors(self):
        self.assertTrue(issubclass(RationaleError, Exception))
        self.assertTrue(issubclass(UsageError, Exception))


if __name__ == "__main__":
    unittest.main()
