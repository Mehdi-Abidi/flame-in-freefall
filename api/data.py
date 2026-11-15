"""Loads the processed data once and answers filter queries. Standard library only.

tests.csv columns follow section 6 of docs/EXECUTION_PLAN.md and docs/data-notes.md.
"""

import csv
import io
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
RAW_INVESTIGATIONS = ROOT / "data" / "raw" / "investigations"

FLOAT_COLUMNS = ("size_mm", "o2_mole_fraction", "pressure_kpa", "flow_cm_s", "burn_time_s", "n_flames")


def normalize_accession(value: str) -> str:
    """'psi-69', 'PSI69' and '69' all become 'PSI-69'."""
    match = re.fullmatch(r"\s*(?:psi)?-?\s*(\d+)\s*", value or "", re.I)
    return f"PSI-{int(match.group(1))}" if match else (value or "").strip().upper()


def _to_float(text: str) -> Optional[float]:
    if text is None or text.strip() == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _typed_row(row: Dict[str, str]) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for key, value in row.items():
        if key in FLOAT_COLUMNS:
            out[key] = _to_float(value)
        else:
            out[key] = value if value != "" else None
    return out


class Store:
    def __init__(self, processed: Path = PROCESSED, raw_investigations: Path = RAW_INVESTIGATIONS):
        self.investigations: List[dict] = json.loads((processed / "investigations.json").read_text(encoding="utf-8"))
        self.by_accession: Dict[str, dict] = {item["accession"]: item for item in self.investigations}
        with (processed / "tests.csv").open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.test_columns: List[str] = list(reader.fieldnames or [])
            self.tests: List[Dict[str, object]] = [_typed_row(row) for row in reader]
        gravity_path = processed / "saffire2_gravity.csv"
        self.gravity: List[Dict[str, str]] = []
        if gravity_path.exists():
            with gravity_path.open(encoding="utf-8", newline="") as handle:
                self.gravity = list(csv.DictReader(handle))
        extracted_path = processed / "extracted.json"
        extracted = json.loads(extracted_path.read_text(encoding="utf-8")) if extracted_path.exists() else []
        self.extracted: Dict[str, dict] = {item["accession"]: item for item in extracted}
        self.raw: Dict[str, dict] = {}
        for accession in self.by_accession:
            path = raw_investigations / f"{accession}.json"
            if path.exists():
                self.raw[accession] = json.loads(path.read_text(encoding="utf-8"))

    def investigation(self, accession: str) -> Optional[dict]:
        return self.by_accession.get(normalize_accession(accession))

    def filter_tests(self, accessions: Optional[Iterable[str]] = None,
                     o2_min: Optional[float] = None, o2_max: Optional[float] = None,
                     p_min: Optional[float] = None, p_max: Optional[float] = None,
                     measured_only: bool = False, record_type: Optional[str] = None) -> List[Dict[str, object]]:
        """Rows matching every given filter. An O2 or pressure bound drops rows that have no value for it."""
        wanted = {normalize_accession(a) for a in accessions} if accessions else None
        rows = []
        for row in self.tests:
            if wanted is not None and row["accession"] not in wanted:
                continue
            if record_type and row["record_type"] != record_type:
                continue
            o2, pressure = row["o2_mole_fraction"], row["pressure_kpa"]
            if (o2_min is not None or o2_max is not None or measured_only) and o2 is None:
                continue
            if (p_min is not None or p_max is not None) and pressure is None:
                continue
            if o2_min is not None and o2 < o2_min:
                continue
            if o2_max is not None and o2 > o2_max:
                continue
            if p_min is not None and pressure < p_min:
                continue
            if p_max is not None and pressure > p_max:
                continue
            if measured_only and row["o2_source"] != "measured":
                continue
            rows.append(row)
        return rows

    def to_csv(self, rows: List[Dict[str, object]]) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=self.test_columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("" if value is None else value) for key, value in row.items()})
        return buffer.getvalue()


def parse_accessions(value: Optional[str]) -> List[str]:
    return [normalize_accession(part) for part in (value or "").split(",") if part.strip()]
