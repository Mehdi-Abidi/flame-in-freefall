"""API tests (tasks A1 to A5). They need fastapi, httpx and rank-bm25, and skip when those are missing.
No API key needed: the LLM is replaced by a fake.

    python -m unittest tests.test_api -v
"""

import importlib.util
import re
import unittest
from unittest import mock

HAVE_DEPS = all(importlib.util.find_spec(name) for name in ("fastapi", "httpx", "rank_bm25"))

if HAVE_DEPS:
    from fastapi.testclient import TestClient

    from api import ask as ask_module
    from api import main
    from api.data import PROCESSED
    from api.limits import RateLimiter, visitor_key

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

    def setUp(self):
        self.original_limiter = main.ask_limiter
        main.ask_limiter = RateLimiter(1000, 1000, 1000, 1000)

    def tearDown(self):
        main.ask_limiter = self.original_limiter

    def test_prompt_forbids_unsupported_effectiveness_claims(self):
        self.assertIn("Do not judge which option is better", ask_module.SYSTEM_PROMPT)
        self.assertIn("does not rank the options", ask_module.SYSTEM_PROMPT)

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
        with mock.patch.object(main, "llm_chat", return_value=fake_chat("Helium did [PSI\u201169].")):
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

    def test_overview_citation_keeps_only_the_investigations_the_answer_names(self):
        reply = "BASS-II tested solid fuels from 13.6% to 22.2% oxygen [OVERVIEW]."
        with mock.patch.object(main, "llm_chat", return_value=fake_chat(reply)):
            body = client.post("/ask", json={"question": "What oxygen levels did BASS-II test with solid fuels?"}).json()
        self.assertEqual(body["citations"], ["PSI-25"])
        self.assertIn("[PSI-25]", body["answer"])

    def test_bass_is_not_matched_inside_bass_ii(self):
        self.assertFalse(ask_module._mentions("BASS-II burned PMMA", "BASS"))
        self.assertTrue(ask_module._mentions("BASS and BASS-II", "BASS"))

    def test_prompt_treats_a_zero_count_as_an_answer(self):
        self.assertIn("A count of zero in a source is an answer", ask_module.SYSTEM_PROMPT)

    def test_oxygen_guard_covers_single_level_investigations_only(self):
        single = {accession for accession, fact in main.oxygen_levels.items() if fact[3]}
        self.assertTrue({"PSI-26", "PSI-107", "PSI-99"} <= single)
        self.assertFalse({"PSI-25", "PSI-69"} & single)

    def test_a_range_borrowed_from_another_investigation_is_flagged(self):
        text = "SAFFIRE-II ran tests with ambient oxygen ranging from 14% to 22% O2 [PSI-99]."
        problems = ask_module.oxygen_problems(text, main.oxygen_levels)
        self.assertEqual(len(problems), 1)
        self.assertIn("PSI-99 SAFFIRE-II ran from 21.5% to 22.1% oxygen, not 14% to 22%", problems[0])

    def test_a_true_range_is_not_flagged(self):
        text = "BASS-II measured oxygen from 14% to 22% O2 [PSI-25]. FLEX droplets went out at 13%\u201324% O2 [PSI-69]."
        self.assertEqual(ask_module.oxygen_problems(text, main.oxygen_levels), [])

    def test_a_habitat_comparison_is_not_read_as_a_test_range(self):
        text = "BASS-II never reached the lunar band of 30% to 40% oxygen [PSI-25]."
        self.assertEqual(ask_module.oxygen_problems(text, main.oxygen_levels), [])

    def test_overview_lists_every_investigation_that_varied_oxygen_or_pressure(self):
        overview = next(c["text"] for c in main.retriever.chunks if c["field"] == "dataset overview")
        lines = {line.split(":")[0]: line for line in overview.split("\n")}
        varied = [i["accession"] for i in main.store.investigations if "oxygen concentration" in (i.get("variables_varied") or [])]
        self.assertEqual(sorted(re.findall(r"PSI-[0-9]+", lines["Varied-oxygen"])), sorted(varied))
        self.assertNotIn("PSI-99", lines["Varied-oxygen"])
        self.assertIn("SAFFIRE-II (PSI-99) about 22% O2 (measured)", lines["Single-oxygen"])
        self.assertIn("FLEX (PSI-69) 70 to 309 kPa", lines["Varied-pressure"])

    def test_variation_lines_do_not_widen_overview_citations(self):
        reply = "No solid-fuel experiments were run at 30% oxygen or higher [OVERVIEW]."
        with mock.patch.object(main, "llm_chat", return_value=fake_chat(reply)):
            body = client.post("/ask", json={"question": "Were any solid materials tested at 30% oxygen?"}).json()
        self.assertNotIn("PSI-69", body["citations"])
        self.assertNotIn("PSI-10", body["citations"])

    def test_overview_gives_each_investigation_its_own_range(self):
        overview = next(c["text"] for c in main.retriever.chunks if c["field"] == "dataset overview")
        self.assertIn("140 have measured oxygen: BASS-II (PSI-25) 14% to 22% O2; SAFFIRE-I (PSI-98) 22% O2; SAFFIRE-II (PSI-99) 22% O2.", overview)

    def test_merged_bass_claim_is_flagged_for_bass_only(self):
        text = "This is consistent with BASS and BASS-II, which examined solid fuels with varied oxygen concentrations [PSI-26, PSI-25]."
        problems = ask_module.oxygen_problems(text, main.oxygen_levels)
        self.assertEqual([p.split(" ")[0] for p in problems], ["PSI-26"])

    def test_correct_contrast_is_not_flagged(self):
        text = "BASS-II varied oxygen from 14% to 22%, while BASS ran in cabin air [PSI-25, PSI-26]."
        self.assertEqual(ask_module.oxygen_problems(text, main.oxygen_levels), [])

    def test_names_match_whatever_hyphen_the_model_writes(self):
        text = "SAFFIRE\u2011II varied oxygen concentration [PSI-99]."
        self.assertEqual([p.split(" ")[0] for p in ask_module.oxygen_problems(text, main.oxygen_levels)], ["PSI-99"])
        self.assertFalse(ask_module._mentions("BASS\u2011II burned PMMA", "BASS"))

    def test_other_variables_held_constant_do_not_excuse_the_claim(self):
        text = "SAFFIRE-II varied oxygen concentration while keeping flow velocity and diluent constant [PSI-99]."
        self.assertEqual([p.split(" ")[0] for p in ask_module.oxygen_problems(text, main.oxygen_levels)], ["PSI-99"])

    def test_a_true_narrow_range_is_not_flagged(self):
        text = "SAFFIRE-II measured oxygen ranging from 21.5% to 22.1% [PSI-99]."
        self.assertEqual(ask_module.oxygen_problems(text, main.oxygen_levels), [])

    def test_oxygen_held_constant_is_a_true_contrast(self):
        text = "SAFFIRE-II varied sample size while oxygen was held constant [PSI-99]."
        self.assertEqual(ask_module.oxygen_problems(text, main.oxygen_levels), [])

    def test_true_single_level_sentence_is_not_flagged(self):
        text = "SPICE tested several fuels at 21% oxygen [PSI-107]."
        self.assertEqual(ask_module.oxygen_problems(text, main.oxygen_levels), [])

    def test_wrong_oxygen_claim_is_retried_with_the_problem_named(self):
        bad = "No solid tests reached 30% oxygen. BASS and BASS-II tested varied oxygen concentrations [PSI-26, PSI-25]."
        good = "No solid tests reached 30% oxygen. BASS-II measured 14% to 22% [PSI-25]."
        prompts = []
        replies = iter([bad, good])

        def chat(system, prompt):
            prompts.append(prompt)
            return next(replies)

        with mock.patch.object(main, "llm_chat", return_value=chat):
            body = client.post("/ask", json={"question": "Were any solid materials tested at 30% oxygen?"}).json()
        self.assertEqual(body["answer"], good)
        self.assertIn("PSI-26 BASS ran at one oxygen level, about 21.0%", prompts[1])

    def test_claim_that_survives_the_retry_is_dropped(self):
        bad = "No solid tests reached 30% oxygen [PSI-25]. BASS tested several oxygen levels [PSI-26]."
        with mock.patch.object(main, "llm_chat", return_value=fake_chat(bad)):
            body = client.post("/ask", json={"question": "Were any solid materials tested at 30% oxygen?"}).json()
        self.assertEqual(body["answer"], "No solid tests reached 30% oxygen [PSI-25].")
        self.assertTrue(body["covered"])

    def test_guard_leaves_true_sentences_alone(self):
        true_sentences = [
            "Droplet flames went out between 12% and 15% oxygen in the same test series [PSI-69].",
            "FLEX burned droplets at several oxygen levels, from 12% to 34%, using the same fuels [PSI-69].",
            "SAFFIRE-II burned several different materials in 21.5% oxygen [PSI-99].",
            "BASS tested different solid fuels in 21% oxygen [PSI-26].",
            "SAFFIRE-II burned several materials at about 22% oxygen [PSI-99].",
            "In SAFFIRE-II, spread was 50 to 80% slower than in 1 g at 21.5% oxygen [PSI-99].",
        ]
        for sentence in true_sentences:
            with self.subTest(sentence):
                self.assertEqual(ask_module.oxygen_problems(sentence, main.oxygen_levels), [])

    def test_guard_still_catches_the_word_habitat_case(self):
        text = "For a habitat designer: BASS-II ran oxygen from 5% to 40% [PSI-25]."
        self.assertEqual([p.split(" ")[0] for p in ask_module.oxygen_problems(text, main.oxygen_levels)], ["PSI-25"])

    def test_dropping_a_sentence_keeps_headings_and_bullets(self):
        text = ("**Solid fuels**\n- BASS tested several oxygen levels [PSI-26].\n- BASS-II ran 14% to 22% O2 [PSI-25].\n\n"
                "**Liquid fuels**\n- FLEX ran 12% to 34% O2 [PSI-69].")
        self.assertEqual(ask_module.drop_oxygen_claims(text, main.oxygen_levels),
                         "**Solid fuels**\n- BASS-II ran 14% to 22% O2 [PSI-25].\n\n**Liquid fuels**\n- FLEX ran 12% to 34% O2 [PSI-69].")

    def test_the_word_same_is_not_the_same_investigation(self):
        sources = [{"accession": "OVERVIEW", "text": "x\nSolid fuels: BASS-II (PSI-25), SAME (PSI-102)"}]
        expanded = ask_module.expand_overview("BASS-II and CFI used the same lower range [OVERVIEW]", sources,
                                              {"PSI-25": "BASS-II", "PSI-102": "SAME"})
        self.assertEqual(expanded, "BASS-II and CFI used the same lower range [PSI-25]")
        self.assertTrue(ask_module._mentions("SAME measured smoke", "SAME"))
        self.assertTrue(ask_module._mentions("the ACME Flame Design tests", "ACME/Flame Design"))

    def test_ask_fails_over_to_the_fallback_without_waiting(self):
        with mock.patch.object(main, "_llm", None), mock.patch.object(main, "LLM") as client:
            main.llm_chat()
        client.assert_called_once_with(max_retries=0, timeout=main.ASK_MODEL_TIMEOUT)

    def test_guard_uses_a_single_citation_when_no_name_is_given(self):
        facts = main.oxygen_levels
        self.assertEqual([p.split(" ")[0] for p in ask_module.oxygen_problems("Oxygen ran from 5% to 40% [PSI-25].", facts)], ["PSI-25"])
        self.assertEqual([p.split(" ")[0] for p in ask_module.oxygen_problems("The study varied oxygen concentration [PSI-99].", facts)], ["PSI-99"])
        self.assertEqual(ask_module.oxygen_problems("Solid tests varied oxygen from 14% to 22% [PSI-25, PSI-98, PSI-99].", facts), [])
        self.assertEqual(ask_module.oxygen_problems("Oxygen ranged from 14% to 22% O2 [PSI-25].", facts), [])

    def test_retries_count_against_the_shared_limit_only(self):
        limiter = RateLimiter(per_minute=6, per_day=60, global_per_minute=20, global_per_day=400, clock=lambda: 100.0)
        bad = "BASS and BASS-II tested varied oxygen concentrations [PSI-26, PSI-25]."
        good = "BASS-II measured 14% to 22% O2 [PSI-25]."
        replies = iter([bad, good])
        with mock.patch.object(main, "ask_limiter", limiter), mock.patch.object(main, "llm_chat", return_value=lambda system, prompt: next(replies)):
            client.post("/ask", json={"question": "What oxygen levels did BASS-II test?"})
        self.assertEqual(len(limiter.everyone), 2)
        self.assertEqual(sum(len(q) for q in limiter.visitors.values()), 1)

    def test_leading_zero_accessions_and_bad_record_types(self):
        self.assertEqual(client.get("/investigations/PSI-069").status_code, 200)
        self.assertEqual(client.get("/tests", params={"record_type": "xyz"}).status_code, 422)
        self.assertEqual(client.get("/tests", params={"accession": "PSI-69", "record_type": "Test"}).status_code, 200)

    def test_question_validation(self):
        self.assertEqual(client.post("/ask", json={"question": "x" * 501}).status_code, 422)



@unittest.skipUnless(HAVE_DEPS, "fastapi, httpx or rank-bm25 not installed")
class CorsTests(unittest.TestCase):
    def test_default_is_the_dashboard_and_local_dev_not_everyone(self):
        self.assertEqual(main.cors_origins(None), ["https://mehdi-abidi.github.io", "http://localhost:3000"])
        self.assertEqual(main.cors_origins("  , "), ["https://mehdi-abidi.github.io", "http://localhost:3000"])
        self.assertNotIn("*", main.cors_origins(None))

    def test_env_value_is_used_when_set(self):
        self.assertEqual(main.cors_origins("https://a.example, https://b.example"), ["https://a.example", "https://b.example"])

    def test_unknown_origin_gets_no_cors_header(self):
        response = client.options("/ask", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_dashboard_origin_is_allowed(self):
        response = client.options("/ask", headers={"Origin": "https://mehdi-abidi.github.io", "Access-Control-Request-Method": "POST"})
        self.assertEqual(response.headers.get("access-control-allow-origin"), "https://mehdi-abidi.github.io")


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@unittest.skipUnless(HAVE_DEPS, "fastapi, httpx or rank-bm25 not installed")
class RateLimiterTests(unittest.TestCase):
    def test_visitor_minute_limit_and_retry_after(self):
        clock = FakeClock()
        limiter = RateLimiter(per_minute=2, per_day=10, global_per_minute=50, global_per_day=500, clock=clock)
        self.assertEqual(limiter.check("a")[0], True)
        clock.now += 10
        self.assertEqual(limiter.check("a")[0], True)
        allowed, retry_after, scope = limiter.check("a")
        self.assertEqual((allowed, retry_after, scope), (False, 50, "visitor"))
        self.assertTrue(limiter.check("b")[0])
        clock.now += 51
        self.assertTrue(limiter.check("a")[0])

    def test_visitor_day_limit(self):
        clock = FakeClock()
        limiter = RateLimiter(per_minute=100, per_day=3, global_per_minute=100, global_per_day=100, clock=clock)
        for _ in range(3):
            self.assertTrue(limiter.check("a")[0])
            clock.now += 61
        allowed, retry_after, scope = limiter.check("a")
        self.assertEqual((allowed, scope), (False, "visitor"))
        self.assertGreater(retry_after, 80000)

    def test_global_limit_protects_the_quota_across_visitors(self):
        limiter = RateLimiter(per_minute=5, per_day=50, global_per_minute=3, global_per_day=100, clock=FakeClock())
        self.assertTrue(all(limiter.check(f"ip{i}")[0] for i in range(3)))
        self.assertEqual(limiter.check("ip99")[2], "global")

    def test_blocked_requests_do_not_count(self):
        clock = FakeClock()
        limiter = RateLimiter(per_minute=1, per_day=10, global_per_minute=10, global_per_day=10, clock=clock)
        limiter.check("a")
        for _ in range(5):
            limiter.check("a")
        clock.now += 61
        self.assertTrue(limiter.check("a")[0])

    def test_visitor_key_uses_the_proxy_added_address(self):
        self.assertEqual(visitor_key("1.2.3.4, 10.0.0.1", "127.0.0.1"), "10.0.0.1")
        self.assertEqual(visitor_key("", "127.0.0.1"), "127.0.0.1")
        self.assertEqual(visitor_key(None, None), "unknown")

    def test_env_overrides_and_bad_values_fall_back(self):
        with mock.patch.dict("os.environ", {"ASK_LIMIT_PER_MINUTE": "2", "ASK_GLOBAL_PER_DAY": "abc", "ASK_LIMIT_PER_DAY": "-5"}):
            limiter = RateLimiter.from_env()
        self.assertEqual(limiter.rules["visitor"], ((60.0, 2), (86400.0, 60)))
        self.assertEqual(limiter.rules["global"], ((60.0, 20), (86400.0, 400)))

    def test_ask_endpoint_answers_429_with_retry_after(self):
        original = main.ask_limiter
        main.ask_limiter = RateLimiter(per_minute=1, per_day=10, global_per_minute=10, global_per_day=10)
        try:
            with mock.patch.object(main, "llm_chat", return_value=fake_chat("Helium did [PSI-69].")):
                first = client.post("/ask", json={"question": AskTests.QUESTION})
                second = client.post("/ask", json={"question": AskTests.QUESTION})
        finally:
            main.ask_limiter = original
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertTrue(int(second.headers["retry-after"]) >= 1)
        self.assertIn("Too many questions from you", second.json()["detail"])


if __name__ == "__main__":
    unittest.main()
