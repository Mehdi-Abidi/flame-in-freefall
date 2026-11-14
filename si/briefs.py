"""Write one cited insight brief per fire-safety pillar: prevention, detection, suppression (task S5).

The model only turns computed facts into prose. Every brief is validated, repaired with feedback,
and replaced by a fact-only brief if it still fails. Briefs await expert review (task T4).

Usage:
    python -m si.briefs [--pillar suppression] [--model openai/gpt-oss-120b] [--templates-only] [--force] [--strict]
"""

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from si.rank import PROCESSED, RankError, UsageError, read_json, shown, write_json_atomic
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
    facts.append("Challenge context: raising oxygen to 30% or more makes materials much more flammable than in Earth air.")
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


PROMPT_VERSION = "s5-v3"
SYSTEM_PROMPT = """You write a short insight brief for spacecraft and lunar habitat fire-safety engineers.
Use only the FACTS. Never add knowledge from outside them.
Reply with JSON only, with exactly these keys:
title: at most 10 words, plain, no colon
findings: a list of exactly 3 objects, each {"text": one or two sentences of at most 45 words, "citations": list of accession numbers such as "PSI-69"}
implication: one sentence of at most 40 words on what this means for a lunar base designer
gap: one sentence of at most 40 words on what the data does not cover
Example of a valid finding:
{"text": "BASS-II burned PMMA and Nomex samples with measured oxygen from 13.6% to 22.2%, all below lunar base levels.", "citations": ["PSI-25"]}
Rules:
- Start each finding with the name of the one investigation it cites, exactly as written in the FACTS, and cite only that accession.
- Each finding is about specific investigations, names every investigation it cites, and cites only accessions listed in the FACTS.
  Dataset-wide facts belong in implication or gap, never in a finding.
- Only say flames went out, were extinguished or self-extinguished when that investigation's observations record it.
- A flame going out at low oxygen does not show that the same agent works at 30% oxygen, where fires are harder to stop.
  Never suggest that results at lower oxygen make a lunar base safe. The implication says what must be tested or designed for.
- Write every number as digits, and only numbers that appear in the FACTS.
- Never write FACT key names or words joined by underscores.
- Do not call anything best, most effective, safest, optimal or ideal. Report what was observed.
- If an investigation's oxygen_basis is not measured, write assumed or planned next to its oxygen values.
- Avoid overconfident language such as can rely on, is effective, can work, is sufficient or safe enough.
- Write the implication with must test or must design for, never as reassurance.
- No hype, no dashes, no semicolons."""


def build_prompt(facts):
    return "FACTS:\n" + json.dumps(facts, ensure_ascii=False, indent=1)


OUTCOME_CLAIM = re.compile(r"\b(extinction|extinguish\w*|went out|put out|self-extinguish\w*)\b", re.I)
OVERCONFIDENT = re.compile(r"\b(can rely on|rely on|will be effective|is effective|are effective|can work|works well|is sufficient|are sufficient|safe enough|guarantee\w*)\b", re.I)
QUALIFIER = re.compile(r"\b(assum\w*|planned|approximate\w*|nominal)\b", re.I)
UNMEASURED = {"nominal_cabin_air", "planned", "approximate", "test_day_list"}
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
QUALIFIER_BEFORE = 35
QUALIFIER_AFTER = 15


def _percent_tokens(values):
    tokens = set()
    for value in values or []:
        tokens.update({f"{value:g}", f"{value:.1f}", f"{round(value)}"})
    return tokens


def _evidence_problems(label, finding, by_accession):
    problems = []
    text = finding.get("text") or ""
    lowered = text.lower()
    cited = [by_accession[c] for c in finding.get("citations") or [] if c in by_accession]
    unnamed = [inv["name"] for inv in cited if inv["name"].lower() not in lowered]
    if unnamed:
        problems.append(f"{label} cites {', '.join(unnamed)} but does not name it, so the citation may not support the claim")
    if OUTCOME_CLAIM.search(text):
        recorded = any(("extinction" in obs or "self-extinguished" in obs) for inv in cited for obs in inv.get("observations") or [])
        if cited and not recorded:
            problems.append(f"{label} claims flames went out, but no extinction outcome is recorded for what it cites")
    for inv in cited:
        if inv.get("oxygen_basis") not in UNMEASURED:
            continue
        tokens = _percent_tokens(inv.get("oxygen_percent_range"))
        for match in PERCENT.finditer(text):
            window = text[max(0, match.start() - QUALIFIER_BEFORE):match.end() + QUALIFIER_AFTER]
            if match.group(1) in tokens and not QUALIFIER.search(window):
                problems.append(f"{label} presents {inv['name']}'s assumed or planned oxygen as measured")
                break
    return problems


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
    by_accession = {inv["accession"]: inv for inv in facts["investigations"]}
    for index, finding in enumerate(findings, start=1):
        label = f"finding {index}"
        problems += _text_problems(label, finding.get("text"), facts, 45, allowed)
        problems += _evidence_problems(label, finding, by_accession)
        cited = finding.get("citations") or []
        if not cited:
            problems.append(f"{label} cites nothing")
        outside = [c for c in cited if c not in allowed_accessions]
        if outside:
            problems.append(f"{label} cites {', '.join(outside)}, which is not in this pillar")
    for key in ("implication", "gap"):
        problems += _text_problems(key, brief.get(key), facts, 40, allowed)
    for key, text in [("implication", brief.get("implication") or ""), ("gap", brief.get("gap") or "")] +             [(f"finding {i}", f.get("text") or "") for i, f in enumerate(findings, start=1)]:
        match = OVERCONFIDENT.search(text)
        if match:
            problems.append(f"{key} uses overconfident safety language ({match.group(0)})")
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


PENDING_REVIEW = "awaiting expert review"


def fingerprint(facts):
    payload = json.dumps({"facts": facts, "prompt": PROMPT_VERSION}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_existing(path):
    if not Path(path).is_file():
        return {}
    document = read_json(path)
    briefs = document.get("briefs") if isinstance(document, dict) else None
    if not isinstance(briefs, dict):
        raise BriefError(f"{shown(path)} is not a briefs file. Delete it and rerun.")
    return briefs


def generate(all_facts, writer, existing=None, only=None, model_id="template", force=False, on_progress=None, save=None):
    """all_facts maps pillar to its facts. writer(facts) returns (brief, source, problems)."""
    output = dict(existing or {})
    stats = {"model": 0, "template": 0, "kept": 0}
    for pillar, facts in all_facts.items():
        if only and pillar != only:
            continue
        key = fingerprint(facts)
        previous = output.get(pillar) or {}
        reusable = (not force and previous.get("fingerprint") == key
                    and (previous.get("source") == "model" or model_id == "template"))
        if reusable:
            stats["kept"] += 1
            record = previous
        else:
            brief, source, problems = writer(facts)
            record = {**brief, "source": source, "model": model_id if source == "model" else "template",
                      "members": [inv["accession"] for inv in facts["investigations"]], "fingerprint": key,
                      "problems": problems, "review": PENDING_REVIEW}
            stats[source] += 1
        output[pillar] = record
        if on_progress:
            on_progress(pillar, record, reusable)
        if save:
            save(output)
    return output, stats


def document_for(briefs, model_id):
    return {"version": 1, "prompt_version": PROMPT_VERSION, "model": model_id, "briefs": briefs}


def collect_facts():
    from si.rationale import load_investigations, load_rankings, load_summaries

    rankings = load_rankings()
    all_rows, rows_by_accession = load_tests()
    members = pillar_members(rankings)
    investigations = load_investigations()
    extracted = load_summaries()
    return {pillar: build_facts(pillar, members[pillar], investigations, extracted, rows_by_accession, all_rows)
            for pillar in PILLARS if members[pillar]}


def run(argv=None):
    parser = argparse.ArgumentParser(prog="python -m si.briefs", description="Write cited insight briefs per pillar.")
    parser.add_argument("--pillar", help="only this pillar: prevention, detection or suppression")
    parser.add_argument("--model", help="override LLM_MODEL")
    parser.add_argument("--templates-only", action="store_true", help="no model calls, write fact-only briefs")
    parser.add_argument("--force", action="store_true", help="rewrite even when the facts did not change")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any brief fell back to the template")
    parser.add_argument("--out", default=str(OUTPUT))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        if args.pillar and args.pillar not in PILLARS:
            raise UsageError(f"unknown pillar '{args.pillar}'. Choose one of: {', '.join(PILLARS)}")
        all_facts = collect_facts()
        if not all_facts:
            raise BriefError("no investigation carries a fire-safety pillar. Check data/domain tags and rerun python -m si.rank --write")
        existing = load_existing(args.out)
        if args.templates_only:
            model_id = "template"

            def writer(facts):
                return template_brief(facts), "template", []
        else:
            from si.llm import LLM, LLMError

            try:
                llm = LLM(model=args.model)
            except LLMError as error:
                raise BriefError(f"cannot start the model client: {error}. Use --templates-only to build without a key.") from error
            model_id = llm.model

            def writer(facts):
                return write_one(llm, facts)

        def progress(pillar, record, reused):
            tag = "kept" if reused else record["source"]
            note = f"  ({'; '.join(record['problems'])[:160]})" if record.get("problems") and not reused else ""
            print(f"{tag:8} {pillar:12} {record['title']}{note}")

        def save(output):
            write_json_atomic(args.out, document_for(output, model_id))

        started = time.time()
        output, stats = generate(all_facts, writer, existing, args.pillar, model_id, args.force, progress, save)
        save(output)
        print(f"\nmodel {stats['model']}, template {stats['template']}, kept {stats['kept']} "
              f"in {time.time() - started:.0f}s -> {shown(args.out)}")
        return 1 if args.strict and stats["template"] else 0
    except UsageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except RankError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("stopped, progress so far is saved", file=sys.stderr)
        return 130
    except Exception as error:
        if args.debug:
            raise
        print(f"unexpected error: {type(error).__name__}: {error}. Rerun with --debug for the full traceback.", file=sys.stderr)
        return 1


def main():
    sys.exit(run())


if __name__ == "__main__":
    main()
