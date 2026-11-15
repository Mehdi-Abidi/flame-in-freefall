"""Rank PSI combustion investigations for a habitat scenario (task S3).

Usage:
    python -m si.rank --scenario lunar_base [--weights prevention=2,detection=1,suppression=1] [--top 10]
    python -m si.rank --write
Library:
    from si.rank import load_inputs, rank
    results = rank("lunar_base", {"prevention": 2, "detection": 1, "suppression": 1}, load_inputs())
"""

import argparse
import csv
import math
import os
import sys
import tempfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
DOMAIN = ROOT / "data" / "domain"

PRODUCERS = {
    "investigations.json": "python pipeline/build_investigations.py",
    "tests.csv": "python pipeline/normalize.py",
    "extracted.json": "python -m si.extract",
    "scenarios.json": "restore data/domain/scenarios.json from git",
    "seed_pillars.json": "restore data/domain/seed_pillars.json from git",
}


class RankError(Exception):
    """A problem with ranking inputs or arguments, with a message meant for the person running it."""


class UsageError(RankError):
    """The caller asked for something invalid (unknown scenario, bad weights). An API should answer 400."""


def shown(path):
    """Paths inside the project are shown relative to it, so messages stay short and readable."""
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _missing(path):
    hint = PRODUCERS.get(Path(path).name)
    return RankError(f"{shown(path)} not found." + (f" Create it with: {hint}" if hint else ""))


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise _missing(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RankError(f"{shown(path)} is not valid JSON (line {error.lineno}, column {error.colno}): {error.msg}") from error
    except (OSError, UnicodeDecodeError) as error:
        raise RankError(f"cannot read {shown(path)}: {error}") from error


def read_csv(path, required_columns):
    path = Path(path)
    if not path.is_file():
        raise _missing(path)
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(set(required_columns) - set(reader.fieldnames or []))
            if missing:
                raise RankError(f"{shown(path)} is missing columns {missing}. Regenerate it with: {PRODUCERS.get(path.name, 'its producer')}")
            return list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise RankError(f"cannot read {shown(path)}: {error}") from error


SCENARIO_KEYS = {"id", "label", "o2_mole_fraction", "pressure_kpa", "context_only", "source", "assumptions"}


def _box(scenario_id, name, value, low, high):
    if (not isinstance(value, list) or len(value) != 2
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)):
        raise RankError(f"scenario '{scenario_id}': {name} must be a [min, max] pair of numbers, got {value!r}")
    if value[0] > value[1]:
        raise RankError(f"scenario '{scenario_id}': {name} min {value[0]} is larger than max {value[1]}")
    if value[0] < low or value[1] > high:
        raise RankError(f"scenario '{scenario_id}': {name} {value} is outside the physical range {low} to {high}")
    return [float(value[0]), float(value[1])]


def validate_scenarios(document):
    if not isinstance(document, dict) or not isinstance(document.get("scenarios"), list) or not document["scenarios"]:
        raise RankError("scenarios.json must contain a non-empty 'scenarios' list")
    tolerance = document.get("tolerance") or {}
    o2_tol, p_tol = tolerance.get("o2_mole_fraction"), tolerance.get("pressure_kpa")
    if not all(isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0 for t in (o2_tol, p_tol)):
        raise RankError("scenarios.json tolerance needs positive numbers for o2_mole_fraction and pressure_kpa")
    scenarios = {}
    for index, scenario in enumerate(document["scenarios"]):
        if not isinstance(scenario, dict):
            raise RankError(f"scenario #{index + 1} must be an object")
        missing = sorted(SCENARIO_KEYS - set(scenario))
        scenario_id = scenario.get("id", f"#{index + 1}")
        if missing:
            raise RankError(f"scenario '{scenario_id}' is missing keys {missing}")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise RankError(f"scenario #{index + 1} needs a non-empty text id")
        if scenario_id in scenarios:
            raise RankError(f"scenario id '{scenario_id}' appears twice")
        scenarios[scenario_id] = {
            **scenario,
            "o2_mole_fraction": _box(scenario_id, "o2_mole_fraction", scenario["o2_mole_fraction"], 0.0, 1.0),
            "pressure_kpa": _box(scenario_id, "pressure_kpa", scenario["pressure_kpa"], 0.0, 1000.0),
        }
    return {"tolerance": {"o2": float(o2_tol), "pressure": float(p_tol)}, "scenarios": scenarios}


PILLARS = ("prevention", "detection", "suppression")
DEFAULT_WEIGHTS = {pillar: 1.0 for pillar in PILLARS}


def parse_weights(value=None):
    """Accept None, a dict from the API, or text like 'prevention=2,detection=1,suppression=1'."""
    if value is None or value == "" or value == {}:
        return dict(DEFAULT_WEIGHTS)
    if isinstance(value, str):
        pairs = {}
        for part in value.split(","):
            if not part.strip():
                continue
            if "=" not in part:
                raise UsageError(f"weight '{part.strip()}' must look like pillar=number, e.g. prevention=2")
            name, number = part.split("=", 1)
            pairs[name.strip().lower()] = number.strip()
        value = pairs
    if not isinstance(value, dict):
        raise UsageError(f"weights must be a mapping of pillar to number, got {type(value).__name__}")
    unknown = sorted(set(value) - set(PILLARS))
    if unknown:
        raise UsageError(f"unknown pillar(s) {unknown}. Use {', '.join(PILLARS)}")
    weights = dict(DEFAULT_WEIGHTS)
    for name, number in value.items():
        try:
            number = float(number)
        except (TypeError, ValueError):
            raise UsageError(f"weight for {name} must be a number, got {number!r}") from None
        if number != number or number in (float("inf"), float("-inf")):
            raise UsageError(f"weight for {name} must be a finite number")
        if number < 0:
            raise UsageError(f"weight for {name} cannot be negative")
        weights[name] = number
    if sum(weights.values()) == 0:
        raise UsageError("at least one pillar weight must be above zero")
    return weights


CONDITION_RECORD_TYPES = {"test", "condition_matrix", "test_day_condition", "test_day"}
BASIS_WEIGHT = {
    "measured": 1.0, "approximate": 0.7, "test_day_list": 0.7, "planned": 0.6,
    "nominal_cabin_air": 0.5, "nominal_cabin": 0.5, "nominal_1atm": 0.5,
}
MISSING_PRESSURE_FACTOR = 0.75


def to_number(text):
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def record_unit(kinds):
    if kinds <= {"test"}:
        return "test"
    if kinds <= {"condition_matrix"}:
        return "planned condition"
    if kinds <= {"test_day", "test_day_condition"}:
        return "test day"
    return "record"


def box_distance(value, box, tolerance):
    """0 inside the box, otherwise the gap to the nearest edge measured in tolerances."""
    if value < box[0]:
        return (box[0] - value) / tolerance
    if value > box[1]:
        return (value - box[1]) / tolerance
    return 0.0


def condition_fit(rows, scenario, tolerance):
    """How close an investigation's tested O2 and pressure come to a habitat, from 0 (nowhere near) to 1.
    n_near counts tests whose conditions are close, whatever their evidence. The fit itself is scaled by evidence strength."""
    scored, kinds = [], set()
    for row in rows:
        if row.get("record_type") not in CONDITION_RECORD_TYPES:
            continue
        o2, o2_basis = to_number(row.get("o2_mole_fraction")), row.get("o2_source")
        if o2 is None or o2_basis not in BASIS_WEIGHT:
            continue
        pressure, p_basis = to_number(row.get("pressure_kpa")), row.get("pressure_source")
        o2_gap = box_distance(o2, scenario["o2_mole_fraction"], tolerance["o2"])
        if pressure is not None and p_basis in BASIS_WEIGHT:
            p_gap = box_distance(pressure, scenario["pressure_kpa"], tolerance["pressure"])
            nearness = math.exp(-0.5 * (o2_gap ** 2 + p_gap ** 2))
            closeness = nearness * min(BASIS_WEIGHT[o2_basis], BASIS_WEIGHT[p_basis])
            inside = o2_gap == 0 and p_gap == 0 and o2_basis == "measured" and p_basis == "measured"
        else:
            nearness = math.exp(-0.5 * o2_gap ** 2) * MISSING_PRESSURE_FACTOR
            closeness = nearness * BASIS_WEIGHT[o2_basis]
            inside = False
        scored.append((closeness, inside, o2, pressure, nearness))
        kinds.add(row.get("record_type"))
    if not scored:
        return {"fit": 0.0, "n_considered": 0, "n_in_target": 0, "n_near": 0, "best": None, "unit": "test"}
    best = max(scored, key=lambda item: item[0])
    mean = sum(item[0] for item in scored) / len(scored)
    return {
        "fit": round(0.5 * best[0] + 0.5 * mean, 4),
        "n_considered": len(scored),
        "n_in_target": sum(1 for item in scored if item[1]),
        "n_near": sum(1 for item in scored if item[4] >= 0.6),
        "best": {"o2_mole_fraction": best[2], "pressure_kpa": best[3], "closeness": round(best[0], 4)},
        "unit": record_unit(kinds),
    }


MATERIAL_RELEVANCE = {"solid": 1.0, "liquid": 0.7, "gas": 0.5, "dust": 0.4}


def material_relevance(phases):
    """Habitat fires start in solids, so solid-material tests matter most."""
    return max((MATERIAL_RELEVANCE.get(phase, 0.0) for phase in phases or []), default=0.0)


def pillar_match(pillars, weights):
    """1.0 when the investigation addresses the user's highest-weighted pillar, scaled down for lower priorities.
    Using the best single pillar, not the sum, stops investigations with many tags from outranking focused ones."""
    top = max(weights.values()) if weights else 0.0
    return round(max((weights.get(p, 0.0) for p in pillars), default=0.0) / top, 4) if top else 0.0


def data_richness(investigation, maxima):
    parts = []
    for key, value in (("n_tests", investigation.get("n_tests") or 0),
                       ("n_files", investigation.get("n_files") or 0),
                       ("publications", len(investigation.get("publications") or []))):
        top = maxima.get(key) or 0
        parts.append(math.log1p(value) / math.log1p(top) if top else 0.0)
    return round(sum(parts) / len(parts), 4)


def resolve_pillars(accession, tags, seed, extracted):
    """Hand-checked tags beat seed tags, which beat model suggestions."""
    for source, table in (("tags", tags), ("seed", seed), ("model", extracted)):
        entry = table.get(accession)
        if entry is not None and entry.get("pillars") is not None:
            pillars = [p for p in entry["pillars"] if p in PILLARS]
            if source != "seed" or pillars or entry.get("role"):
                return pillars, source
    return [], "none"


TEST_COLUMNS = ("accession", "record_type", "o2_mole_fraction", "o2_source", "pressure_kpa", "pressure_source")


def _index(records, path):
    if not isinstance(records, list):
        raise RankError(f"{path} must contain a list of records")
    indexed = {}
    for position, record in enumerate(records):
        accession = record.get("accession") if isinstance(record, dict) else None
        if not isinstance(accession, str) or not accession:
            raise RankError(f"{path}: record #{position + 1} has no accession")
        indexed[accession] = record
    return indexed


def load_inputs(processed=PROCESSED, domain=DOMAIN):
    """Read and validate every input. Optional files that are missing become notes, not errors."""
    processed, domain = Path(processed), Path(domain)
    investigations = _index(read_json(processed / "investigations.json"), processed / "investigations.json")
    if not investigations:
        raise RankError(f"{processed / 'investigations.json'} has no investigations")
    rows_by_accession = {}
    for row in read_csv(processed / "tests.csv", TEST_COLUMNS):
        rows_by_accession.setdefault(row["accession"], []).append(row)
    notes = []
    optional = {}
    for name, path in (("extracted", processed / "extracted.json"), ("tags", domain / "tags.json"),
                       ("seed", domain / "seed_pillars.json")):
        if not path.is_file():
            optional[name] = {}
            if name != "tags":
                notes.append(f"{path.name} not found, so pillars fall back to the next source")
            continue
        document = read_json(path)
        records = document.get("investigations") if isinstance(document, dict) else document
        optional[name] = _index(records, path)
    unknown = sorted(set(rows_by_accession) - set(investigations))
    if unknown:
        notes.append(f"tests.csv has rows for accessions missing from investigations.json: {', '.join(unknown)}")
    return {
        "investigations": investigations,
        "rows": rows_by_accession,
        "scenarios": validate_scenarios(read_json(domain / "scenarios.json")),
        "extracted": optional["extracted"],
        "tags": optional["tags"],
        "seed": optional["seed"],
        "notes": notes,
    }


COMPONENT_WEIGHTS = {"condition_fit": 0.35, "material_relevance": 0.20, "pillar_match": 0.25, "data_richness": 0.20}


def get_scenario(scenarios, scenario_id):
    if scenario_id not in scenarios["scenarios"]:
        raise UsageError(f"unknown scenario '{scenario_id}'. Choose one of: {', '.join(scenarios['scenarios'])}")
    return scenarios["scenarios"][scenario_id]


def _percent(fraction):
    return f"{fraction * 100:.0f}% O2"


def reasons_for(investigation, fit, phases, pillars, pillar_source, scenario):
    reasons = []
    if fit["n_in_target"]:
        reasons.append(f"{fit['n_in_target']} measured test(s) inside the {scenario['label']} target")
    best = fit["best"]
    if best and best["closeness"] >= 0.3:
        where = _percent(best["o2_mole_fraction"]) + (f" at {best['pressure_kpa']:.0f} kPa" if best["pressure_kpa"] is not None else "")
        reasons.append(f"closest {fit.get('unit', 'test')}: {where}")
    elif fit["n_considered"]:
        reasons.append(f"none of its {fit['n_considered']} {fit.get('unit', 'test')}s come near this habitat's O2 and pressure")
    else:
        reasons.append("no O2 or pressure data to compare with this habitat")
    if phases:
        reasons.append(f"burned {', '.join(phases)} fuels")
    reasons.append(f"fire-safety focus: {', '.join(pillars) or 'fundamentals only'} (from {'team' if pillar_source == 'tags' else 'seed'} tags)"
                   if pillar_source in ("tags", "seed") else
                   f"fire-safety focus: {', '.join(pillars) or 'not identified'} (model suggestion, not yet checked)")
    if investigation.get("platform") == "ground":
        reasons.append("ground study, no flight tests of its own")
    return reasons


def rank(scenario_id, weights=None, inputs=None):
    """Return every investigation scored for one habitat, best first. Raises RankError on bad input."""
    inputs = inputs if inputs is not None else load_inputs()
    scenario = get_scenario(inputs["scenarios"], scenario_id)
    weights = parse_weights(weights)
    investigations = inputs["investigations"]
    maxima = {
        "n_tests": max((i.get("n_tests") or 0) for i in investigations.values()),
        "n_files": max((i.get("n_files") or 0) for i in investigations.values()),
        "publications": max(len(i.get("publications") or []) for i in investigations.values()),
    }
    results = []
    for accession, investigation in investigations.items():
        fit = condition_fit(inputs["rows"].get(accession, []), scenario, inputs["scenarios"]["tolerance"])
        phases = investigation.get("fuel_phase") or []
        pillars, pillar_source = resolve_pillars(accession, inputs["tags"], inputs["seed"], inputs["extracted"])
        components = {
            "condition_fit": fit["fit"],
            "material_relevance": material_relevance(phases),
            "pillar_match": pillar_match(pillars, weights),
            "data_richness": data_richness(investigation, maxima),
        }
        score = round(sum(COMPONENT_WEIGHTS[name] * value for name, value in components.items()), 4)
        results.append({
            "accession": accession,
            "acronym": investigation.get("acronym"),
            "title": investigation.get("title"),
            "score": score,
            "components": components,
            "pillars": pillars,
            "pillar_source": pillar_source,
            "evidence": {key: fit[key] for key in ("n_considered", "n_in_target", "n_near", "best")},
            "reasons": reasons_for(investigation, fit, phases, pillars, pillar_source, scenario),
        })
    results.sort(key=lambda r: (-r["score"], int(r["accession"].split("-")[1]) if r["accession"].split("-")[-1].isdigit() else 0))
    for position, result in enumerate(results, start=1):
        result["rank"] = position
    return results


def build_rankings(inputs):
    """Default-weight rankings for every scenario, ready for the API and the dashboard."""
    scenarios = {}
    for scenario_id, scenario in inputs["scenarios"]["scenarios"].items():
        scenarios[scenario_id] = {
            "label": scenario["label"],
            "o2_mole_fraction": scenario["o2_mole_fraction"],
            "pressure_kpa": scenario["pressure_kpa"],
            "context_only": bool(scenario["context_only"]),
            "source": scenario["source"],
            "assumptions": scenario["assumptions"],
            "ranking": rank(scenario_id, None, inputs),
        }
    return {
        "version": 1,
        "component_weights": COMPONENT_WEIGHTS,
        "default_pillar_weights": DEFAULT_WEIGHTS,
        "tolerance": inputs["scenarios"]["tolerance"],
        "notes": inputs["notes"],
        "scenarios": scenarios,
    }


def write_json_atomic(path, document):
    """Write to a temporary file in the same folder, then swap it in, so readers never see half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    except OSError as error:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise RankError(f"cannot write {shown(path)}: {error}") from error


def format_table(results, top):
    lines = [f"{'#':>2}  {'score':>5}  {'investigation':22} {'fit':>4} {'mat':>4} {'pil':>4} {'data':>4}  why"]
    for result in results[:top]:
        c = result["components"]
        name = (result["acronym"] or result["accession"])[:22]
        lines.append(f"{result['rank']:>2}  {result['score']:.3f}  {name:22} {c['condition_fit']:.2f} {c['material_relevance']:.2f} "
                     f"{c['pillar_match']:.2f} {c['data_richness']:.2f}  {result['reasons'][0]}")
    return "\n".join(lines)


def run(argv=None):
    parser = argparse.ArgumentParser(prog="python -m si.rank", description="Rank PSI combustion investigations for a habitat.")
    parser.add_argument("--scenario", default="lunar_base", help="habitat id from data/domain/scenarios.json")
    parser.add_argument("--weights", default="", help="e.g. prevention=2,detection=1,suppression=1")
    parser.add_argument("--top", type=int, default=10, help="how many rows to print")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    parser.add_argument("--write", action="store_true", help="write data/processed/rankings.json for all scenarios")
    parser.add_argument("--debug", action="store_true", help="show the full traceback on unexpected errors")
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        inputs = load_inputs()
        for note in inputs["notes"]:
            print(f"note: {note}", file=sys.stderr)
        if args.write:
            document = build_rankings(inputs)
            write_json_atomic(PROCESSED / "rankings.json", document)
            print(f"wrote {shown(PROCESSED / 'rankings.json')} for {len(document['scenarios'])} scenarios")
            return 0
        results = rank(args.scenario, args.weights or None, inputs)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            scenario = inputs["scenarios"]["scenarios"][args.scenario]
            print(f"{scenario['label']}: O2 {scenario['o2_mole_fraction']}, pressure {scenario['pressure_kpa']} kPa"
                  + ("  (context only)" if scenario["context_only"] else ""))
            print(format_table(results, args.top))
        return 0
    except UsageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except RankError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
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
