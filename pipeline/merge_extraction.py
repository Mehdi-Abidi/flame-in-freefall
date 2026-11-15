"""Merge data/processed/extracted.json into data/processed/investigations.json (task D5).

investigations.json (task D3) already holds the fields computed from tests.csv:
accession, ranges, basis, counts, metadata. extracted.json (task S2) holds what the
LLM read out of each investigation's free text: summary, variables_varied,
variables_fixed, sensors, and a suggested set of pillars.

This script copies those LLM fields across, keyed by accession, so investigations.json
becomes the one file the frontend and API both read (the plan's own "done when" for D5).

Pillars are the one field that is NOT a straight copy. The plan says hand-checked tags
(task T1, data/domain/tags.json) beat the model's guess, which is only a fallback. That
same three-way priority (tags, then the seed tags reviewers are checking, then the model)
is already implemented once in si.rank.resolve_pillars, because si/rank.py has to make the
exact same decision when it scores investigations for each habitat. This script reuses that
function instead of re-implementing the same rule a second time, so investigations.json's
pillars field can never silently disagree with what the ranking engine used to score it.

Usage: python pipeline/merge_extraction.py [--processed data/processed] [--domain data/domain]
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from si.rank import resolve_pillars

DIRECT_FIELDS = ("summary", "variables_varied", "variables_fixed", "sensors")


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def index_by_accession(records):
    return {r["accession"]: r for r in records}


def load_pillar_source(path):
    """tags.json and seed_pillars.json can be a bare list or {"investigations": [...]}.

    Missing file -> empty dict, same as si.rank.load_inputs treats an optional source,
    so resolve_pillars falls through to the next source exactly as it does when ranking.
    """
    if not os.path.isfile(path):
        return {}
    document = load_json(path)
    records = document.get("investigations") if isinstance(document, dict) else document
    return index_by_accession(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed", default="data/processed")
    parser.add_argument("--domain", default="data/domain")
    args = parser.parse_args()

    investigations_path = os.path.join(args.processed, "investigations.json")
    extracted_path = os.path.join(args.processed, "extracted.json")

    investigations = load_json(investigations_path)
    extracted_by_accession = index_by_accession(load_json(extracted_path))
    tags_by_accession = load_pillar_source(os.path.join(args.domain, "tags.json"))
    seed_by_accession = load_pillar_source(os.path.join(args.domain, "seed_pillars.json"))

    missing_extraction = []
    pillar_sources = {"tags": 0, "seed": 0, "model": 0, "none": 0}

    for inv in investigations:
        accession = inv["accession"]
        extracted = extracted_by_accession.get(accession)
        if extracted is None:
            missing_extraction.append(accession)
            continue

        for field in DIRECT_FIELDS:
            inv[field] = extracted.get(field)

        pillars, source = resolve_pillars(accession, tags_by_accession, seed_by_accession, extracted_by_accession)
        inv["pillars"] = pillars
        pillar_sources[source] += 1

    if missing_extraction:
        print(f"WARNING: no extracted.json record for {', '.join(missing_extraction)}; "
              f"those investigations were left as they were (pillars/summary/etc. still null).")

    with open(investigations_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(investigations, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"Merged extracted.json into {investigations_path} for {len(investigations) - len(missing_extraction)} "
          f"of {len(investigations)} investigations.")
    print(f"Pillar source used: tags={pillar_sources['tags']}, seed={pillar_sources['seed']}, "
          f"model={pillar_sources['model']}, none={pillar_sources['none']}")
    if not os.path.isfile(os.path.join(args.domain, "tags.json")):
        print("data/domain/tags.json does not exist yet (task T1) -- pillars came from seed_pillars.json "
              "or the model's own guess. Re-run this script once Taha adds tags.json, to upgrade pillars "
              "without needing anything else to change.")


if __name__ == "__main__":
    main()
