"""Write one cited insight brief per fire-safety pillar: prevention, detection, suppression (task S5).

The model only turns computed facts into prose. Every brief is validated, repaired with feedback,
and replaced by a fact-only brief if it still fails. Briefs await expert review (task T4).

Usage:
    python -m si.briefs [--pillar suppression] [--model openai/gpt-oss-120b] [--templates-only] [--force] [--strict]
"""

import collections
import csv
import json
import re
from pathlib import Path

from si.rank import PROCESSED, RankError, UsageError, read_json, shown
from si.rationale import FIELD_NAME, NUMBER, NUMBER_WORDS, allowed_numbers, number_is_allowed, sanitize

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


PROMPT_VERSION = "s5-v1"
SYSTEM_PROMPT = """You write a short insight brief for spacecraft and lunar habitat fire-safety engineers.
Use only the FACTS. Never add knowledge from outside them.
Reply with JSON only, with exactly these keys:
title: at most 10 words, plain, no colon
findings: a list of exactly 3 objects, each {"text": one or two sentences of at most 45 words, "citations": list of accession numbers such as "PSI-69"}
implication: one sentence of at most 40 words on what this means for a lunar base designer
gap: one sentence of at most 40 words on what the data does not cover
Rules:
- Each finding must be supported by the investigations it cites, and cite only accessions listed in the FACTS.
- Write every number as digits, and only numbers that appear in the FACTS.
- Never write FACT key names or words joined by underscores.
- Do not call anything best, most effective, safest, optimal or ideal. Report what was observed.
- If oxygen or pressure is assumed or planned, say so rather than presenting it as measured.
- No hype, no dashes, no semicolons."""


def build_prompt(facts):
    return "FACTS:\n" + json.dumps(facts, ensure_ascii=False, indent=1)


SUPERLATIVE = re.compile(r"\b(best|most effective|safest|optimal|ideal|superior|clearly better)\b", re.I)
CITATION = re.compile(r"PSI-\d+")


def _text_problems(label, text, facts, max_words, allowed_numbers_set):
    problems = []
    if not text:
        return [f"{label} is empty"]
    words = len(text.split())
    if words > max_words:
        problems.append(f"{label} has {words} words, limit is {max_words}")
    without_citations = CITATION.sub("", text)
    unknown = sorted({t for t in NUMBER.findall(without_citations) if not number_is_allowed(t, allowed_numbers_set)}, key=float)
    if unknown:
        problems.append(f"{label} mentions numbers not in the facts: {', '.join(unknown)}")
    spelled = sorted({m.group(0).lower() for m in NUMBER_WORDS.finditer(text)})
    if spelled:
        problems.append(f"{label} spells out numbers ({', '.join(spelled)}), write digits")
    fields = sorted({m.group(0) for m in FIELD_NAME.finditer(text)})
    if fields:
        problems.append(f"{label} uses internal field names ({', '.join(fields)})")
    if SUPERLATIVE.search(text):
        problems.append(f"{label} makes a superlative claim ({SUPERLATIVE.search(text).group(0)}) the data does not state")
    return problems


def clean_brief(raw):
    raw = raw if isinstance(raw, dict) else {}
    findings = []
    for item in raw.get("findings") or []:
        if isinstance(item, dict):
            text = sanitize(item.get("text"))
            cited = item.get("citations") if isinstance(item.get("citations"), list) else []
            cited = [c for c in dict.fromkeys(str(c).strip().upper() for c in cited) if c]
            cited += [c for c in CITATION.findall(text) if c not in cited]
            findings.append({"text": text, "citations": cited})
    return {
        "title": sanitize(raw.get("title")).rstrip("."),
        "findings": findings,
        "implication": sanitize(raw.get("implication")),
        "gap": sanitize(raw.get("gap")),
    }


def validate_brief(brief, facts):
    """Return a list of problems; an empty list means the brief is safe to publish."""
    allowed_accessions = {inv["accession"] for inv in facts["investigations"]}
    allowed = allowed_numbers(facts)
    problems = []
    title = brief.get("title") or ""
    if not title:
        problems.append("title is empty")
    elif len(title.split()) > 10:
        problems.append(f"title has {len(title.split())} words, limit is 10")
    findings = brief.get("findings") or []
    if len(findings) != 3:
        problems.append(f"has {len(findings)} findings, needs exactly 3")
    for index, finding in enumerate(findings, start=1):
        label = f"finding {index}"
        problems += _text_problems(label, finding.get("text"), facts, 45, allowed)
        cited = finding.get("citations") or []
        if not cited:
            problems.append(f"{label} cites nothing")
        outside = [c for c in cited if c not in allowed_accessions]
        if outside:
            problems.append(f"{label} cites {', '.join(outside)}, which is not in this pillar")
    for key in ("implication", "gap"):
        problems += _text_problems(key, brief.get(key), facts, 40, allowed)
    return problems


BASIS_SHORT = {
    "measured": "measured",
    "planned": "planned",
    "approximate": "approximate",
    "test_day_list": "listed per test day",
    "nominal_cabin_air": "assumed cabin air",
}
MAX_ATTEMPTS = 3


def _range_text(values):
    if not values:
        return None
    low, high = values
    return f"{low:g}%" if low == high else f"{low:g}% to {high:g}%"


def template_brief(facts):
    """A plain, always-valid fallback built only from the computed facts."""
    pillar = facts["pillar"]
    candidates = sorted(facts["investigations"], key=lambda inv: (-(inv.get("tests") or 0), inv["lunar_base_rank"]))
    findings = []
    for inv in candidates[:3]:
        parts = [f"{inv['name']} recorded {inv.get('tests') or 'no individual'} tests"]
        if inv.get("fuel_phase"):
            parts.append(f"with {' and '.join(inv['fuel_phase'])} fuels")
        oxygen = _range_text(inv.get("oxygen_percent_range"))
        if oxygen:
            parts.append(f"at {oxygen} oxygen ({BASIS_SHORT.get(inv.get('oxygen_basis'), 'basis not stated')})")
        findings.append({"text": " ".join(parts) + ".", "citations": [inv["accession"]]})
    solid_fact = next((f for f in facts["dataset_facts"] if f.startswith("The highest measured oxygen")), None)
    implication = ("Solid-material tests in PSI stop below the 30% oxygen expected in a lunar base, "
                   f"so {pillar} findings need checking at lunar conditions.") if solid_fact else \
        f"Lunar {pillar} findings need checking at lunar conditions."
    return {
        "title": f"What NASA PSI records show on {pillar}",
        "findings": findings,
        "implication": sanitize(implication),
        "gap": "No partial-gravity combustion data is in PSI yet.",
    }


def write_one(llm, facts):
    """Return (brief, source, problems). Model errors are retried, rejected briefs are retried with the
    exact problems, and after three attempts the fact-only brief is used."""
    from si.llm import LLMError

    prompt = build_prompt(facts)
    problems = []
    for attempt in range(MAX_ATTEMPTS):
        try:
            reply = llm.json(prompt, system=SYSTEM_PROMPT, max_tokens=1500)
        except LLMError as error:
            problems = [f"model error: {error}"[:300]]
            if attempt < MAX_ATTEMPTS - 1:
                continue
            return template_brief(facts), "template", problems
        brief = clean_brief(reply)
        problems = validate_brief(brief, facts)
        if not problems:
            return brief, "model", []
        prompt = (build_prompt(facts) + "\n\nYour previous brief was rejected for these reasons: " + "; ".join(problems)
                  + ". Write it again following every rule.")
    return template_brief(facts), "template", problems
