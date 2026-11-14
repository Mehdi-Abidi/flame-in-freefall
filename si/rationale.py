"""Write two-sentence explanations of each investigation's rank for each habitat (task S4).

The model only turns already-computed facts into prose. Every reply is validated against those facts,
repaired once with feedback, and replaced by a deterministic template if it still fails.

Usage:
    python -m si.rationale [--scenario lunar_base] [--only PSI-69] [--model openai/gpt-oss-120b] [--strict]
"""

import hashlib
import json
from pathlib import Path

from si.rank import PROCESSED, RankError, UsageError, read_json, shown

OUTPUT = PROCESSED / "rationale.json"


class RationaleError(RankError):
    """A data or model problem while writing rationales, with a message for the person running it."""


def load_rankings(path=PROCESSED / "rankings.json"):
    document = read_json(path)
    scenarios = document.get("scenarios") if isinstance(document, dict) else None
    if not isinstance(scenarios, dict) or not scenarios:
        raise RationaleError(f"{shown(path)} has no scenarios. Rebuild it with: python -m si.rank --write")
    for scenario_id, scenario in scenarios.items():
        ranking = scenario.get("ranking") if isinstance(scenario, dict) else None
        if not isinstance(ranking, list) or not ranking:
            raise RationaleError(f"{shown(path)}: scenario '{scenario_id}' has no ranking. Rebuild it with: python -m si.rank --write")
        for entry in ranking:
            missing = {"accession", "rank", "score", "components", "reasons", "evidence"} - set(entry)
            if missing:
                raise RationaleError(f"{shown(path)}: an entry in '{scenario_id}' is missing {sorted(missing)}")
    return scenarios


def load_summaries(path=PROCESSED / "extracted.json"):
    if not Path(path).is_file():
        return {}
    records = read_json(path)
    if not isinstance(records, list):
        raise RationaleError(f"{shown(path)} must be a list of records")
    return {r["accession"]: r for r in records if isinstance(r, dict) and r.get("accession")}


def group_scenarios(scenarios):
    """Scenarios with the same target box share one ranking, so they share one rationale."""
    groups = {}
    for scenario_id, scenario in scenarios.items():
        key = json.dumps([scenario.get("o2_mole_fraction"), scenario.get("pressure_kpa")])
        groups.setdefault(key, []).append(scenario_id)
    return list(groups.values())


def fingerprint(facts):
    return hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
