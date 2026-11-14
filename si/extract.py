"""Extract structured fire-safety facts for every PSI combustion investigation (task S2).

Usage: python -m si.extract [--only PSI-69 PSI-25] [--model openai/gpt-oss-20b]
Writes data/processed/extracted.json.
"""

import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def load_tests(path=PROCESSED / "tests.csv"):
    by_accession = collections.defaultdict(list)
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            by_accession[row["accession"]].append(row)
    return by_accession


def load_investigations(path=PROCESSED / "investigations.json"):
    with open(path, encoding="utf-8") as handle:
        return {record["accession"]: record for record in json.load(handle)}


PLACEHOLDERS = {"unknown", "sample", "n/a", "none"}


def top_values(rows, field, limit):
    counts = collections.Counter(row[field].strip() for row in rows
                                 if row.get(field, "").strip() and row[field].strip().lower() not in PLACEHOLDERS)
    return [value for value, _ in counts.most_common(limit)]


def numeric_range(rows, field):
    values = []
    for row in rows:
        try:
            values.append(float(row[field]))
        except (KeyError, ValueError):
            pass
    return [min(values), max(values)] if values else None


TEXT_LIMITS = {"objective": 1600, "approach": 2000, "hypothesis": 900, "researchImpacts": 900}


def load_metadata(accession, raw_dir=RAW):
    with open(Path(raw_dir) / "investigations" / f"{accession}.json", encoding="utf-8") as handle:
        return json.load(handle)


def load_keywords(raw_dir=RAW):
    with open(Path(raw_dir) / "catalog.json", encoding="utf-8") as handle:
        return {entry["Accession"]: " ".join((entry.get("Keywords") or "").split()) for entry in json.load(handle)}


def clip(text, limit):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def text_context(metadata, keywords="", max_publications=6):
    """The NASA write-up for one investigation, trimmed so one request stays under free-tier limits."""
    sections = {name: clip(metadata.get(name), limit) for name, limit in TEXT_LIMITS.items()}
    titles = [clip(p.get("title"), 160) for p in metadata.get("publications") or [] if p.get("title")]
    return {
        "title": clip(metadata.get("title"), 200),
        "keywords": clip(keywords, 300),
        **sections,
        "publication_titles": titles[:max_publications],
    }


def data_facts(investigation, rows):
    """Facts already proven by tests.csv and investigations.json, handed to the model as ground truth."""
    return {
        "record_types": dict(collections.Counter(row["record_type"] for row in rows)),
        "n_tests": investigation.get("n_tests", 0),
        "fuel_phase": investigation.get("fuel_phase") or [],
        "fuels_in_tables": top_values(rows, "fuel", 15),
        "geometries_in_tables": top_values(rows, "geometry", 8),
        "diluents_in_tables": top_values(rows, "diluent", 6),
        "outcomes_in_tables": top_values(rows, "outcome", 8),
        "size_mm_range": numeric_range(rows, "size_mm"),
        "flow_cm_s_range": numeric_range(rows, "flow_cm_s"),
        "o2_range": investigation.get("o2_range"),
        "o2_basis": investigation.get("o2_basis"),
        "pressure_kpa_range": investigation.get("pressure_kpa_range"),
        "pressure_basis": investigation.get("pressure_basis"),
        "platform": investigation.get("platform"),
        "hardware": investigation.get("hardware"),
    }
