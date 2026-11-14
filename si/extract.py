"""Extract structured fire-safety facts for every PSI combustion investigation (task S2).

Usage: python -m si.extract [--only PSI-69 PSI-25] [--model openai/gpt-oss-20b]
Writes data/processed/extracted.json.
"""

import argparse
import collections
import csv
import json
import re
import sys
import time
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


PROMPT_VERSION = "s2-v3"
PILLARS = ("prevention", "detection", "suppression")
PHASES = ("solid", "liquid", "gas", "dust")
LIST_FIELDS = ("fuels", "sample_geometry", "variables_varied", "variables_fixed", "sensors", "measurements", "earth_benefits")
TEXT_FIELDS = ("summary", "objective_short", "sample_size", "pillar_reason")

SYSTEM_PROMPT = """You turn NASA microgravity combustion investigation records into structured facts for a spacecraft fire safety dashboard.
Rules:
- Use only the TEXT and DATA FACTS given. Never add knowledge from outside them.
- DATA FACTS come from the experiment tables and are correct. Prefer them over the text when they disagree.
- If something is not stated, use null for strings and [] for lists.
- Keep list items short (1 to 6 words), lowercase except chemical formulas and acronyms.
- Write plain words such as "oxygen concentration", never DATA FACTS key names such as o2_range.
Fire safety pillars. Assign a pillar only when it is a main aim of the investigation. Most have one or two.
- prevention: flammability, ignition, flame spread, material selection, oxygen or pressure limits, including flames or cool flames at high oxygen
- detection: measuring smoke, soot or aerosol particles to design or test fire detectors, or telling smoke from dust. Observing that a flame went out is NOT detection.
- suppression: extinguishing flames, diluents or agents such as CO2 or helium, extinction limits
variables_fixed lists physical test conditions held constant (for example ambient temperature or droplet size). Never list the platform, hardware or facility there.
sample_size is a short description of sample size from the TEXT, or null.
Reply with one JSON object with exactly these keys:
summary: 2 to 3 plain sentences for an engineer new to the topic
objective_short: one sentence
fuels: list of fuels or materials burned
fuel_phase: list from solid, liquid, gas, dust
sample_geometry: list, e.g. droplet, flat sheet, rod, spherical burner, coflow burner
sample_size: string or null
variables_varied: list of conditions changed between tests
variables_fixed: list of conditions held constant
sensors: list of instruments
measurements: list of quantities measured
pillars: list from prevention, detection, suppression
pillar_reason: one sentence saying why those pillars apply
earth_benefits: list of practical uses on Earth stated in the text"""


def build_prompt(context, facts):
    return ("TEXT:\n" + json.dumps(context, ensure_ascii=False, indent=1)
            + "\n\nDATA FACTS:\n" + json.dumps(facts, ensure_ascii=False, indent=1))


def clean_text(value, limit=900):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:limit] if value and value.lower() not in {"null", "none", "n/a", "unknown"} else None


def clean_list(value, limit=12):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    seen, out = set(), []
    for item in value:
        text = clean_text(item, 120) if isinstance(item, str) else None
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out[:limit]


def clean_record(raw, facts):
    """Coerce a model reply into the extracted.json schema. Data-proven values override the model."""
    raw = raw if isinstance(raw, dict) else {}
    record = {field: clean_text(raw.get(field)) for field in TEXT_FIELDS}
    record.update({field: clean_list(raw.get(field)) for field in LIST_FIELDS})
    record["pillars"] = [p for p in PILLARS if p in {x.lower() for x in clean_list(raw.get("pillars"))}]
    model_phases = [p for p in PHASES if p in {x.lower() for x in clean_list(raw.get("fuel_phase"))}]
    record["fuel_phase"] = list(facts.get("fuel_phase") or []) or model_phases
    size = facts.get("size_mm_range")
    if size:
        record["sample_size"] = f"{size[0]:g} mm" if size[0] == size[1] else f"{size[0]:g} to {size[1]:g} mm"
    return record


STOPWORDS = {"the", "and", "with", "for", "fuel", "fuels", "sample", "samples", "pure", "mixture", "based", "flame", "flames", "gas", "gases"}


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3 and w not in STOPWORDS}


def is_grounded(item, haystack_words):
    item_words = words(item)
    return not item_words or bool(item_words & haystack_words)


DETECTION_TERMS = ("smoke", "aerosol", "particle", "particulate", "detector", "detection", "dust")


def enforce_detection_evidence(record, context):
    """Drop a detection pillar the source text gives no evidence for, and say so."""
    text = json.dumps(context, ensure_ascii=False).lower()
    if "detection" in record["pillars"] and not any(term in text for term in DETECTION_TERMS):
        record["pillars"] = [p for p in record["pillars"] if p != "detection"]
        return ["detection pillar removed: no smoke, aerosol, particle, dust or detector terms in source"]
    return []


def grounding_warnings(record, context, facts):
    """Flag anything the model named that does not appear in the text or data it was given."""
    haystack = words(json.dumps(context, ensure_ascii=False) + " " + json.dumps(facts, ensure_ascii=False))
    warnings = []
    for field in ("fuels", "sensors"):
        missing = [item for item in record[field] if not is_grounded(item, haystack)]
        if missing:
            warnings.append(f"{field} not found in source: {', '.join(missing)}")
    if not record["pillars"]:
        warnings.append("no fire-safety pillar assigned")
    if not record["summary"]:
        warnings.append("no summary")
    return warnings


TEXT_LIMITS = {"objective": 1600, "approach": 2000, "hypothesis": 900, "researchImpacts": 900}


def load_metadata(accession, raw_dir=RAW):
    with open(Path(raw_dir) / "investigations" / f"{accession}.json", encoding="utf-8") as handle:
        return json.load(handle)


def load_keywords(raw_dir=RAW):
    with open(Path(raw_dir) / "catalog.json", encoding="utf-8") as handle:
        return {entry["Accession"]: " ".join((entry.get("Keywords") or "").split()) for entry in json.load(handle)}


def load_sub_areas(raw_dir=RAW):
    with open(Path(raw_dir) / "catalog.json", encoding="utf-8") as handle:
        return {entry["Accession"]: " ".join((entry.get("SubResearch Area") or "").split()) for entry in json.load(handle)}


def clip(text, limit):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def text_context(metadata, keywords="", max_publications=6, sub_area=""):
    """The NASA write-up for one investigation, trimmed so one request stays under free-tier limits."""
    sections = {name: clip(metadata.get(name), limit) for name, limit in TEXT_LIMITS.items()}
    titles = [clip(p.get("title"), 160) for p in metadata.get("publications") or [] if p.get("title")]
    return {
        "title": clip(metadata.get("title"), 200),
        "keywords": clip(keywords, 300),
        "sub_research_area": clip(sub_area, 120),
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


def extract_one(llm, investigation, rows, metadata, keywords="", sub_area=""):
    context = text_context(metadata, keywords, sub_area=sub_area)
    facts = data_facts(investigation, rows)
    raw = llm.json(build_prompt(context, facts), system=SYSTEM_PROMPT, max_tokens=2500)
    record = clean_record(raw, facts)
    guard_warnings = enforce_detection_evidence(record, context)
    return {
        "accession": investigation["accession"],
        "acronym": investigation.get("acronym"),
        **record,
        "warnings": guard_warnings + grounding_warnings(record, context, facts),
        "model": llm.last_model,
        "prompt_version": PROMPT_VERSION,
    }


def accession_number(accession):
    return int(accession.split("-")[1])


def load_existing(path):
    path = Path(path)
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        return {}
    try:
        return {record["accession"]: record for record in json.loads(path.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, TypeError, KeyError) as error:
        raise SystemExit(f"{path} is not a valid extraction file ({error}). Fix or delete it, then rerun.")


def write_records(path, records):
    ordered = sorted(records.values(), key=lambda r: accession_number(r["accession"]))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(ordered, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main():
    from si.llm import LLM, LLMError

    parser = argparse.ArgumentParser(description="Extract structured facts for PSI combustion investigations.")
    parser.add_argument("--only", nargs="*", help="accessions to (re)extract, default all")
    parser.add_argument("--model", help="override LLM_MODEL")
    parser.add_argument("--out", default=str(PROCESSED / "extracted.json"))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    llm = LLM(model=args.model)
    investigations = load_investigations()
    tests = load_tests()
    keywords = load_keywords()
    sub_areas = load_sub_areas()
    records = load_existing(args.out)
    targets = sorted(args.only or investigations, key=accession_number)
    failures = []
    started = time.time()
    for accession in targets:
        try:
            record = extract_one(llm, investigations[accession], tests.get(accession, []),
                                 load_metadata(accession), keywords.get(accession, ""), sub_areas.get(accession, ""))
        except (LLMError, KeyError) as error:
            failures.append(accession)
            print(f"FAIL {accession}: {error}")
            continue
        records[accession] = record
        flag = f"  warnings: {record['warnings']}" if record["warnings"] else ""
        print(f"ok   {accession:8} {record['acronym'] or '-':20} pillars={','.join(record['pillars']) or '-'}{flag}")
        write_records(args.out, records)
    print(f"\n{len(targets) - len(failures)}/{len(targets)} extracted in {time.time() - started:.0f}s, "
          f"model calls {llm.usage['calls']}, cached {llm.usage['cached']}, tokens {llm.usage['tokens']}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
