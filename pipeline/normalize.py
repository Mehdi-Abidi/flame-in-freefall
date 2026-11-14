"""Build data/processed/tests.csv and saffire2_gravity.csv from the PSI experimental tables.

Usage: python pipeline/normalize.py [--raw data/raw] [--out data/processed]
"""

import argparse
import csv
import datetime as dt
import glob
import io
import os
import re
import statistics

COLUMNS = [
    "row_id", "accession", "acronym", "source_file", "record_type", "test_id", "date",
    "fuel", "fuel_phase", "geometry", "size_mm",
    "o2_mole_fraction", "o2_source", "pressure_kpa", "pressure_source",
    "diluent", "flow_cm_s", "gravity", "outcome", "burn_time_s", "n_flames", "notes",
]

CABIN_PRESSURE_KPA = 101.3
AIR_O2 = 0.21
KPA_PER = {"atm": 101.325, "bar": 100.0, "mmhg": 0.133322, "psi": 6.89476, "kpa": 1.0}
NUMBER = re.compile(r"-?\d+(?:\.\d+)?|-?\.\d+")
FUEL_NAMES = {
    "c2h4": "ethylene", "ch4": "methane", "c3h8": "propane", "c2h6": "ethane",
    "c12h26": "n-dodecane", "c3h6": "propylene", "dme": "dimethyl ether",
}
OUTCOMES = {
    "extinction": "extinction", "disruption": "disruption", "completion": "burned to completion",
    "se": "self-extinguished", "ft": "flow terminated",
}
MONTHS = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr", "june": "Jun", "july": "Jul",
    "august": "Aug", "sept": "Sep", "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
}
NOT_AVAILABLE = {"–", "—", "-", "n/a", "na"}
DUPLICATES_DROPPED = {}


def key(text):
    return " ".join(str(text).replace("﻿", "").split()).strip().lower()


def decode(raw_bytes):
    try:
        return raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw_bytes.decode("cp1252", errors="replace")


def read_table(path):
    with open(path, "rb") as handle:
        rows = list(csv.reader(io.StringIO(decode(handle.read()), newline="")))
    header = [key(h) for h in rows[0]]
    records = []
    seen = set()
    dropped = 0
    for raw in rows[1:]:
        if not any(cell.strip() for cell in raw):
            continue
        signature = tuple(cell.strip() for cell in raw)
        if signature in seen:
            dropped += 1
            continue
        seen.add(signature)
        records.append({header[i]: ("" if raw[i].strip().lower() in NOT_AVAILABLE else raw[i].strip())
                        for i in range(min(len(header), len(raw)))})
    DUPLICATES_DROPPED[os.path.basename(path)] = dropped
    return records


def col(record, *needles):
    for name, value in record.items():
        if all(n in name for n in needles):
            return value
    return ""


def numbers(text):
    return [float(n) for n in NUMBER.findall(str(text).replace(",", ""))]


def first_number(text):
    found = numbers(text)
    return found[0] if found else None


def range_mean(text):
    found = numbers(text)
    if not found:
        return None
    if re.search(r"\d\s*-\s*\d", str(text)):
        return statistics.mean(found[:2])
    return found[0]


def as_fraction(value):
    if value is None:
        return None
    while value > 100:
        value /= 100
    return round(value / 100, 4) if value > 1 else round(value, 4)


def to_kpa(text, default_unit=None):
    value = first_number(text)
    if value is None:
        return None
    lowered = str(text).lower()
    unit = next((u for u in KPA_PER if u in lowered), default_unit)
    return round(value * KPA_PER[unit], 2) if unit else None


def length_mm(text):
    value = first_number(text)
    if value is None or re.match(r"^\s*0\d", str(text)):
        return None
    lowered = str(text).lower()
    if '"' in lowered or "inch" in lowered:
        return round(value * 25.4, 2)
    if "micron" in lowered:
        return round(value / 1000, 3)
    if "mm" in lowered:
        return value
    if "cm" in lowered:
        return round(value * 10, 2)
    return None


def day_of_year(year, day):
    return (dt.date(year, 1, 1) + dt.timedelta(days=day - 1)).isoformat()


def iso_date(text):
    text = str(text).strip().replace("`", "").rstrip("*")
    cleaned = re.sub(r"[A-Za-z]+\.?", lambda m: MONTHS.get(m.group(0).rstrip(".").lower(), m.group(0).rstrip(".")), text)
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%b-%d", "%d-%b-%y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            pass
    match = re.match(r"^(\d{2})(\d{3})$", text)
    if match:
        return day_of_year(2000 + int(match.group(1)), int(match.group(2)))
    match = re.match(r"^GMT\s+(\d{1,3})\s+\((\d{4})\)$", text)
    if match:
        return day_of_year(int(match.group(2)), int(match.group(1)))
    return text


def fuel_label(text):
    cleaned = re.sub(r"CH[5-9]\b", "CH4", str(text))
    cleaned = re.sub(r"with N[3-9]\b", "with N2", cleaned)
    lowered = cleaned.lower()
    if "/" in lowered or "mixture" in lowered:
        return cleaned.strip()
    for formula, name in FUEL_NAMES.items():
        if re.search(rf"\b{formula}\b", lowered):
            share = re.search(r"(\d+)\s*%", cleaned)
            return f"{name} {share.group(1)}% in N2" if share and share.group(1) != "100" else name
    return cleaned.strip()


def solid_sample(text):
    lowered = key(text)
    material = "unknown"
    for needle, name in (("pmma", "PMMA"), ("sibal", "SIBAL cotton-fiberglass"), ("nomex", "Nomex"),
                         ("ultem", "Ultem"), ("japan wax", "Japan wax"), ("paraf", "paraffin wax"),
                         ("parraf", "paraffin wax"), ("candle", "paraffin wax"), ("wax", "paraffin wax"),
                         ("rod", "PMMA"), ("film", "PMMA"), ("micron", "PMMA"), ("sphere", "PMMA")):
        if needle in lowered:
            material = name
            break
    geometry = "sample"
    for needle, name in (("sphere", "sphere"), ("rod", "rod"), ("candle", "candle"), ("slab", "slab"),
                         ("film", "thin film"), ("sheet", "sheet"), ("thick", "flat strip"), ("sibal", "fabric strip"),
                         ("nomex", "fabric strip")):
        if needle in lowered:
            geometry = name
            break
    size = None
    for pattern in (r"(\d+(?:\.\d+)?)\s*micron", r"(\d+(?:\.\d+)?)\s*mm thick", r"(\d+/\d+)\"?", r"(\d+(?:\.\d+)?)\s*\"",
                    r"(\d+(?:\.\d+)?)\s*cm"):
        match = re.search(pattern, lowered)
        if match:
            token = match.group(1)
            value = eval_fraction(token)
            if "micron" in pattern:
                size = round(value / 1000, 3)
            elif "mm" in pattern:
                size = value
            elif "cm" in pattern:
                size = value * 10
            else:
                size = round(value * 25.4, 2)
            break
    return material, geometry, size


def eval_fraction(token):
    if "/" in token:
        top, bottom = token.split("/")
        return float(top) / float(bottom)
    return float(token)


def base(accession, acronym, source_file, **values):
    row = {c: "" for c in COLUMNS}
    row.update(accession=accession, acronym=acronym, source_file=source_file, gravity="micro", record_type="test")
    row.update({k: v for k, v in values.items() if v is not None})
    return row


def flex(path, name):
    rows = []
    for r in read_table(path):
        diluents = [label for label, needle in (("N2", "n initial"), ("CO2", "co initial"), ("He", "he initial"))
                    if (first_number(col(r, needle)) or 0) > 0]
        rows.append(base("PSI-69", "FLEX", name, test_id=col(r, "flex identifier"), date=iso_date(col(r, "test date")),
                         fuel=col(r, "fuel").lower(), fuel_phase="liquid", geometry="droplet",
                         size_mm=first_number(col(r, "droplet initial diameter")),
                         o2_mole_fraction=first_number(col(r, "o initial")), o2_source="measured",
                         pressure_kpa=to_kpa(col(r, "ambient pressure"), "mmhg"), pressure_source="measured",
                         diluent="+".join(diluents), outcome=OUTCOMES.get(col(r, "test end").lower(), col(r, "test end").lower()),
                         burn_time_s=first_number(col(r, "burn time"))))
    return rows


def flex2(path, name):
    rows = []
    for r in read_table(path):
        o2_values = numbers(col(r, "oxygen mole fraction"))
        pressures = numbers(col(r, "ambient pressure"))
        for o2 in o2_values:
            for atm in pressures:
                rows.append(base("PSI-68", "FLEX-2", name, record_type="condition_matrix",
                                 fuel=col(r, "sample").lower(), fuel_phase="liquid", geometry="droplet",
                                 o2_mole_fraction=o2, o2_source="planned", pressure_kpa=round(atm * KPA_PER["atm"], 2),
                                 pressure_source="planned", diluent="N2 or He", flow_cm_s=None,
                                 notes=f"droplet {col(r, 'droplet diameter')} mm, flow {col(r, 'flow velocity')} cm/s, test matrix not per-test results"))
    return rows


def cfi(path, name):
    rows = []
    for r in read_table(path):
        diluents = [label for label, needle in (("N2", "nitrogen"), ("He", "helium")) if (first_number(col(r, needle)) or 0) > 0]
        rows.append(base("PSI-39", "CFI", name, test_id=col(r, "cir"), date=iso_date(col(r, "test date")),
                         fuel=fuel_label(col(r, "fuel")), fuel_phase="liquid",
                         geometry="fiber-supported droplet" if col(r, "fiber").lower() == "yes" else "droplet",
                         o2_mole_fraction=first_number(col(r, "oxygen")), o2_source="measured",
                         pressure_kpa=to_kpa(col(r, "pressure"), "atm"), pressure_source="measured",
                         diluent="+".join(diluents)))
    return rows


def cfi_g(path, name):
    rows = []
    inverse = "inverse" in name.lower()
    for r in read_table(path):
        test = col(r, "test")
        if not test:
            continue
        o2 = first_number(col(r, "xo2")) if inverse else first_number(col(r, "xo2 before"))
        ignited = col(r, "hot ignition").lower()
        termination = OUTCOMES.get(col(r, "self", "ext").lower() or col(r, "self-ext").lower(), "")
        outcome = "no ignition" if ignited == "no" else termination or ("ignited" if ignited == "yes" else "")
        notes = [f"ACME test day {col(r, 'day')}"] if col(r, "day") else []
        if not inverse and col(r, "cool flame").lower() == "yes":
            notes.append("cool flame observed")
        if col(r, "comments"):
            notes.append(col(r, "comments"))
        rows.append(base("PSI-159", "ACME CFI-G", name, test_id=test,
                         fuel=col(r, "fuel").lower(), fuel_phase="gas",
                         geometry="spherical burner, inverse flame" if inverse else "spherical burner, normal flame",
                         o2_mole_fraction=o2, o2_source="measured",
                         pressure_kpa=to_kpa(col(r, "approx p"), "bar"), pressure_source="measured",
                         diluent="N2", outcome=outcome, burn_time_s=first_number(col(r, "burn time")),
                         notes="; ".join(notes)))
    return rows


def flame_design(path, name):
    rows = []
    inverse = "inverse" in name.lower()
    for r in read_table(path):
        o2 = first_number(col(r, "xo2")) if inverse else first_number(col(r, "xo2 (init)"))
        pressure = first_number(col(r, "pmean"))
        notes = [f"ACME test day {col(r, 'day')}"] if col(r, "day") else []
        if "ramped" in " ".join(r.values()).lower():
            notes.append("flow ramped during test")
        rows.append(base("PSI-10", "ACME Flame Design", name, test_id=col(r, "test"),
                         fuel="ethylene" if inverse else fuel_label(col(r, "fuel")), fuel_phase="gas",
                         geometry="spherical burner, inverse flame" if inverse else "spherical burner, normal flame",
                         o2_mole_fraction=o2, o2_source="measured",
                         pressure_kpa=round(pressure * KPA_PER["atm"], 2) if pressure else None,
                         pressure_source="measured" if pressure else "", diluent="N2",
                         notes="; ".join(notes)))
    return rows


def acme_bre(path, name):
    rows = []
    for r in read_table(path):
        day = f"{col(r, 'year')}-{col(r, 'month')}-{col(r, 'date')}"
        for value in numbers(col(r, "oxygen conc")) or [None]:
            rows.append(base("PSI-20", "ACME BRE", name, record_type="test_day_condition", date=iso_date(day.replace("March", "Mar")),
                             fuel=fuel_label(col(r, "fuel bottle")), fuel_phase="gas",
                             geometry="porous burner (burning rate emulator)", size_mm=first_number(col(r, "burner size")),
                             o2_mole_fraction=as_fraction(value), o2_source="test_day_list" if value else "",
                             diluent="N2", n_flames=first_number(col(r, "flames ignited")),
                             notes="pressure varied but not listed in source table"))
    return rows


def acme_day_table(accession, acronym, geometry):
    def parse(path, name):
        rows = []
        for r in read_table(path):
            fuel = col(r, "fuel bottle")
            if not fuel:
                continue
            atmosphere = col(r, "atmosphere")
            o2 = as_fraction(first_number(atmosphere)) if atmosphere else None
            rows.append(base(accession, acronym, name, record_type="test_day", test_id=col(r, "test day"),
                             date=iso_date(col(r, "test day").rstrip("*")), fuel=fuel_label(fuel), fuel_phase="gas",
                             geometry=geometry, o2_mole_fraction=o2, o2_source="approximate" if o2 else "",
                             pressure_kpa=CABIN_PRESSURE_KPA if atmosphere else None,
                             pressure_source="nominal_1atm" if atmosphere else "",
                             n_flames=first_number(col(r, "flames ignited")),
                             notes=" ".join(filter(None, [col(r, "test type"), col(r, "mesh polarity") and f"mesh polarity {col(r, 'mesh polarity')}",
                                                          col(r, "fuel conc") and f"fuel conc {col(r, 'fuel conc')}"]))))
        return rows
    return parse


def slice_table(path, name):
    rows = []
    for r in read_table(path):
        rows.append(base("PSI-106", "SLICE", name, record_type="test_day", date=iso_date(col(r, "test date").split(" ")[0]),
                         fuel=fuel_label(col(r, "fuel type").split(" including")[0]), fuel_phase="gas",
                         geometry="coflow jet nozzle", notes=col(r, "fuel type")))
    return rows


def spice(path, name):
    rows = []
    for r in read_table(path):
        rows.append(base("PSI-107", "SPICE", name, test_id=f"{col(r, 'gmt date')}-{col(r, 'gmt ignition')}",
                         fuel=col(r, "fuel").lower(), fuel_phase="gas",
                         geometry="coflow jet nozzle", size_mm=first_number(col(r, "nozzle")),
                         o2_mole_fraction=AIR_O2, o2_source="nominal_cabin_air",
                         pressure_kpa=CABIN_PRESSURE_KPA, pressure_source="nominal_cabin",
                         diluent="N2 (air)", flow_cm_s=first_number(col(r, "air rate")),
                         notes=f"GMT day {col(r, 'gmt date')} (year not given); fuel rate {col(r, 'fuel rate (sccm)')} sccm"))
    return rows


def bass(path, name):
    rows = []
    for r in read_table(path):
        sample = col(r, "fuel sample material")
        if "soot" in sample.lower():
            continue
        material, geometry, size = solid_sample(sample)
        rows.append(base("PSI-26", "BASS", name, test_id=col(r, "as run test"), date=iso_date(col(r, "date")),
                         fuel=material, fuel_phase="solid", geometry=geometry, size_mm=size,
                         o2_mole_fraction=AIR_O2, o2_source="nominal_cabin_air",
                         pressure_kpa=CABIN_PRESSURE_KPA, pressure_source="nominal_cabin",
                         diluent="N2 (air)", notes=sample))
    return rows


def bass2(path, name):
    rows = []
    for r in read_table(path):
        sample = col(r, "fuel sample material")
        material, geometry, size = solid_sample(sample)
        o2 = first_number(col(r, "initial o2"))
        rows.append(base("PSI-25", "BASS-II", name, test_id=col(r, "test #"), date=iso_date(col(r, "date")),
                         fuel=material, fuel_phase="solid", geometry=geometry, size_mm=size,
                         o2_mole_fraction=as_fraction(o2), o2_source="measured" if o2 else "",
                         pressure_kpa=CABIN_PRESSURE_KPA, pressure_source="nominal_cabin",
                         diluent="N2", notes=f"{sample}; PI {col(r, 'pi')}"))
    return rows


def saffire(accession, acronym):
    def parse(path, name):
        rows = []
        previous_material = ""
        for r in read_table(path):
            if not re.match(r"^(S\d|\d+-\d+)", col(r, "sample number")):
                continue
            material = col(r, "material") or previous_material
            previous_material = material
            o2 = range_mean(col(r, "percent o2"))
            rows.append(base(accession, acronym, name, test_id=col(r, "sample number"),
                             fuel=material, fuel_phase="solid", geometry=f"large sheet, {col(r, 'direction').strip().lower()} flow",
                             size_mm=round(float(col(r, "thickness")) * 10, 3) if re.fullmatch(r"\d*\.?\d+", col(r, "thickness"))
                             else length_mm(col(r, "thickness")),
                             o2_mole_fraction=as_fraction(o2) if o2 else AIR_O2,
                             o2_source="measured" if o2 else "nominal_cabin_air",
                             pressure_kpa=CABIN_PRESSURE_KPA, pressure_source="nominal_cabin", diluent="N2 (air)",
                             flow_cm_s=first_number(col(r, "air flow")), burn_time_s=first_number(col(r, "burn time")),
                             notes="flown in a departing Cygnus cargo vehicle"))
        return rows
    return parse


def saffire2_gravity(path):
    out = []
    previous_material = ""
    for r in read_table(path):
        if not re.match(r"^\d+-\d+", col(r, "sample number")):
            continue
        previous_material = col(r, "material") or previous_material
        out.append({
            "sample": col(r, "sample number"), "material": previous_material, "thickness": col(r, "thickness"),
            "flow_direction": col(r, "flow direction"),
            "micro_g_burn_length": col(r, "-g burn length"), "micro_g_spread_length": col(r, "-g spread length"),
            "one_g_burn_length": col(r, "1-g burn length"), "one_g_spread_rate": col(r, "1-g spread rate"),
        })
    return out


def same(path, name):
    rows = []
    records = read_table(path)
    template = [r for r in records if first_number(col(r, "air flow")) is not None]
    for r in records:
        material = col(r, "sample material")
        copies = [r] if r in template else [dict(t, **{"sample material": material.split(":")[0]}) for t in template]
        for index, c in enumerate(copies, start=1):
            test_id = col(r, "sample #") if c is r else f"{col(r, 'sample #')}.{index}"
            rows.append(base("PSI-102", "SAME", name, test_id=test_id, fuel=col(c, "sample material").split(":")[0],
                             fuel_phase="solid", geometry="heated smoke source", o2_mole_fraction=AIR_O2,
                             o2_source="nominal_cabin_air", pressure_kpa=CABIN_PRESSURE_KPA, pressure_source="nominal_cabin",
                             flow_cm_s=first_number(col(c, "air flow")),
                             notes=f"aging {col(c, 'aging duration')} min, weight loss {col(c, 'weight loss')} mg/min"
                             + ("" if c is r else "; conditions copied from samples 1-4 per source note")))
    return rows


def same_r(path, name):
    rows = []
    for r in read_table(path):
        rows.append(base("PSI-101", "SAME-R", name, test_id=col(r, "same test"), date=col(r, "date"),
                         fuel=col(r, "sample type"), fuel_phase="solid", geometry="heated smoke source",
                         o2_mole_fraction=AIR_O2, o2_source="nominal_cabin_air", pressure_kpa=CABIN_PRESSURE_KPA,
                         pressure_source="nominal_cabin", flow_cm_s=first_number(col(r, "inlet velocity")),
                         notes=f"{col(r, 'description')}; duration {col(r, 'duration')} s"))
    return rows


def daft(path, name):
    rows = []
    for r in read_table(path):
        rows.append(base("PSI-47", "DAFT / DAFT-2", name, record_type="session", test_id=col(r, "session name"),
                         date=iso_date(col(r, "actual day")), fuel="Arizona road dust", fuel_phase="dust",
                         geometry="aerosol sampling", notes=f"{col(r, 'hardware')}; {col(r, 'sampled location')}"))
    return rows


PARSERS = {
    "PSI-69_": flex, "PSI-68_": flex2, "PSI-39_": cfi, "PSI-159_": cfi_g, "PSI-10_": flame_design,
    "PSI-20_": acme_bre, "PSI-21_": acme_day_table("PSI-21", "ACME CLD Flame", "coflow burner"),
    "PSI-22_": acme_day_table("PSI-22", "ACME E-FIELD Flames", "coflow or gas-jet burner with electric field"),
    "PSI-23_": acme_day_table("PSI-23", "ACME s-Flame", "spherical porous burner"),
    "PSI-106_": slice_table, "PSI-107_": spice, "PSI-26_": bass, "PSI-25_": bass2,
    "PSI-98_": saffire("PSI-98", "SAFFIRE-I"), "PSI-99_": saffire("PSI-99", "SAFFIRE-II"),
    "PSI-100_": saffire("PSI-100", "SAFFIRE-III"), "PSI-102_": same, "PSI-101_": same_r, "PSI-47_": daft,
}
SKIPPED = {"PSI-142_": "data summary of publications, no per-test conditions"}


def write_csv(path, rows, columns):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--out", default="data/processed")
    args = parser.parse_args()

    all_rows = []
    for path in sorted(glob.glob(os.path.join(args.raw, "tables", "*.csv"))):
        name = os.path.basename(path)
        prefix = name.split("Experimental")[0]
        if prefix in SKIPPED:
            print(f"skip   {name}: {SKIPPED[prefix]}")
            continue
        rows = PARSERS[prefix](path, name)
        all_rows.extend(rows)
        print(f"{len(rows):5}  {name}")
        if prefix == "PSI-99_":
            write_csv(os.path.join(args.out, "saffire2_gravity.csv"), saffire2_gravity(path),
                      ["sample", "material", "thickness", "flow_direction", "micro_g_burn_length",
                       "micro_g_spread_length", "one_g_burn_length", "one_g_spread_rate"])

    finalize(all_rows)
    write_csv(os.path.join(args.out, "tests.csv"), all_rows, COLUMNS)
    dropped = {name: count for name, count in DUPLICATES_DROPPED.items() if count}
    print(f"dropped exact duplicate source rows: {dropped}")
    print(f"total  {len(all_rows)} rows -> {os.path.join(args.out, 'tests.csv')}")


def add_note(row, text):
    row["notes"] = "; ".join(filter(None, [row["notes"], text]))


def finalize(rows):
    counters = {}
    for row in rows:
        o2, pressure, flow = row["o2_mole_fraction"], row["pressure_kpa"], row["flow_cm_s"]
        if isinstance(o2, float) and not 0 < o2 <= 1:
            add_note(row, f"source O2 value {o2} out of range, blanked")
            row["o2_mole_fraction"] = ""
        if isinstance(pressure, float) and pressure <= 0:
            add_note(row, f"source pressure {pressure} out of range, blanked")
            row["pressure_kpa"] = ""
        if isinstance(flow, float) and flow < 0:
            add_note(row, f"source flow {flow} cm/s is negative, blanked")
            row["flow_cm_s"] = ""
        if row["o2_mole_fraction"] in ("", None):
            row["o2_mole_fraction"], row["o2_source"] = "", ""
        if row["pressure_kpa"] in ("", None):
            row["pressure_kpa"], row["pressure_source"] = "", ""
        if row["date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row["date"])):
            add_note(row, f"date as given: {row['date']}")
            row["date"] = ""
        if row["fuel_phase"] == "solid" and row["fuel"] == "PMMA" and "pmma" not in row["notes"].lower() and row["acronym"].startswith("BASS"):
            add_note(row, "material inferred as PMMA, verify")
        for field in ("size_mm", "o2_mole_fraction", "pressure_kpa", "flow_cm_s", "burn_time_s", "n_flames"):
            if isinstance(row[field], float):
                row[field] = round(row[field], 4)
        counters[row["accession"]] = counters.get(row["accession"], 0) + 1
        row["row_id"] = f"{row['accession']}-{counters[row['accession']]:04d}"


if __name__ == "__main__":
    main()
