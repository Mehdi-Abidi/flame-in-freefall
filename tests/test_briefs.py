import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from si.briefs import (PENDING_REVIEW, PILLARS, clean_brief, collect_facts, generate, group_observations, run, template_brief,
                       validate_brief, write_one)
from si.llm import LLMError

FACTS = {
    "pillar": "suppression",
    "pillar_meaning": "putting fires out",
    "dataset_facts": ["The highest measured oxygen in any solid-material test is 22.2% across 140 solid tests."],
    "investigations": [
        {"accession": "PSI-69", "name": "FLEX", "tests": 274, "fuel_phase": ["liquid"], "oxygen_percent_range": [12.0, 34.0],
         "oxygen_basis": "measured", "lunar_base_rank": 1, "observations": ["50 liquid-fuel rows with N2+He, 40 ended in extinction, the lowest at 13.0% oxygen"]},
        {"accession": "PSI-68", "name": "FLEX-2", "tests": 0, "fuel_phase": ["liquid"], "oxygen_percent_range": [17.0, 30.0],
         "oxygen_basis": "planned", "lunar_base_rank": 4, "observations": []},
        {"accession": "PSI-25", "name": "BASS-II", "tests": 129, "fuel_phase": ["solid"], "oxygen_percent_range": [13.6, 22.2],
         "oxygen_basis": "measured", "lunar_base_rank": 6, "observations": []},
        {"accession": "PSI-107", "name": "SPICE", "tests": 435, "fuel_phase": ["gas"], "oxygen_percent_range": [21.0, 21.0],
         "oxygen_basis": "nominal_cabin_air", "lunar_base_rank": 9, "observations": []},
    ],
}
GOOD = {
    "title": "What FLEX and BASS show about putting fires out",
    "findings": [
        {"text": "FLEX droplets in nitrogen and helium went out as low as 13.0% oxygen.", "citations": ["PSI-69"]},
        {"text": "FLEX-2 lists planned oxygen of 17% to 30%, not measured values.", "citations": ["PSI-68"]},
        {"text": "BASS-II burned solids with measured oxygen from 13.6% to 22.2%.", "citations": ["PSI-25"]},
    ],
    "implication": "Solid tests stop at 22.2% oxygen, below a lunar base, so extinction limits need new tests.",
    "gap": "No solid-material suppression test ran at lunar-base oxygen.",
}


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
    def test_good_brief_passes(self):
        self.assertEqual(validate_brief(clean_brief(GOOD), FACTS), [])

    def test_each_problem_is_caught(self):
        def broken(change):
            brief = json.loads(json.dumps(GOOD))
            change(brief)
            return validate_brief(clean_brief(brief), FACTS)

        cases = {
            "two findings": (lambda b: b["findings"].pop(), "needs exactly 3"),
            "no citation": (lambda b: b["findings"][0].update(citations=[]), "cites nothing"),
            "other pillar": (lambda b: b["findings"][0].update(citations=["PSI-102"]), "not in this pillar"),
            "invented number": (lambda b: b["findings"][0].update(text="FLEX went out at 7% oxygen."), "numbers not in the facts: 7"),
            "superlative": (lambda b: b["findings"][1].update(text="Helium is the most effective agent."), "superlative"),
            "spelled number": (lambda b: b.update(gap="Twenty tests are missing."), "spells out numbers"),
            "field name": (lambda b: b.update(implication="The oxygen_basis says measured."), "internal field names"),
            "long title": (lambda b: b.update(title=" ".join(["word"] * 12)), "limit is 10"),
            "empty gap": (lambda b: b.update(gap=""), "gap is empty"),
        }
        for name, (change, expected) in cases.items():
            with self.subTest(name):
                self.assertTrue(any(expected in p for p in broken(change)), broken(change))

    def test_citation_ids_are_not_treated_as_numbers(self):
        brief = json.loads(json.dumps(GOOD))
        brief["findings"][0]["text"] += " [PSI-69]"
        self.assertEqual(validate_brief(clean_brief(brief), FACTS), [])

    def test_inline_citations_are_collected(self):
        brief = clean_brief({**GOOD, "findings": [{"text": "FLEX data [PSI-69].", "citations": None}] + GOOD["findings"][1:]})
        self.assertEqual(brief["findings"][0]["citations"], ["PSI-69"])

    def test_garbage_reply_cleans_to_an_invalid_brief(self):
        self.assertTrue(validate_brief(clean_brief("not json"), FACTS))


class EvidenceGuardTests(unittest.TestCase):
    def with_finding(self, text, citations, **extra):
        brief = json.loads(json.dumps(GOOD))
        brief["findings"][0] = {"text": text, "citations": citations}
        brief.update(extra)
        return validate_brief(clean_brief(brief), FACTS)

    def test_cited_investigations_must_be_named(self):
        problems = self.with_finding("All 66 lunar tests used gas fuels.", ["PSI-69"])
        self.assertTrue(any("does not name it" in p for p in problems))

    def test_extinction_claims_need_recorded_outcomes(self):
        problems = self.with_finding("BASS-II samples showed extinction at 13.6% oxygen.", ["PSI-25"])
        self.assertTrue(any("no extinction outcome is recorded" in p for p in problems))
        self.assertEqual(self.with_finding("FLEX droplets went out at 13.0% oxygen.", ["PSI-69"]), [])

    def test_assumed_oxygen_must_be_called_assumed_near_the_number(self):
        problems = self.with_finding("SPICE measured smoke points at 21% oxygen, unlike the planned lunar base.", ["PSI-107"])
        self.assertTrue(any("assumed or planned oxygen as measured" in p for p in problems))
        self.assertEqual(self.with_finding("SPICE ran in assumed cabin air of 21% oxygen.", ["PSI-107"]), [])

    def test_absence_claims_the_facts_contradict_are_rejected(self):
        facts = json.loads(json.dumps(FACTS))
        facts["investigations"][0]["observations"] += ["101 liquid-fuel rows with N2, 58 ended in extinction, from 12.0% to 30.0% oxygen, 2 of them at 30.0% oxygen or more"]
        brief = json.loads(json.dumps(GOOD))
        brief["gap"] = "The data lack extinction results at lunar-base oxygen."
        self.assertTrue(any("extinctions at 30% oxygen or more" in p for p in validate_brief(clean_brief(brief), facts)))
        brief["gap"] = "No microgravity data exist for solid or fabric fires."
        self.assertTrue(any("solids have no data" in p for p in validate_brief(clean_brief(brief), facts)))
        brief["gap"] = "No solid-material test ran at lunar-base oxygen."
        self.assertEqual(validate_brief(clean_brief(brief), facts), [])

    def test_a_count_must_belong_to_the_diluent_it_is_given_to(self):
        facts = json.loads(json.dumps(FACTS))
        facts["investigations"][0]["observations"] = [
            "123 liquid-fuel rows with N2+CO2, measured oxygen 14.0% to 25.0%, 88 ended in extinction, from 14.0% to 24.0% oxygen",
            "101 liquid-fuel rows with N2, measured oxygen 12.0% to 34.0%, 58 ended in extinction, from 12.0% to 30.0% oxygen"]
        brief = json.loads(json.dumps(GOOD))
        brief["findings"][0] = {"text": "FLEX had 88 liquid-fuel rows with N2 that went out between 14.0% and 24.0% oxygen.", "citations": ["PSI-69"]}
        self.assertTrue(any("belongs to a different group" in p for p in validate_brief(clean_brief(brief), facts)))
        brief["findings"][0] = {"text": "FLEX had 88 liquid-fuel rows with N2+CO2 that went out between 14.0% and 24.0% oxygen.", "citations": ["PSI-69"]}
        self.assertFalse(any("belongs to a different group" in p for p in validate_brief(clean_brief(brief), facts)))

    def test_kept_model_brief_that_fails_a_newer_check_is_rewritten(self):
        bad = {**GOOD, "gap": "No microgravity data exist for solid or fabric fires."}
        output, _ = generate({"suppression": FACTS}, lambda f: (bad, "model", []), model_id="m")
        _, stats = generate({"suppression": FACTS}, lambda f: (GOOD, "model", []), existing=output, model_id="m")
        self.assertEqual(stats["model"], 1)

    def test_overconfident_safety_language_is_rejected(self):
        problems = self.with_finding(GOOD["findings"][0]["text"], ["PSI-69"],
                                     implication="Designers can rely on diluents that worked at lower oxygen.")
        self.assertTrue(any("overconfident" in p for p in problems))

    def test_effectiveness_claims_are_overconfident(self):
        problems = self.with_finding("FLEX droplets went out at 13.0% oxygen, so helium is effective.", ["PSI-69"])
        self.assertTrue(any("overconfident" in p for p in problems))

    def test_v1_safety_inversion_is_caught(self):
        problems = self.with_finding(GOOD["findings"][0]["text"], ["PSI-69"],
                                     implication="Suppression strategies can rely on diluents effective at those lower concentrations.")
        self.assertTrue(any("can rely on" in p for p in problems))


class TemplateTests(unittest.TestCase):
    def test_template_always_validates_and_labels_the_basis(self):
        brief = template_brief(FACTS)
        self.assertEqual(validate_brief(brief, FACTS), [])
        texts = {f["citations"][0]: f["text"] for f in brief["findings"]}
        self.assertIn("(assumed cabin air)", texts["PSI-107"])
        self.assertIn("(measured)", texts["PSI-69"])

    def test_real_data_templates_validate_for_every_pillar(self):
        for pillar, facts in collect_facts().items():
            with self.subTest(pillar):
                self.assertEqual(validate_brief(template_brief(facts), facts), [])

    def test_observations_give_the_highest_oxygen_and_the_lunar_count(self):
        rows = [{"record_type": "test", "fuel_phase": "gas", "diluent": "N2", "o2_source": "measured",
                 "o2_mole_fraction": value, "outcome": "self-extinguished"} for value in ("0.14", "0.39")]
        line = group_observations(rows)[0]
        self.assertTrue(line.startswith("2 gas-fuel rows with N2"))
        self.assertIn("from 14.0% to 39.0% oxygen", line)
        self.assertIn("1 of them at 30.0% oxygen or more", line)

    def test_template_says_how_many_tests_have_an_oxygen_value(self):
        facts = collect_facts()["prevention"]
        cfi_g = next(inv for inv in facts["investigations"] if inv["accession"] == "PSI-159")
        self.assertEqual((cfi_g["tests"], cfi_g["tests_with_oxygen"]), (333, 179))
        text = next(f["text"] for f in template_brief(facts)["findings"] if f["citations"] == ["PSI-159"])
        self.assertIn("333 tests with gas fuels, 179 of them with an oxygen value from 18% to 40%", text)

    def test_outcomes_read_naturally(self):
        rows = [{"record_type": "test", "fuel_phase": "liquid", "diluent": "N2", "o2_source": "measured",
                 "o2_mole_fraction": "0.2", "outcome": "burned to completion"}]
        self.assertIn("1 burned completely", group_observations(rows)[0])


class WriteOneTests(unittest.TestCase):
    def test_valid_reply_is_used(self):
        brief, source, problems = write_one(FakeLLM([GOOD]), FACTS)
        self.assertEqual((source, problems), ("model", []))
        self.assertEqual(brief["title"], GOOD["title"])

    def test_rejected_reply_is_repaired_with_feedback(self):
        bad = {**GOOD, "findings": GOOD["findings"][:2]}
        llm = FakeLLM([bad, GOOD])
        self.assertEqual(write_one(llm, FACTS)[1], "model")
        self.assertIn("rejected for these reasons", llm.prompts[1])

    def test_model_errors_are_retried_then_fall_back(self):
        self.assertEqual(write_one(FakeLLM([LLMError("HTTP 400"), GOOD]), FACTS)[1], "model")
        brief, source, problems = write_one(FakeLLM([LLMError("x")] * 3), FACTS)
        self.assertEqual(source, "template")
        self.assertEqual(validate_brief(brief, FACTS), [])


class GenerateTests(unittest.TestCase):
    def test_records_carry_members_review_status_and_are_resumable(self):
        output, stats = generate({"suppression": FACTS}, lambda f: (GOOD, "model", []), model_id="m")
        record = output["suppression"]
        self.assertEqual(record["members"], ["PSI-69", "PSI-68", "PSI-25", "PSI-107"])
        self.assertEqual(record["review"], PENDING_REVIEW)
        record["review"] = "reviewed by Taha"
        _, again = generate({"suppression": FACTS}, lambda f: (GOOD, "model", []), existing=output, model_id="m")
        self.assertEqual(again["kept"], 1)
        self.assertEqual(output["suppression"]["review"], "reviewed by Taha")

    def test_a_reviewed_brief_survives_a_model_rerun(self):
        output, _ = generate({"suppression": FACTS}, lambda f: (GOOD, "model", []), model_id="m")
        output["suppression"].update(source="reviewed", model="claude", review="reviewed by Taha")
        kept, stats = generate({"suppression": FACTS}, lambda f: (template_brief(f), "template", []), existing=output, model_id="other")
        self.assertEqual(stats["kept"], 1)
        self.assertEqual((kept["suppression"]["source"], kept["suppression"]["review"]), ("reviewed", "reviewed by Taha"))

    def test_the_committed_briefs_pass_the_current_checks(self):
        document = json.loads((Path(__file__).resolve().parent.parent / "data/processed/briefs.json").read_text(encoding="utf-8"))
        facts = collect_facts()
        for pillar, brief in document["briefs"].items():
            self.assertEqual(validate_brief(clean_brief(brief), facts[pillar]), [], pillar)

    def test_changed_facts_reset_the_review(self):
        output, _ = generate({"suppression": FACTS}, lambda f: (GOOD, "model", []), model_id="m")
        output["suppression"]["review"] = "reviewed by Taha"
        changed = {**FACTS, "dataset_facts": FACTS["dataset_facts"] + ["new fact"]}
        updated, stats = generate({"suppression": changed}, lambda f: (GOOD, "model", []), existing=output, model_id="m")
        self.assertEqual(stats["model"], 1)
        self.assertEqual(updated["suppression"]["review"], PENDING_REVIEW)


class CommandLineTests(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = run(argv)
        return code, out.getvalue(), err.getvalue()

    def test_unknown_pillar_exits_2(self):
        self.assertEqual(self.run_cli(["--pillar", "fire", "--templates-only"])[0], 2)

    def test_templates_only_writes_all_pillars_and_strict_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "b.json")
            self.assertEqual(self.run_cli(["--templates-only", "--out", out])[0], 0)
            briefs = json.loads(Path(out).read_text(encoding="utf-8"))["briefs"]
            self.assertEqual(sorted(briefs), sorted(PILLARS))
            self.assertEqual(self.run_cli(["--templates-only", "--strict", "--force", "--out", out])[0], 1)

    def test_missing_key_is_a_clear_data_error(self):
        with mock.patch("si.llm.LLM", side_effect=LLMError("LLM_API_KEY is not set")):
            code, _, err = self.run_cli(["--pillar", "suppression"])
        self.assertEqual(code, 1)
        self.assertIn("--templates-only", err)
        self.assertNotIn("..", err)

    def test_corrupt_existing_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.json"
            out.write_text('{"version": 1}', encoding="utf-8")
            code, _, err = self.run_cli(["--templates-only", "--out", str(out)])
        self.assertEqual(code, 1)
        self.assertIn("not a briefs file", err)


if __name__ == "__main__":
    unittest.main()
