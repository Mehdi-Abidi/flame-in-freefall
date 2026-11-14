"""Rank PSI combustion investigations for a habitat scenario (task S3).

Usage:
    python -m si.rank --scenario lunar_base [--weights prevention=2,detection=1,suppression=1] [--top 10]
    python -m si.rank --write
Library:
    from si.rank import load_inputs, rank
    results = rank("lunar_base", {"prevention": 2, "detection": 1, "suppression": 1}, load_inputs())
"""

import csv
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
