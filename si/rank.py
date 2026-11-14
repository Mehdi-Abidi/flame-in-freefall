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
