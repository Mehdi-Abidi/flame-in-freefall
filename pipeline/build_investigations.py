"""Build data/processed/investigations.json (task D3).

Combines three raw sources that are all keyed by `accession` (e.g. "PSI-69"):
  - data/raw/catalog.json              -> one row per investigation, search-result style
  - data/raw/index.json                -> one row per investigation, file counts
  - data/raw/investigations/PSI-*.json -> full metadata, one file per investigation
and one computed source:
  - data/processed/tests.csv           -> normalized test rows (task D2), grouped by accession

Fills every field in the investigations.json schema (docs/EXECUTION_PLAN.md, section 6)
that can be read or computed today. Fields that need the LLM extraction (S2) or domain
tagging (T1) are left as null/empty placeholders so Mehdi's merge (D5) has one file to
write into instead of inventing the structure later.

Usage: python pipeline/build_investigations.py [--raw data/raw] [--processed data/processed]
"""

import argparse
import csv
import glob
import json
import os


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_catalog_by_accession(raw_dir):
    """data/raw/catalog.json is a list; index it by accession for O(1) lookup."""
    catalog = load_json(os.path.join(raw_dir, "catalog.json"))
    return {entry["Accession"]: entry for entry in catalog}


def load_index_by_accession(raw_dir):
    """data/raw/index.json is also a list, same shape of lookup."""
    index = load_json(os.path.join(raw_dir, "index.json"))
    return {entry["accession"]: entry for entry in index}


def load_investigation_detail(raw_dir, accession):
    """One JSON file per investigation: data/raw/investigations/PSI-69.json."""
    path = os.path.join(raw_dir, "investigations", f"{accession}.json")
    return load_json(path)


def clean(text):
    """Turn a blank/whitespace-only string into None.

    The five ground studies (PSI-60, PSI-62, PSI-115, PSI-117, PSI-142) really do
    have "" for acronym, hardware and flight platform in the raw PSI data -- they
    are literature/modeling studies with no flight hardware, not a parsing bug.
    But an empty string and "we don't have this" should look the same to any
    consumer of this file, so we normalize "" to null rather than passing it through.
    """
    text = (text or "").strip()
    return text or None


PLATFORMS = {"space station": "ISS", "(iss)": "ISS", "cygnus": "Cygnus", "shuttle": "Space Shuttle"}
O2_BASIS_PRIORITY = ("measured", "approximate", "test_day_list", "planned", "nominal_cabin_air")
PRESSURE_BASIS_PRIORITY = ("measured", "planned", "nominal_1atm", "nominal_cabin")


def platform_from_flight_platform(text, project_type=None):
    """Map PSI's free-text flight platform to ISS, Cygnus, Space Shuttle or ground."""
    if project_type and "ground" in project_type.lower():
        return "ground"
    lowered = (text or "").strip().lower()
    if not lowered or lowered == "not applicable":
        return None
    for needle, short in PLATFORMS.items():
        if needle in lowered:
            return short
    return text.strip()


def extract_publications(detail):
    """Keep only title + authors, per the schema. The raw list carries a lot more
    (DOIs, pubmed IDs, EFO ontology IDs) that nobody downstream asked for.
    """
    out = []
    for pub in detail.get("publications", []):
        title = (pub.get("title") or "").strip()
        authors = ", ".join(name.strip() for name in (pub.get("authorList") or "").split(",")
                            if name.strip() and "undefined" not in name.lower())
        if title:
            out.append({"title": title, "authors": authors})
    return out


def psi_url(accession):
    return f"https://psi.nasa.gov/physci/repo/data/investigations/{accession}"


def load_tests_by_accession(processed_dir):
    """Group tests.csv rows by accession so we can compute ranges per investigation.

    Returns {accession: [row, row, ...]} using the raw csv.DictReader rows (all
    strings) -- numeric parsing happens where we use them, so a blank stays blank
    instead of silently becoming 0.
    """
    path = os.path.join(processed_dir, "tests.csv")
    by_accession = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_accession.setdefault(row["accession"], []).append(row)
    return by_accession


def to_float(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def range_with_basis(rows, value_field, source_field, priority, digits):
    """Return ([min, max], basis) using the most trustworthy source tag present.

    Measured values win. If none are measured, the next best tag is used and named in
    basis, so a nominal or planned range is never mistaken for a tested one.
    """
    tagged = [(to_float(r[value_field]), r[source_field]) for r in rows]
    tagged = [(value, source) for value, source in tagged if value is not None and source]
    for basis in priority:
        values = [value for value, source in tagged if source == basis]
        if values:
            return [round(min(values), digits), round(max(values), digits)], basis
    return None, None


def compute_ranges(rows):
    """Summarize one investigation's tests.csv rows: counts, fuel phases, O2 and pressure ranges."""
    o2_range, o2_basis = range_with_basis(rows, "o2_mole_fraction", "o2_source", O2_BASIS_PRIORITY, 3)
    pressure_range, pressure_basis = range_with_basis(rows, "pressure_kpa", "pressure_source", PRESSURE_BASIS_PRIORITY, 1)
    return {
        "n_tests": sum(1 for r in rows if r.get("record_type") == "test"),
        "n_records": len(rows),
        "o2_range": o2_range,
        "o2_basis": o2_basis,
        "pressure_kpa_range": pressure_range,
        "pressure_basis": pressure_basis,
        "fuel_phase": sorted({r["fuel_phase"] for r in rows if r.get("fuel_phase")}),
    }


def build_one(accession, catalog_entry, index_entry, detail, test_rows):
    ranges = compute_ranges(test_rows)
    project_type = clean(index_entry.get("project_type")) or clean(catalog_entry.get("Project Type"))

    return {
        "accession": accession,
        "acronym": clean(index_entry.get("acronym")) or clean(catalog_entry.get("Acronym")),
        "title": clean(index_entry.get("title")) or clean(catalog_entry.get("Title")),
        "project_type": project_type,
        "platform": platform_from_flight_platform(catalog_entry.get("Flight Platform"), project_type),
        "hardware": clean(index_entry.get("hardware")) or clean(detail.get("experimentHardware")),
        "pillars": None,
        "summary": None,
        "variables_varied": None,
        "variables_fixed": None,
        "sensors": None,
        "fuel_phase": ranges["fuel_phase"],
        "o2_range": ranges["o2_range"],
        "o2_basis": ranges["o2_basis"],
        "pressure_kpa_range": ranges["pressure_kpa_range"],
        "pressure_basis": ranges["pressure_basis"],
        "n_tests": ranges["n_tests"],
        "n_records": ranges["n_records"],
        "n_experimental_tables": len(index_entry.get("experimental_tables") or []),
        "n_files": index_entry.get("files", {}).get("file_count"),
        "publications": extract_publications(detail),
        "psi_url": psi_url(accession),
        "scores": {},
        "rationale": {},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--processed", default="data/processed")
    args = parser.parse_args()

    catalog_by_accession = load_catalog_by_accession(args.raw)
    index_by_accession = load_index_by_accession(args.raw)
    tests_by_accession = load_tests_by_accession(args.processed)

    detail_paths = sorted(glob.glob(os.path.join(args.raw, "investigations", "PSI-*.json")))
    accessions = sorted((os.path.splitext(os.path.basename(p))[0] for p in detail_paths),
                        key=lambda accession: int(accession.split("-")[1]))

    investigations = []
    for accession in accessions:
        catalog_entry = catalog_by_accession.get(accession, {})
        index_entry = index_by_accession.get(accession, {})
        detail = load_investigation_detail(args.raw, accession)
        test_rows = tests_by_accession.get(accession, [])
        investigations.append(
            build_one(accession, catalog_entry, index_entry, detail, test_rows)
        )

    out_path = os.path.join(args.processed, "investigations.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(investigations, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    with_table = sum(1 for inv in investigations if inv["n_experimental_tables"])
    with_records = sum(1 for inv in investigations if inv["n_records"])
    with_measured_o2 = sum(1 for inv in investigations if inv["o2_basis"] == "measured")
    print(f"Wrote {len(investigations)} investigations to {out_path}")
    print(f"{with_table} have an experimental table, {with_records} have rows in tests.csv, "
          f"{with_measured_o2} have a measured O2 range")


if __name__ == "__main__":
    main()
