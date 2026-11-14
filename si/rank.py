"""Rank PSI combustion investigations for a habitat scenario (task S3).

Usage:
    python -m si.rank --scenario lunar_base [--weights prevention=2,detection=1,suppression=1] [--top 10]
    python -m si.rank --write
Library:
    from si.rank import load_inputs, rank
    results = rank("lunar_base", {"prevention": 2, "detection": 1, "suppression": 1}, load_inputs())
"""

import csv
import math
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


def _missing(path):
    hint = PRODUCERS.get(Path(path).name)
    return RankError(f"{path} not found." + (f" Create it with: {hint}" if hint else ""))


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise _missing(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RankError(f"{path} is not valid JSON (line {error.lineno}, column {error.colno}): {error.msg}") from error
    except (OSError, UnicodeDecodeError) as error:
        raise RankError(f"cannot read {path}: {error}") from error


def read_csv(path, required_columns):
    path = Path(path)
    if not path.is_file():
        raise _missing(path)
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(set(required_columns) - set(reader.fieldnames or []))
            if missing:
                raise RankError(f"{path} is missing columns {missing}. Regenerate it with: {PRODUCERS.get(path.name, 'its producer')}")
            return list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise RankError(f"cannot read {path}: {error}") from error


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
                raise RankError(f"weight '{part.strip()}' must look like pillar=number, e.g. prevention=2")
            name, number = part.split("=", 1)
            pairs[name.strip().lower()] = number.strip()
        value = pairs
    if not isinstance(value, dict):
        raise RankError(f"weights must be a mapping of pillar to number, got {type(value).__name__}")
    unknown = sorted(set(value) - set(PILLARS))
    if unknown:
        raise RankError(f"unknown pillar(s) {unknown}. Use {', '.join(PILLARS)}")
    weights = dict(DEFAULT_WEIGHTS)
    for name, number in value.items():
        try:
            number = float(number)
        except (TypeError, ValueError):
            raise RankError(f"weight for {name} must be a number, got {number!r}") from None
        if number != number or number in (float("inf"), float("-inf")):
            raise RankError(f"weight for {name} must be a finite number")
        if number < 0:
            raise RankError(f"weight for {name} cannot be negative")
        weights[name] = number
    if sum(weights.values()) == 0:
        raise RankError("at least one pillar weight must be above zero")
    return weights


CONDITION_RECORD_TYPES = {"test", "condition_matrix", "test_day_condition"}
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


def box_distance(value, box, tolerance):
    """0 inside the box, otherwise the gap to the nearest edge measured in tolerances."""
    if value < box[0]:
        return (box[0] - value) / tolerance
    if value > box[1]:
        return (value - box[1]) / tolerance
    return 0.0


def condition_fit(rows, scenario, tolerance):
    """How close an investigation's tested O2 and pressure come to a habitat, from 0 (nowhere near) to 1."""
    scored = []
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
            closeness = math.exp(-0.5 * (o2_gap ** 2 + p_gap ** 2)) * min(BASIS_WEIGHT[o2_basis], BASIS_WEIGHT[p_basis])
            inside = o2_gap == 0 and p_gap == 0 and o2_basis == "measured" and p_basis == "measured"
        else:
            closeness = math.exp(-0.5 * o2_gap ** 2) * BASIS_WEIGHT[o2_basis] * MISSING_PRESSURE_FACTOR
            inside = False
        scored.append((closeness, inside, o2, pressure))
    if not scored:
        return {"fit": 0.0, "n_considered": 0, "n_in_target": 0, "n_near": 0, "best": None}
    best = max(scored, key=lambda item: item[0])
    mean = sum(item[0] for item in scored) / len(scored)
    return {
        "fit": round(0.5 * best[0] + 0.5 * mean, 4),
        "n_considered": len(scored),
        "n_in_target": sum(1 for item in scored if item[1]),
        "n_near": sum(1 for item in scored if item[0] >= 0.6),
        "best": {"o2_mole_fraction": best[2], "pressure_kpa": best[3], "closeness": round(best[0], 4)},
    }
