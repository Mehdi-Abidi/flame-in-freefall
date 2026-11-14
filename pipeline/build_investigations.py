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


def platform_from_flight_platform(text):
    """Catalog says 'International Space Station (ISS)'; the schema wants just 'ISS'.

    Keep it simple: if the text contains a known short form, use that; otherwise
    keep the original text rather than guessing.
    """
    if not text:
        return None
    known = {
        "ISS": "ISS",
        "Ground": "ground",
    }
    for needle, short in known.items():
        if needle.lower() in text.lower():
            return short
    return text


def extract_publications(detail):
    """Keep only title + authors, per the schema. The raw list carries a lot more
    (DOIs, pubmed IDs, EFO ontology IDs) that nobody downstream asked for.
    """
    out = []
    for pub in detail.get("publications", []):
        title = (pub.get("title") or "").strip()
        authors = (pub.get("authorList") or "").strip()
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


def compute_ranges(rows):
    """From this investigation's test rows, compute o2_range, pressure_kpa_range,
    n_tests and the set of fuel phases actually tested.

    We use every row that has a value, regardless of o2_source/pressure_source
    (measured vs nominal_cabin_air etc.) -- the range describes what the table
    covers, same as the map draws both solid and hollow dots. qa.py / the map
    layer is where "measured only" filtering belongs, not here.
    """
    n_tests = len(rows)
    o2_values = [v for v in (to_float(r["o2_mole_fraction"]) for r in rows) if v is not None]
    pressure_values = [v for v in (to_float(r["pressure_kpa"]) for r in rows) if v is not None]
    fuel_phases = sorted({r["fuel_phase"] for r in rows if r.get("fuel_phase")})

    o2_range = [round(min(o2_values), 3), round(max(o2_values), 3)] if o2_values else None
    pressure_range = (
        [round(min(pressure_values), 1), round(max(pressure_values), 1)]
        if pressure_values
        else None
    )
    return {
        "n_tests": n_tests,
        "o2_range": o2_range,
        "pressure_kpa_range": pressure_range,
        "fuel_phase": fuel_phases,
    }


def build_one(accession, catalog_entry, index_entry, detail, test_rows):
    ranges = compute_ranges(test_rows) if test_rows else {
        "n_tests": 0,
        "o2_range": None,
        "pressure_kpa_range": None,
        "fuel_phase": [],
    }

    return {
        "accession": accession,
        "acronym": clean(index_entry.get("acronym")) or clean(catalog_entry.get("Acronym")),
        "title": clean(index_entry.get("title")) or clean(catalog_entry.get("Title")),
        "project_type": clean(index_entry.get("project_type")) or clean(catalog_entry.get("Project Type")),
        "platform": platform_from_flight_platform(catalog_entry.get("Flight Platform")),
        "hardware": clean(index_entry.get("hardware")) or clean(detail.get("experimentHardware")),

        # Filled later by S2 (LLM extraction) + D5 (merge). Kept here, as null,
        # so the file's shape never has to change -- only these values do.
        "pillars": None,
        "summary": None,
        "variables_varied": None,
        "variables_fixed": None,
        "sensors": None,

        "fuel_phase": ranges["fuel_phase"],
        "o2_range": ranges["o2_range"],
        "pressure_kpa_range": ranges["pressure_kpa_range"],
        "n_tests": ranges["n_tests"],
        "n_files": index_entry.get("files", {}).get("file_count"),
        "publications": extract_publications(detail),
        "psi_url": psi_url(accession),

        # Filled later by S3/S4 (ranking engine + rationale writer).
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
    accessions = [os.path.splitext(os.path.basename(p))[0] for p in detail_paths]

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
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(investigations, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    with_ranges = sum(1 for inv in investigations if inv["o2_range"] is not None)
    print(f"Wrote {len(investigations)} investigations to {out_path}")
    print(f"{with_ranges} have o2/pressure ranges filled; "
          f"{len(investigations) - with_ranges} have no experimental table yet.")


if __name__ == "__main__":
    main()
