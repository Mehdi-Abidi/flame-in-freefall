"""API tests (tasks A1 to A5). They need fastapi, httpx and rank-bm25, and skip when those are missing.
No API key needed: the LLM is replaced by a fake.

    python -m unittest tests.test_api -v
"""

import importlib.util
import unittest
from unittest import mock

HAVE_DEPS = all(importlib.util.find_spec(name) for name in ("fastapi", "httpx", "rank_bm25"))

if HAVE_DEPS:
    from fastapi.testclient import TestClient

    from api import ask as ask_module
    from api import main
    from api.data import PROCESSED

    client = TestClient(main.app)


def fake_chat(reply):
    return lambda system, prompt: reply


@unittest.skipUnless(HAVE_DEPS, "fastapi, httpx or rank-bm25 not installed")
class InvestigationTests(unittest.TestCase):
    def test_root_redirects_to_docs(self):
        response = client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/docs")

    def test_health(self):
        body = client.get("/health").json()
        self.assertEqual(body["investigations"], 24)
        self.assertGreater(body["tests"], 2000)

    def test_list_and_detail(self):
        self.assertEqual(len(client.get("/investigations").json()), 24)
        self.assertEqual(client.get("/investigations/psi-69").json()["acronym"], "FLEX")
        self.assertEqual(client.get("/investigations/PSI-999").status_code, 404)


@unittest.skipUnless(HAVE_DEPS, "fastapi, httpx or rank-bm25 not installed")
class TestFilters(unittest.TestCase):
    def test_lunar_box_has_no_solid_tests(self):
        rows = client.get("/tests", params={"o2_min": 0.30, "p_max": 70.3}).json()
        self.assertTrue(rows)
        self.assertTrue(all(row["o2_mole_fraction"] >= 0.30 and row["pressure_kpa"] <= 70.3 for row in rows))
        self.assertNotIn("solid", {row["fuel_phase"] for row in rows})

    def test_measured_only(self):
        rows = client.get("/tests", params={"measured_only": True}).json()
        self.assertTrue(rows)
        self.assertTrue(all(row["o2_source"] == "measured" for row in rows))

    def test_accession_list_and_unknown(self):
        rows = client.get("/tests", params={"accession": "PSI-69,psi-68"}).json()
        self.assertEqual({row["accession"] for row in rows}, {"PSI-69", "PSI-68"})
        self.assertEqual(client.get("/tests", params={"accession": "PSI-999"}).status_code, 404)

    def test_bad_bound_rejected(self):
        self.assertEqual(client.get("/tests", params={"o2_min": 21}).status_code, 422)


@unittest.skipUnless(HAVE_DEPS, "fastapi, httpx or rank-bm25 not installed")
class ExportTests(unittest.TestCase):
    def test_full_export_matches_tests_csv(self):
        response = client.get("/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        expected = (PROCESSED / "tests.csv").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(response.text, expected)

    def test_filtered_export(self):
        response = client.get("/export", params={"accession": "PSI-69"})
        self.assertIn("PSI-69", response.headers["content-disposition"])
        lines = response.text.strip().split("\n")
        self.assertTrue(all(",PSI-69," in line for line in lines[1:]))


@unittest.skipUnless(HAVE_DEPS, "fastapi, httpx or rank-bm25 not installed")
class RankAndCompareTests(unittest.TestCase):
    def test_rank_shape_and_order(self):
        body = client.get("/rank", params={"scenario": "lunar_base"}).json()
        results = body["results"]
        self.assertEqual(body["scenario"]["id"], "lunar_base")
        self.assertEqual(len(results), 24)
        self.assertEqual([r["rank"] for r in results], list(range(1, 25)))
        self.assertEqual(results, sorted(results, key=lambda r: -r["score"]))
        self.assertEqual(set(results[0]["components"]), {"condition_fit", "material_relevance", "pillar_match", "data_richness"})
        self.assertTrue(results[0]["reasons"])

    def test_matches_si_rank(self):
        from si import rank as si_rank
        expected = si_rank.rank("iss", {"detection": 2}, si_rank.load_inputs())
        body = client.get("/rank", params={"scenario": "iss", "w_detect": 2}).json()
        self.assertEqual(body["results"], expected)

    def test_weights_change_ranking(self):
        detect = client.get("/rank", params={"w_prevent": 0, "w_detect": 1, "w_suppress": 0}).json()["results"]
        suppress = client.get("/rank", params={"w_prevent": 0, "w_detect": 0, "w_suppress": 1}).json()["results"]
        self.assertNotEqual([r["accession"] for r in detect], [r["accession"] for r in suppress])

    def test_limit(self):
        self.assertEqual(len(client.get("/rank", params={"limit": 5}).json()["results"]), 5)

    def test_usage_errors_are_400(self):
        self.assertEqual(client.get("/rank", params={"scenario": "venus"}).status_code, 400)
        self.assertEqual(client.get("/rank", params={"w_prevent": -1}).status_code, 400)
        zero = client.get("/rank", params={"w_prevent": 0, "w_detect": 0, "w_suppress": 0})
        self.assertEqual(zero.status_code, 400)
        self.assertIn("above zero", zero.json()["detail"])

    def test_data_errors_are_500(self):
        with mock.patch.object(main.si_rank, "rank", side_effect=main.si_rank.RankError("broken file")):
            response = client.get("/rank")
        self.assertEqual(response.status_code, 500)
        self.assertIn("broken file", response.json()["detail"])

    def test_scenarios(self):
        body = client.get("/scenarios").json()
        ids = [s["id"] for s in body["scenarios"]]
        self.assertEqual(ids, ["iss", "lunar_base", "pressurized_rover", "mars_habitat", "spacesuit"])
        self.assertIn("o2", body["tolerance"])

    def test_compare(self):
        body = client.get("/compare", params={"ids": "PSI-69,PSI-68"}).json()
        self.assertEqual(body["ids"], ["PSI-69", "PSI-68"])
        rows = {row["field"]: row for row in body["rows"]}
        self.assertTrue(rows["acronym"]["differs"])
        self.assertFalse(rows["platform"]["differs"])

    def test_compare_needs_two_to_four(self):
        self.assertEqual(client.get("/compare", params={"ids": "PSI-69"}).status_code, 422)
        self.assertEqual(client.get("/compare", params={"ids": "PSI-69,PSI-69"}).status_code, 422)
        self.assertEqual(client.get("/compare", params={"ids": "PSI-69,PSI-999"}).status_code, 404)


@unittest.skipUnless(HAVE_DEPS, "fastapi, httpx or rank-bm25 not installed")
class AskTests(unittest.TestCase):
    QUESTION = "Which diluent put out droplet flames at lower oxygen, CO2 or helium?"

    def test_retrieval_finds_flex(self):
        accessions = {s["accession"] for s in main.retriever.search(self.QUESTION)}
        self.assertTrue(accessions & {"PSI-69", "PSI-68"})

    def test_cited_answer(self):
        with mock.patch.object(main, "llm_chat", return_value=fake_chat("Helium did, at lower oxygen [PSI-69].")):
            body = client.post("/ask", json={"question": self.QUESTION}).json()
        self.assertTrue(body["covered"])
        self.assertEqual(body["citations"], ["PSI-69"])
        self.assertTrue(body["sources"])

    def test_model_says_not_covered(self):
        with mock.patch.object(main, "llm_chat", return_value=fake_chat(ask_module.NOT_COVERED)):
            body = client.post("/ask", json={"question": "What did FLEX find about ethanol droplets?"}).json()
        self.assertFalse(body["covered"])
        self.assertEqual(body["answer"], ask_module.NOT_COVERED)

    def test_uncited_or_invented_citation_is_not_covered(self):
        with mock.patch.object(main, "llm_chat", return_value=fake_chat("Helium works best [PSI-999].")):
            body = client.post("/ask", json={"question": self.QUESTION}).json()
        self.assertFalse(body["covered"])
        self.assertEqual(body["citations"], [])

    def test_uncited_answer_gets_one_retry(self):
        replies = iter(["Helium did, at lower oxygen.", "Helium did, at lower oxygen [PSI-69]."])
        with mock.patch.object(main, "llm_chat", return_value=lambda system, prompt: next(replies)):
            body = client.post("/ask", json={"question": self.QUESTION}).json()
        self.assertTrue(body["covered"])
        self.assertEqual(body["citations"], ["PSI-69"])

    def test_no_matching_text_skips_llm(self):
        with mock.patch.object(main, "llm_chat", return_value=None):
            body = client.post("/ask", json={"question": "zzqx qqzz"}).json()
        self.assertEqual(body["answer"], ask_module.NOT_COVERED)

    def test_no_key_returns_503(self):
        with mock.patch.object(main, "llm_chat", return_value=None):
            response = client.post("/ask", json={"question": self.QUESTION})
        self.assertEqual(response.status_code, 503)

    def test_non_breaking_hyphen_citation_counts(self):
        with mock.patch.object(main, "llm_chat", return_value=fake_chat("Helium did [PSI‑69].")):
            body = client.post("/ask", json={"question": self.QUESTION}).json()
        self.assertTrue(body["covered"])
        self.assertEqual(body["citations"], ["PSI-69"])
        self.assertIn("[PSI-69]", body["answer"])

    def test_sources_are_labelled_by_accession(self):
        prompt = ask_module.build_prompt("q", main.retriever.search(self.QUESTION))
        self.assertIn("[PSI-69]", prompt)
        self.assertNotIn("[1]", prompt)

    def test_test_table_passage_names_helium(self):
        sources = main.retriever.search(self.QUESTION)
        table = [s for s in sources if s["accession"] == "PSI-69" and s["field"] == "test table"]
        self.assertTrue(table)
        self.assertIn("helium", table[0]["text"])
        self.assertIn("extinction", table[0]["text"])

    def test_gravity_passage_found(self):
        sources = main.retriever.search("cotton-fiberglass flame spread microgravity versus normal gravity")
        self.assertIn(("PSI-99", "gravity comparison"), [(s["accession"], s["field"]) for s in sources])

    def test_overview_states_the_pitch_numbers(self):
        overview = next(c["text"] for c in main.retriever.chunks if c["field"] == "dataset overview")
        self.assertIn("Highest measured oxygen for a solid fuel: 22.2% O2, in BASS-II (PSI-25), burning Nomex, PMMA.", overview)
        self.assertIn("0 solid-fuel rows have measured O2 of 30% or more.", overview)
        self.assertIn("BASS (PSI-26) ran in cabin air", overview)
        self.assertIn("FLEX-2 (PSI-68) lists planned O2 levels only", overview)
        self.assertIn("ACME BRE (PSI-20) lists O2 per test day", overview)
        self.assertNotIn("FLEX-2 (PSI-68) ran in cabin air", overview)

    def test_citing_an_accession_named_inside_the_overview_counts(self):
        with mock.patch.object(main, "llm_chat", return_value=fake_chat("No, solids stopped at 22.2% [PSI-98].")):
            body = client.post("/ask", json={"question": "Were any solid materials tested at 30% oxygen?"}).json()
        self.assertTrue(body["covered"])
        self.assertEqual(body["citations"], ["PSI-98"])

    def test_overview_label_citation_becomes_solid_accessions(self):
        reply = "No solid-fuel experiments were run at 30% oxygen or higher [OVERVIEW]."
        with mock.patch.object(main, "llm_chat", return_value=fake_chat(reply)):
            body = client.post("/ask", json={"question": "Were any solid materials tested at 30% oxygen?"}).json()
        self.assertTrue(body["covered"])
        self.assertNotIn("OVERVIEW", body["answer"])
        self.assertIn("PSI-25", body["citations"])
        self.assertNotIn("PSI-69", body["citations"])

    def test_question_validation(self):
        self.assertEqual(client.post("/ask", json={"question": "x" * 501}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
