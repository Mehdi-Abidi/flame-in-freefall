"""Write one cited insight brief per fire-safety pillar: prevention, detection, suppression (task S5).

The model only turns computed facts into prose. Every brief is validated, repaired with feedback,
and replaced by a fact-only brief if it still fails. Briefs await expert review (task T4).

Usage:
    python -m si.briefs [--pillar suppression] [--model openai/gpt-oss-120b] [--templates-only] [--force] [--strict]
"""

import collections
import csv
import json
from pathlib import Path

from si.rank import PROCESSED, RankError, UsageError, read_json, shown

OUTPUT = PROCESSED / "briefs.json"
PILLARS = ("prevention", "detection", "suppression")
PILLAR_MEANING = {
    "prevention": "keeping fires from starting or spreading: flammability, ignition, flame spread, oxygen and pressure limits",
    "detection": "noticing a fire early: smoke, soot and aerosol measurement, detectors, telling smoke from dust",
    "suppression": "putting fires out: extinction limits, diluents and agents such as carbon dioxide or helium",
}
MAX_GROUPS = 4
OUTCOME_PHRASE = {
    "extinction": "ended in extinction",
    "disruption": "ended in droplet disruption",
    "burned to completion": "burned completely",
    "self-extinguished": "self-extinguished",
    "flow terminated": "were stopped by ending the flow",
    "no ignition": "did not ignite",
    "ignited": "ignited",
}


class BriefError(RankError):
    """A data or model problem while writing briefs, with a message for the person running it."""


def pct(fraction):
    return round(fraction * 100, 1)


def load_tests(path=PROCESSED / "tests.csv"):
    if not Path(path).is_file():
        raise BriefError(f"{shown(path)} not found. Create it with: python pipeline/normalize.py")
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_accession = collections.defaultdict(list)
    for row in rows:
        by_accession[row.get("accession", "")].append(row)
    return rows, by_accession


def number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def pillar_members(rankings):
    """Investigations per pillar, taken from the lunar-base ranking (pillars are the same in every habitat)."""
    scenario = rankings.get("lunar_base") or next(iter(rankings.values()))
    members = {pillar: [] for pillar in PILLARS}
    for entry in scenario["ranking"]:
        for pillar in entry.get("pillars") or []:
            if pillar in members:
                members[pillar].append(entry)
    return members


def group_observations(rows):
    """Plain sentences per fuel phase and diluent: measured oxygen range and outcomes."""
    groups = collections.defaultdict(list)
    for row in rows:
        if row.get("record_type") in ("test", "condition_matrix", "test_day_condition"):
            groups[(row.get("fuel_phase") or "unknown", row.get("diluent") or "diluent not recorded")].append(row)
    lines = []
    for (phase, diluent), group in sorted(groups.items(), key=lambda item: -len(item[1]))[:MAX_GROUPS]:
        measured = [number(r["o2_mole_fraction"]) for r in group if r.get("o2_source") == "measured" and number(r.get("o2_mole_fraction")) is not None]
        line = f"{len(group)} {phase}-fuel rows with {diluent}"
        if measured:
            line += f", measured oxygen {pct(min(measured))}% to {pct(max(measured))}%"
        outcomes = collections.Counter(r["outcome"] for r in group if r.get("outcome"))
        for outcome, count in outcomes.most_common(2):
            o2 = [number(r["o2_mole_fraction"]) for r in group if r.get("outcome") == outcome and number(r.get("o2_mole_fraction")) is not None]
            phrase = OUTCOME_PHRASE.get(outcome, f"ended as {outcome}")
            line += f", {count} {phrase}" + (f", the lowest at {pct(min(o2))}% oxygen" if o2 else "")
        lines.append(line)
    return lines


def gravity_observations(path=PROCESSED / "saffire2_gravity.csv"):
    if not Path(path).is_file():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    lines = []
    for row in rows:
        lines.append(f"SAFFIRE-II sample {row.get('sample')} ({row.get('material')}): microgravity burn length "
                     f"{row.get('micro_g_burn_length') or 'not given'}, 1 g burn length {row.get('one_g_burn_length') or 'not given'}")
    return lines


def dataset_facts(all_rows):
    solid = [number(r["o2_mole_fraction"]) for r in all_rows
             if r.get("fuel_phase") == "solid" and r.get("o2_source") == "measured" and number(r.get("o2_mole_fraction")) is not None]
    lunar = [r for r in all_rows if r.get("record_type") == "test" and r.get("o2_source") == "measured"
             and (number(r.get("o2_mole_fraction")) or 0) >= 0.30 and number(r.get("pressure_kpa")) is not None
             and number(r.get("pressure_kpa")) <= 70.3]
    phases = sorted({r.get("fuel_phase") for r in lunar})
    facts = []
    if solid:
        facts.append(f"The highest measured oxygen in any solid-material test is {pct(max(solid))}% across {len(solid)} solid tests.")
    facts.append(f"{len(lunar)} individual tests ran at lunar-base conditions (30% oxygen or more at 70.3 kPa or less), "
                 f"all with {' and '.join(phases) or 'no'} fuels.")
    facts.append("A lunar base is expected to run at 30% oxygen or more and 70.3 kPa (10.2 psi) or less.")
    facts.append("No partial-gravity combustion data is in PSI yet. Microgravity and 1 g results bound what may happen on the Moon or Mars.")
    return facts


def build_facts(pillar, members, investigations, extracted, rows_by_accession, all_rows):
    entries = []
    for entry in sorted(members, key=lambda e: e["rank"]):
        accession = entry["accession"]
        inv = investigations.get(accession) or {}
        ex = extracted.get(accession) or {}
        best = (entry.get("evidence") or {}).get("best") or {}
        o2_range = inv.get("o2_range")
        kpa_range = inv.get("pressure_kpa_range")
        entries.append({
            "accession": accession,
            "name": entry.get("acronym") or accession,
            "summary": (ex.get("summary") or "")[:320],
            "fuels": (ex.get("fuels") or [])[:5],
            "fuel_phase": inv.get("fuel_phase") or [],
            "varied": ex.get("variables_varied") or [],
            "oxygen_percent_range": [pct(v) for v in o2_range] if o2_range else None,
            "oxygen_basis": inv.get("o2_basis"),
            "pressure_kpa_range": [round(v) for v in kpa_range] if kpa_range else None,
            "pressure_basis": inv.get("pressure_basis"),
            "tests": inv.get("n_tests", 0),
            "lunar_base_rank": entry["rank"],
            "closest_lunar_test": (f"{pct(best['o2_mole_fraction'])}% oxygen at {round(best['pressure_kpa'])} kPa"
                                   if best.get("o2_mole_fraction") is not None and best.get("pressure_kpa") is not None else None),
            "observations": group_observations(rows_by_accession.get(accession, [])),
        })
    facts = {
        "pillar": pillar,
        "pillar_meaning": PILLAR_MEANING[pillar],
        "dataset_facts": dataset_facts(all_rows),
        "investigations": entries,
    }
    if pillar == "prevention":
        facts["gravity_observations"] = gravity_observations()
    return facts
