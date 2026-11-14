"""Write two-sentence explanations of each investigation's rank for each habitat (task S4).

The model only turns already-computed facts into prose. Every reply is validated against those facts,
repaired once with feedback, and replaced by a deterministic template if it still fails.

Usage:
    python -m si.rationale [--scenario lunar_base] [--only PSI-69] [--model openai/gpt-oss-120b] [--strict]
"""

import hashlib
import json
import re
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


PROMPT_VERSION = "s4-v1"
SYSTEM_PROMPT = """You explain a fire-safety ranking to an aerospace engineer.
Write exactly two plain sentences, at most 60 words in total.
Sentence 1: why this investigation ranks where it does for this habitat, naming its strongest factor.
Sentence 2: its main limitation or caveat for this habitat.
Rules:
- Use only the FACTS. Do not add knowledge from outside them.
- Every number you write must appear in the FACTS. Prefer words over numbers when unsure.
- If n_in_target is 0, never say its tests were inside or within the habitat's target.
- No hype, no lists, no dashes, no semicolons.
Reply with JSON only: {"rationale": "<two sentences>"}"""


def build_facts(entry, scenario, total, summary_record):
    best = (entry.get("evidence") or {}).get("best") or {}
    components = {k: round(float(v), 2) for k, v in (entry.get("components") or {}).items()}
    summary = (summary_record or {}).get("summary") or ""
    return {
        "investigation": entry.get("acronym") or entry["accession"],
        "title": entry.get("title"),
        "habitat": scenario.get("label"),
        "habitat_oxygen_percent": [round(v * 100) for v in scenario.get("o2_mole_fraction") or []],
        "habitat_pressure_kpa": scenario.get("pressure_kpa"),
        "rank": entry["rank"],
        "out_of": total,
        "score_out_of_100": round(float(entry["score"]) * 100),
        "score_parts_0_to_1": components,
        "pillars": entry.get("pillars") or [],
        "n_considered": (entry.get("evidence") or {}).get("n_considered", 0),
        "n_in_target": (entry.get("evidence") or {}).get("n_in_target", 0),
        "n_near": (entry.get("evidence") or {}).get("n_near", 0),
        "closest_test_oxygen_percent": round(best["o2_mole_fraction"] * 100, 1) if best.get("o2_mole_fraction") is not None else None,
        "closest_test_pressure_kpa": round(best["pressure_kpa"]) if best.get("pressure_kpa") is not None else None,
        "computed_reasons": entry.get("reasons") or [],
        "summary": summary[:400],
    }


def build_prompt(facts):
    return "FACTS:\n" + json.dumps(facts, ensure_ascii=False, indent=1)


MAX_WORDS = 70
NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")
INSIDE_CLAIM = re.compile(r"\b(inside|within|in)\s+(the\s+)?(lunar|habitat|target|box|its|this)?\s*(target|box|habitat'?s? (range|conditions|target))", re.I)
RANK_CLAIM = re.compile(r"(?:\branks?\s+(?:#|number\s+)?|#|\bno\.\s*)(\d+)|\b(\d+)(?:st|nd|rd|th)\b", re.I)


def sanitize(text):
    text = " ".join(str(text or "").split())
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = re.sub(r"(?<=\w)\s+-\s+(?=\w)", ", ", text)
    text = text.replace(";", ",")
    return text.strip()


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def allowed_numbers(facts):
    values = set()
    for token in NUMBER.findall(json.dumps(facts, ensure_ascii=False)):
        value = float(token)
        values.update({value, round(value), value * 100, round(value * 100), value / 100})
    return values


def number_is_allowed(token, allowed):
    value = float(token)
    return any(abs(value - a) <= 0.05 + 1e-9 for a in allowed)


def validate(text, facts):
    """Return a list of problems; an empty list means the rationale is safe to publish."""
    problems = []
    if not text:
        return ["empty rationale"]
    count = len(sentences(text))
    if count != 2:
        problems.append(f"has {count} sentences, needs exactly 2")
    words = len(text.split())
    if words > MAX_WORDS:
        problems.append(f"has {words} words, limit is {MAX_WORDS}")
    allowed = allowed_numbers(facts)
    unknown = sorted({t for t in NUMBER.findall(text) if not number_is_allowed(t, allowed)}, key=float)
    if unknown:
        problems.append(f"mentions numbers not in the facts: {', '.join(unknown)}")
    if not facts.get("n_in_target") and INSIDE_CLAIM.search(text):
        problems.append("claims tests were inside the target, but none were")
    for match in RANK_CLAIM.finditer(text):
        stated = int(match.group(1) or match.group(2))
        if stated != facts.get("rank") and stated != facts.get("out_of"):
            problems.append(f"states rank {stated}, real rank is {facts.get('rank')}")
            break
    return problems


def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def template_rationale(facts):
    """A plain, always-correct fallback built only from the computed facts."""
    reasons = facts.get("computed_reasons") or []
    first = reasons[0] if reasons else "its overall score"
    lead = (f"{facts['investigation']} ranks {ordinal(facts['rank'])} of {facts['out_of']} for the {facts['habitat']} "
            f"with a score of {facts['score_out_of_100']}, mainly because of this: {first}.")
    if facts.get("n_in_target"):
        caveat = f"{facts['n_in_target']} of its {facts['n_considered']} tests ran inside this habitat's target."
    elif facts.get("n_considered"):
        caveat = "None of its tests ran inside this habitat's oxygen and pressure target."
    else:
        caveat = "It has no recorded oxygen and pressure to compare with this habitat."
    return sanitize(f"{lead} {caveat}")


def write_one(llm, facts):
    """Return (text, source, problems). Asks once, repairs once with feedback, then falls back to the template."""
    from si.llm import LLMError

    prompt = build_prompt(facts)
    problems = []
    for attempt in range(2):
        try:
            reply = llm.json(prompt, system=SYSTEM_PROMPT, max_tokens=400)
        except LLMError as error:
            return template_rationale(facts), "template", [f"model error: {error}"[:300]]
        text = sanitize(reply.get("rationale") if isinstance(reply, dict) else "")
        problems = validate(text, facts)
        if not problems:
            return text, "model", []
        prompt = (build_prompt(facts) + "\n\nYour previous answer was rejected for these reasons: " + "; ".join(problems)
                  + ". Write it again following every rule.")
    return template_rationale(facts), "template", problems
