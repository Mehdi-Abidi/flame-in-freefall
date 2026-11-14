"""Write two-sentence explanations of each investigation's rank for each habitat (task S4).

The model only turns already-computed facts into prose. Every reply is validated against those facts,
repaired once with feedback, and replaced by a deterministic template if it still fails.

Usage:
    python -m si.rationale [--scenario lunar_base] [--only PSI-69] [--model openai/gpt-oss-120b] [--strict]
"""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

from si.rank import PROCESSED, RankError, UsageError, read_json, shown, write_json_atomic

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
NEGATION = re.compile(r"\b(no|none|not|never|neither|without)\b", re.I)
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
    if not facts.get("n_in_target"):
        for sentence in sentences(text):
            if INSIDE_CLAIM.search(sentence) and not NEGATION.search(sentence):
                problems.append("claims tests were inside the target, but none were")
                break
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
    reasons = [r for r in facts.get("computed_reasons") or [] if not r.startswith("no O2 or pressure data")]
    basis = reasons[0] if reasons else "its material, fire-safety focus and data"
    lead = (f"{facts['investigation']} ranks {ordinal(facts['rank'])} of {facts['out_of']} for the {facts['habitat']} "
            f"with a score of {facts['score_out_of_100']}, mainly on {basis}.")
    phases = next((r[len("burned "):-len(" fuels")] for r in facts.get("computed_reasons") or [] if r.startswith("burned ") and r.endswith(" fuels")), "")
    if facts.get("n_in_target") and phases and "solid" not in phases:
        caveat = f"Its tests burned {phases} fuels, so they do not show how solid cabin materials behave there."
    elif facts.get("n_in_target"):
        caveat = f"{facts['n_in_target']} of its {facts['n_considered']} tests ran inside this habitat's target."
    elif facts.get("n_near"):
        caveat = (f"{facts['n_near']} of its tests ran near this habitat's conditions, "
                  "but none had both oxygen and pressure measured inside the target.")
    elif facts.get("n_considered"):
        caveat = "None of its tests came near this habitat's oxygen and pressure."
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


def load_existing(path):
    if not Path(path).is_file():
        return {}
    document = read_json(path)
    rationales = document.get("rationales") if isinstance(document, dict) else None
    if not isinstance(rationales, dict):
        raise RationaleError(f"{shown(path)} is not a rationale file. Delete it and rerun.")
    return rationales


def validate_selection(scenarios, scenario_filter, only):
    if scenario_filter and scenario_filter not in scenarios:
        raise UsageError(f"unknown scenario '{scenario_filter}'. Choose one of: {', '.join(scenarios)}")
    known = {e["accession"] for s in scenarios.values() for e in s["ranking"]}
    unknown = sorted({a.upper() for a in only or []} - known)
    if unknown:
        raise UsageError(f"unknown accession(s): {', '.join(unknown)}")


def is_reusable(previous, print_key, model_id, force):
    if force or previous.get("fingerprint") != print_key:
        return False
    if previous.get("source") == "model":
        return True
    return previous.get("source") == "template" and model_id == "template"


def generate(rankings, summaries, writer, existing=None, scenario_filter=None, only=None, model_id="template",
             force=False, on_progress=None, save=None):
    """Fill rationales for every (scenario group, investigation). writer(facts) returns (text, source, problems)."""
    existing = existing or {}
    output = {sid: dict(existing.get(sid) or {}) for sid in rankings}
    wanted = {a.upper() for a in only} if only else None
    stats = {"model": 0, "template": 0, "kept": 0}
    for group in group_scenarios(rankings):
        if scenario_filter and scenario_filter not in group:
            continue
        lead = rankings[group[0]]
        label = " / ".join(rankings[sid]["label"] for sid in group)
        total = len(lead["ranking"])
        for entry in lead["ranking"]:
            accession = entry["accession"]
            if wanted and accession not in wanted:
                continue
            facts = build_facts(entry, {**lead, "label": label}, total, summaries.get(accession))
            print_key = fingerprint({"facts": facts, "prompt": PROMPT_VERSION})
            previous = output[group[0]].get(accession) or {}
            reused = is_reusable(previous, print_key, model_id, force)
            if reused:
                record = previous
                stats["kept"] += 1
            else:
                text, source, problems = writer(facts)
                record = {"text": text, "source": source, "model": model_id if source == "model" else "template",
                          "fingerprint": print_key, "problems": problems}
                stats[source] += 1
            for sid in group:
                output[sid][accession] = {**record, "rank": entry["rank"], "score": entry["score"]}
            if on_progress:
                on_progress(group[0], accession, record, reused)
            if save:
                save(output)
    return output, stats


def document_for(rationales, model_id):
    return {"version": 1, "prompt_version": PROMPT_VERSION, "model": model_id, "rationales": rationales}


def template_writer(facts):
    return template_rationale(facts), "template", []


def run(argv=None):
    parser = argparse.ArgumentParser(prog="python -m si.rationale", description="Write two-sentence rank explanations.")
    parser.add_argument("--scenario", help="only this habitat (its whole box group is written)")
    parser.add_argument("--only", nargs="*", help="only these accessions")
    parser.add_argument("--model", help="override LLM_MODEL")
    parser.add_argument("--templates-only", action="store_true", help="no model calls, write fact-only templates")
    parser.add_argument("--force", action="store_true", help="rewrite even when the facts did not change")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any rationale fell back to a template")
    parser.add_argument("--out", default=str(OUTPUT))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        rankings = load_rankings()
        summaries = load_summaries()
        validate_selection(rankings, args.scenario, args.only)
        existing = load_existing(args.out)
        if args.templates_only:
            model_id, writer = "template", template_writer
        else:
            from si.llm import LLM, LLMError

            try:
                llm = LLM(model=args.model)
            except LLMError as error:
                raise RationaleError(f"cannot start the model client: {error}. Use --templates-only to build without a key.") from error
            model_id = llm.model

            def writer(facts):
                return write_one(llm, facts)

        def progress(scenario_id, accession, record, reused):
            tag = "kept" if reused else record["source"]
            note = f"  ({'; '.join(record['problems'])[:120]})" if record.get("problems") and not reused else ""
            print(f"{tag:8} {scenario_id:18} {accession:8} {record['text'][:80]}{note}")

        def save(output):
            write_json_atomic(args.out, document_for(output, model_id))

        started = time.time()
        output, stats = generate(rankings, summaries, writer, existing, args.scenario, args.only, model_id,
                                 args.force, progress, save)
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
