"""Check data/processed/tests.csv against the data contract and the raw PSI tables.

Usage: python pipeline/qa.py [--raw data/raw] [--processed data/processed]
Exits with status 1 if any check fails.
"""

import argparse
import collections
import csv
import io
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
    report.check("CFI-G inverse pressure and O2", compare(
        tests, args.raw, "PSI-159_Experimental table_CFI-G_Inverse Flames.csv", lambda r: r[3].strip(),
        lambda r, o: o["test_id"] == r[3].strip() and close(number(o["pressure_kpa"]), float(r[6]) * 100, 0.01)
        and close(number(o["o2_mole_fraction"]), float(r[7]), 1e-4)))
    report.check("CFI-G normal pressure and O2", compare(
        tests, args.raw, "PSI-159_Experimental table_CFI-G_Normal Flames.csv", lambda r: r[3].strip(),
        lambda r, o: o["test_id"] == r[3].strip() and close(number(o["pressure_kpa"]), float(r[7]) * 100, 0.01)
        and (not r[5] or close(number(o["o2_mole_fraction"]), float(r[5]), 1e-4))))
    report.check("BASS-II O2 percent to fraction", compare(
        tests, args.raw, "PSI-25_Experimental table_BASS-II.csv", lambda r: True,
        lambda r, o: not r[11] or close(number(o["o2_mole_fraction"]), float(r[11]) / 100, 1e-6)))
    report.check("Flame Design normal pressure", compare(
        tests, args.raw, "PSI-10_Experimental table_Flame Design_Normal Flame.csv", lambda r: True,
        lambda r, o: o["test_id"] == r[3] and (not number(o["pressure_kpa"]) or close(number(o["pressure_kpa"]), float(r[12]) * 101.325, 0.01))))

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
