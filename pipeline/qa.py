"""Check data/processed/tests.csv against the data contract and the raw PSI tables.

Usage: python pipeline/qa.py [--raw data/raw] [--processed data/processed]
Exits with status 1 if any check fails.
"""

import argparse
import collections
import csv
import io
import json
import os
import re
import sys

EXPECTED_COLUMNS = [
    "row_id", "accession", "acronym", "source_file", "record_type", "test_id", "date",
    "fuel", "fuel_phase", "geometry", "size_mm",
    "o2_mole_fraction", "o2_source", "pressure_kpa", "pressure_source",
    "diluent", "flow_cm_s", "gravity", "outcome", "burn_time_s", "n_flames", "notes",
]
ENUMS = {
    "record_type": {"test", "test_day", "test_day_condition", "condition_matrix", "session"},
    "fuel_phase": {"solid", "liquid", "gas", "dust"},
    "gravity": {"micro", "1g"},
    "o2_source": {"", "measured", "planned", "approximate", "test_day_list", "nominal_cabin_air"},
    "pressure_source": {"", "measured", "planned", "nominal_cabin", "nominal_1atm"},
}
RANGES = {
    "o2_mole_fraction": (0.05, 1.0),
    "pressure_kpa": (20.0, 700.0),
    "size_mm": (0.0, 200.0),
    "flow_cm_s": (0.0, 200.0),
    "burn_time_s": (0.0, 2000.0),
}


class Report:
    def __init__(self):
        self.failures = 0

    def check(self, name, problems):
        status = "PASS" if not problems else "FAIL"
        print(f"[{status}] {name}" + ("" if not problems else f": {len(problems)} problem(s), e.g. {problems[:3]}"))
        self.failures += bool(problems)


def number(value):
    return float(value) if value not in ("", None) else None


def raw_rows(raw_dir, name):
    with open(os.path.join(raw_dir, "tables", name), "rb") as handle:
        data = handle.read()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    rows = [r for r in csv.reader(io.StringIO(text, newline="")) if any(c.strip() for c in r)]
    unique = []
    seen = set()
    for r in rows[1:]:
        signature = tuple(c.strip() for c in r)
        if signature not in seen:
            seen.add(signature)
            unique.append(r)
    return unique


def compare(tests, raw_dir, source, raw_filter, checker):
    produced = [t for t in tests if t["source_file"] == source]
    source_rows = [r for r in raw_rows(raw_dir, source) if raw_filter(r)]
    problems = []
    if len(produced) != len(source_rows):
        problems.append(f"{len(produced)} output rows vs {len(source_rows)} source rows")
    for raw, out in zip(source_rows, produced):
        try:
            if not checker(raw, out):
                problems.append(out["row_id"])
        except (ValueError, IndexError) as error:
            problems.append(f"{out['row_id']}: {error}")
    return problems


def close(a, b, tolerance):
    return abs(a - b) <= tolerance


INVESTIGATION_KEYS = {
    "accession", "acronym", "title", "project_type", "platform", "hardware", "pillars", "summary",
    "variables_varied", "variables_fixed", "sensors", "fuel_phase", "o2_range", "o2_basis",
    "pressure_kpa_range", "pressure_basis", "n_tests", "n_records", "n_experimental_tables", "n_files",
    "publications", "psi_url", "scores", "rationale",
}
PLATFORMS = {"ISS", "Cygnus", "Space Shuttle", "ground"}


def expected_range(rows, value_field, source_field):
    measured = [number(r[value_field]) for r in rows if r[source_field] == "measured" and r[value_field]]
    if measured:
        return [min(measured), max(measured)], "measured"
    others = {r[source_field] for r in rows if r[value_field] and r[source_field]}
    return None, others


EXTRACTED_KEYS = {
    "accession", "acronym", "summary", "objective_short", "sample_size", "pillar_reason", "fuels", "sample_geometry",
    "variables_varied", "variables_fixed", "sensors", "measurements", "earth_benefits", "pillars", "fuel_phase",
    "warnings", "model", "prompt_version",
}
EXTRACTED_LISTS = ("fuels", "sample_geometry", "variables_varied", "variables_fixed", "sensors", "measurements",
                   "earth_benefits", "pillars", "fuel_phase", "warnings")


def check_extracted(report, processed_dir):
    path = os.path.join(processed_dir, "extracted.json")
    if not os.path.exists(path):
        print("\nextracted.json not present yet, skipping its checks")
        return
    with open(path, encoding="utf-8") as handle:
        extracted = json.load(handle)
    with open(os.path.join(processed_dir, "investigations.json"), encoding="utf-8") as handle:
        investigations = {i["accession"]: i for i in json.load(handle)}
    print("\nChecks on extracted.json")
    accessions = [r.get("accession") for r in extracted]
    report.check("one extracted record per investigation",
                 [] if sorted(accessions) == sorted(investigations) and len(set(accessions)) == len(accessions)
                 else [f"{len(accessions)} records vs {len(investigations)} investigations"])
    report.check("extracted fields match the data contract",
                 [f"{r.get('accession')}: {sorted(set(r) ^ EXTRACTED_KEYS)}" for r in extracted if set(r) != EXTRACTED_KEYS])
    report.check("list fields are lists of text",
                 [f"{r['accession']}.{f}" for r in extracted for f in EXTRACTED_LISTS
                  if not isinstance(r.get(f), list) or not all(isinstance(x, str) for x in r.get(f) or [])])
    report.check("pillars and phases use allowed values",
                 [r["accession"] for r in extracted
                  if not set(r.get("pillars") or []) <= {"prevention", "detection", "suppression"}
                  or not set(r.get("fuel_phase") or []) <= {"solid", "liquid", "gas", "dust"}])
    report.check("fuel phase agrees with the test tables",
                 [r["accession"] for r in extracted
                  if investigations.get(r["accession"], {}).get("fuel_phase") and r.get("fuel_phase") != investigations[r["accession"]]["fuel_phase"]])
    report.check("every record has a summary", [r["accession"] for r in extracted if not r.get("summary")])
    report.check("no condition listed as both varied and fixed",
                 [f"{r['accession']}: {sorted({v.lower() for v in r.get('variables_varied') or []} & {v.lower() for v in r.get('variables_fixed') or []})}"
                  for r in extracted
                  if {v.lower() for v in r.get("variables_varied") or []} & {v.lower() for v in r.get("variables_fixed") or []}])
    report.check("no summary contradicts the test tables",
                 [f"{r['accession']}: {w}" for r in extracted for w in r.get("warnings") or [] if w.startswith("summary may call")])
    report.check("one prompt version and model across the file",
                 [] if len({(r.get("prompt_version"), r.get("model")) for r in extracted}) == 1
                 else [sorted({f"{r.get('prompt_version')}/{r.get('model')}" for r in extracted})])
    flagged = [r["accession"] for r in extracted if r.get("warnings")]
    print(f"  {len(flagged)} record(s) carry review warnings (see docs/extraction-review.md): {', '.join(flagged) or 'none'}")


def check_briefs(report, processed_dir):
    path = os.path.join(processed_dir, "briefs.json")
    if not os.path.exists(path):
        print("\nbriefs.json not present yet, skipping its checks")
        return
    with open(path, encoding="utf-8") as handle:
        briefs = (json.load(handle) or {}).get("briefs") or {}
    with open(os.path.join(processed_dir, "rankings.json"), encoding="utf-8") as handle:
        ranking = json.load(handle)["scenarios"]["lunar_base"]["ranking"]
    members = collections.defaultdict(list)
    for entry in sorted(ranking, key=lambda e: e["rank"]):
        for pillar in entry.get("pillars") or []:
            members[pillar].append(entry["accession"])
    print("\nChecks on briefs.json")
    expected = sorted(p for p in ("prevention", "detection", "suppression") if members.get(p))
    report.check("one brief per pillar that has investigations", [] if sorted(briefs) == expected else [f"{sorted(briefs)} vs {expected}"])
    shape, citations, stale, source = [], [], [], []
    for pillar, brief in briefs.items():
        findings = brief.get("findings") or []
        if not brief.get("title") or len(findings) != 3 or not brief.get("implication") or not brief.get("gap"):
            shape.append(pillar)
        for finding in findings:
            cited = finding.get("citations") or []
            if not cited or any(c not in members.get(pillar, []) for c in cited):
                citations.append(f"{pillar}: {cited}")
        if brief.get("members") != members.get(pillar):
            stale.append(pillar)
        if brief.get("source") not in {"model", "template", "reviewed"} or not brief.get("review"):
            source.append(pillar)
    report.check("briefs have a title, 3 findings, an implication and a gap", shape)
    report.check("every finding cites investigations from its own pillar", citations)
    report.check("briefs match current pillar membership (rerun python -m si.briefs if stale)", stale)
    report.check("briefs carry a source and a review status", source)
    pending = [p for p, b in briefs.items() if b.get("review") == "awaiting expert review"]
    print(f"  {len(pending)} brief(s) awaiting expert review: {', '.join(pending) or 'none'}")


def check_rationales(report, processed_dir):
    path = os.path.join(processed_dir, "rationale.json")
    if not os.path.exists(path):
        print("\nrationale.json not present yet, skipping its checks")
        return
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    with open(os.path.join(processed_dir, "rankings.json"), encoding="utf-8") as handle:
        rankings = json.load(handle)["scenarios"]
    print("\nChecks on rationale.json")
    rationales = document.get("rationales") or {}
    missing, stale, bad_source, bad_text = [], [], [], []
    for scenario_id, scenario in rankings.items():
        for entry in scenario["ranking"]:
            record = (rationales.get(scenario_id) or {}).get(entry["accession"])
            key = f"{scenario_id}/{entry['accession']}"
            if not record:
                missing.append(key)
                continue
            if record.get("rank") != entry["rank"] or abs((record.get("score") or 0) - entry["score"]) > 1e-9:
                stale.append(key)
            if record.get("source") not in {"model", "template"}:
                bad_source.append(key)
            text = record.get("text") or ""
            sentence_count = len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])
            if not text or sentence_count != 2 or "—" in text or "–" in text:
                bad_text.append(key)
    report.check("a rationale for every habitat and investigation", missing)
    report.check("rationales match the current rankings (rerun python -m si.rationale if stale)", stale)
    report.check("rationale source is model or template", bad_source)
    report.check("rationales are two sentences without dashes", bad_text)
    templates = sum(1 for s in rationales.values() for r in s.values() if r.get("source") == "template")
    print(f"  {templates} rationale(s) fell back to the fact-only template")


def check_rankings(report, processed_dir, domain_dir):
    path = os.path.join(processed_dir, "rankings.json")
    if not os.path.exists(path):
        print("\nrankings.json not present yet, skipping its checks")
        return
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    with open(os.path.join(processed_dir, "investigations.json"), encoding="utf-8") as handle:
        accessions = sorted(i["accession"] for i in json.load(handle))
    with open(os.path.join(domain_dir, "scenarios.json"), encoding="utf-8") as handle:
        scenario_ids = [s["id"] for s in json.load(handle)["scenarios"]]
    print("\nChecks on rankings.json")
    rankings = document.get("scenarios") or {}
    weights = document.get("component_weights") or {}
    report.check("one ranking per habitat in scenarios.json", [] if sorted(rankings) == sorted(scenario_ids) else [f"{sorted(rankings)} vs {sorted(scenario_ids)}"])
    report.check("component weights sum to 1", [] if abs(sum(weights.values()) - 1) < 1e-9 else [weights])
    coverage, order, bounds, sums, sources = [], [], [], [], []
    for scenario_id, scenario in rankings.items():
        ranking = scenario.get("ranking") or []
        if sorted(r["accession"] for r in ranking) != accessions:
            coverage.append(scenario_id)
        if [r["rank"] for r in ranking] != list(range(1, len(ranking) + 1)) or any(a["score"] < b["score"] for a, b in zip(ranking, ranking[1:])):
            order.append(scenario_id)
        for r in ranking:
            values = [r["score"], *r["components"].values()]
            if not all(0.0 <= v <= 1.0 for v in values):
                bounds.append(f"{scenario_id}/{r['accession']}")
            if abs(r["score"] - sum(weights.get(k, 0) * v for k, v in r["components"].items())) > 0.001:
                sums.append(f"{scenario_id}/{r['accession']}")
            if r.get("pillar_source") not in {"tags", "seed", "model", "none"}:
                sources.append(f"{scenario_id}/{r['accession']}")
    report.check("every investigation ranked once per habitat", coverage)
    report.check("ranks run 1 to N in score order", order)
    report.check("scores and components between 0 and 1", bounds)
    report.check("each score equals the weighted sum of its components", sums)
    report.check("pillar source is tags, seed, model or none", sources)


def check_investigations(report, raw_dir, processed_dir, tests):
    path = os.path.join(processed_dir, "investigations.json")
    if not os.path.exists(path):
        report.check("investigations.json exists", [path])
        return
    with open(path, encoding="utf-8") as handle:
        investigations = json.load(handle)
    print("\nChecks on investigations.json")
    raw_accessions = sorted(os.path.splitext(n)[0] for n in os.listdir(os.path.join(raw_dir, "investigations")))
    accessions = [i["accession"] for i in investigations]
    report.check("one record per PSI investigation", [] if sorted(accessions) == raw_accessions and len(set(accessions)) == len(accessions)
                 else [f"{len(accessions)} records vs {len(raw_accessions)} raw files"])
    report.check("fields match the data contract", [f"{i['accession']}: {sorted(set(i) ^ INVESTIGATION_KEYS)}" for i in investigations if set(i) != INVESTIGATION_KEYS])
    report.check("platform values allowed", [f"{i['accession']}={i.get('platform')}" for i in investigations if i.get("platform") not in PLATFORMS])
    report.check("psi_url points at the accession", [i["accession"] for i in investigations if not str(i.get("psi_url")).endswith("/" + i["accession"])])

    rows_by_accession = collections.defaultdict(list)
    for t in tests:
        rows_by_accession[t["accession"]].append(t)
    count_problems, range_problems, basis_problems = [], [], []
    for inv in investigations:
        rows = rows_by_accession.get(inv["accession"], [])
        real_tests = sum(1 for r in rows if r["record_type"] == "test")
        if inv.get("n_tests") != real_tests or inv.get("n_records") != len(rows):
            count_problems.append(f"{inv['accession']}: n_tests {inv.get('n_tests')} vs {real_tests}, n_records {inv.get('n_records')} vs {len(rows)}")
        for value_field, source_field, range_key, basis_key in (("o2_mole_fraction", "o2_source", "o2_range", "o2_basis"),
                                                                 ("pressure_kpa", "pressure_source", "pressure_kpa_range", "pressure_basis")):
            got_range, got_basis = inv.get(range_key), inv.get(basis_key)
            want_range, want_basis = expected_range(rows, value_field, source_field)
            if (got_range is None) != (got_basis is None):
                basis_problems.append(f"{inv['accession']}: {range_key} and {basis_key} disagree on being empty")
            if want_basis == "measured":
                if got_basis != "measured" or not got_range or not (close(got_range[0], want_range[0], 0.06) and close(got_range[1], want_range[1], 0.06)):
                    range_problems.append(f"{inv['accession']}: {range_key} {got_range} ({got_basis}) vs measured {want_range}")
            elif got_basis == "measured":
                basis_problems.append(f"{inv['accession']}: {basis_key} says measured but no measured rows exist")
            elif got_basis is not None and got_basis not in want_basis:
                basis_problems.append(f"{inv['accession']}: {basis_key} {got_basis} not among source tags {sorted(want_basis)}")
    report.check("n_tests counts only real tests, n_records counts all rows", count_problems)
    report.check("ranges use measured values whenever they exist", range_problems)
    report.check("range basis matches the source tags in tests.csv", basis_problems)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--processed", default="data/processed")
    args = parser.parse_args()

    with open(os.path.join(args.processed, "tests.csv"), encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        tests = list(reader)
    report = Report()
    print(f"{len(tests)} rows in tests.csv\n")

    report.check("columns match the data contract", [] if columns == EXPECTED_COLUMNS else [f"got {columns}"])
    report.check("row_id is unique", [k for k, v in collections.Counter(t["row_id"] for t in tests).items() if v > 1])
    for field, allowed in ENUMS.items():
        report.check(f"{field} values allowed", sorted({t[field] for t in tests} - allowed))
    report.check("no blank fuel", [t["row_id"] for t in tests if not t["fuel"]])

    for field, (low, high) in RANGES.items():
        report.check(f"{field} within {low} to {high}",
                     [f"{t['row_id']}={t[field]}" for t in tests if number(t[field]) is not None and not low <= number(t[field]) <= high])
    for value, source in (("o2_mole_fraction", "o2_source"), ("pressure_kpa", "pressure_source")):
        report.check(f"{value} present exactly when {source} is set",
                     [t["row_id"] for t in tests if (t[value] == "") != (t[source] == "")])
    report.check("dates are ISO or blank", [f"{t['row_id']}={t['date']}" for t in tests if t["date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", t["date"])])
    report.check("nominal values never tagged measured",
                 [t["row_id"] for t in tests if t["o2_source"] == "measured" and t["acronym"] in {"SPICE", "BASS", "SAME", "SAME-R", "SAFFIRE-III"}])

    print("\nSpot checks against raw tables")
    mmhg = 101.325 / 760
    report.check("FLEX pressure, O2 and droplet size", compare(
        tests, args.raw, "PSI-69_Experimental table_FLEX.csv", lambda r: True,
        lambda r, o: o["test_id"] == r[1]
        and (not number(r[5]) or close(number(o["pressure_kpa"]), float(r[5]) * mmhg, 0.01))
        and (not r[6] or close(number(o["o2_mole_fraction"]), float(r[6]), 1e-6))
        and (not re.fullmatch(r"[\d.]+", r[10]) or close(number(o["size_mm"]), float(r[10]), 1e-6))))
    report.check("CFI-G inverse pressure, and no ambient O2 from the burner's oxidizer stream", compare(
        tests, args.raw, "PSI-159_Experimental table_CFI-G_Inverse Flames.csv", lambda r: r[3].strip(),
        lambda r, o: o["test_id"] == r[3].strip() and close(number(o["pressure_kpa"]), float(r[6]) * 100, 0.01)
        and number(o["o2_mole_fraction"]) is None and o["o2_source"] == "" and "inverse flame" in o["notes"]))
    report.check("no inverse-flame row carries an ambient O2 value",
                 [t["row_id"] for t in tests if "inverse" in t["geometry"] and t["o2_mole_fraction"]])
    report.check("CFI-G normal pressure and O2", compare(
        tests, args.raw, "PSI-159_Experimental table_CFI-G_Normal Flames.csv", lambda r: r[3].strip(),
        lambda r, o: o["test_id"] == r[3].strip() and close(number(o["pressure_kpa"]), float(r[7]) * 100, 0.01)
        and (not r[5] or close(number(o["o2_mole_fraction"]), float(r[5]), 1e-4))))
    report.check("BASS-II O2 percent to fraction", compare(
        tests, args.raw, "PSI-25_Experimental table_BASS-II.csv", lambda r: True,
        lambda r, o: not r[11] or close(number(o["o2_mole_fraction"]), float(r[11]) / 100, 1e-6)))
    report.check("Flame Design normal pressure", compare(
        tests, args.raw, "PSI-10_Experimental table_Flame Design_Normal Flame.csv", lambda r: True,
        lambda r, o: o["test_id"] == r[3] and (not number(o["pressure_kpa"]) or close(number(o["pressure_kpa"]), float(r[12] or r[10]) * 101.325, 0.01))))

    check_investigations(report, args.raw, args.processed, tests)
    check_extracted(report, args.processed)
    check_rankings(report, args.processed, os.path.join(os.path.dirname(args.raw.rstrip("/").rstrip(chr(92))) or ".", "domain"))
    check_rationales(report, args.processed)
    check_briefs(report, args.processed)

    solid = [number(t["o2_mole_fraction"]) for t in tests if t["fuel_phase"] == "solid" and t["o2_source"] == "measured"]
    lunar = [t for t in tests if t["record_type"] == "test" and t["o2_source"] == "measured"
             and number(t["o2_mole_fraction"]) >= 0.30 and number(t["pressure_kpa"]) is not None and number(t["pressure_kpa"]) <= 70.3]
    print("\nHeadline numbers (README and pitch)")
    print(f"  solid tests with measured O2: {len(solid)}, highest O2: {max(solid):.3f}")
    print(f"  tests at lunar-base conditions: {len(lunar)}, phases: {dict(collections.Counter(t['fuel_phase'] for t in lunar))}")

    print(f"\n{'ALL CHECKS PASSED' if not report.failures else f'{report.failures} CHECK(S) FAILED'}")
    sys.exit(1 if report.failures else 0)


if __name__ == "__main__":
    main()
