# Data notes (tasks D1, D2 and D4)

How each PSI experimental table is read by `pipeline/normalize.py`, which units it uses, and what we had to clean. Run it with:

```bash
python pipeline/normalize.py
python pipeline/qa.py
```

`qa.py` checks the output against the data contract and against the raw tables, and exits with status 1 if anything fails. Run it after every change to `normalize.py`.

It reads `data/raw/tables/*.csv` and writes:

| File | Rows | What it is |
|---|---|---|
| `data/processed/tests.csv` | 2,127 | One row per test (or per test day or planned condition, see `record_type`) |
| `data/processed/saffire2_gravity.csv` | 9 | SAFFIRE-II burn length and spread in microgravity next to 1 g, for the Gravity Bounds panel |

## Columns added beyond the plan

The plan's schema (section 6) still holds. Six columns were added so every row has a stable key and nobody mistakes an assumed number for a measured one.

| Column | Values | Why |
|---|---|---|
| `row_id` | `PSI-69-0001` style | Unique key for the API and React lists. `test_id` is not unique: SPICE logs several fuel-rate settings per ignition and BASS reuses test numbers. |
| `record_type` | `test`, `test_day`, `test_day_condition`, `condition_matrix`, `session` | Several ACME tables list test days, not tests. FLEX-2 lists the planned test matrix, not results. |
| `o2_source` | `measured`, `planned`, `approximate`, `test_day_list`, `nominal_cabin_air` | Experiments run in ISS cabin air never logged O2. We fill 0.21 and say so. |
| `pressure_source` | `measured`, `planned`, `nominal_cabin`, `nominal_1atm` | Same idea for pressure. Nominal cabin pressure is 101.3 kPa. |
| `n_flames` | number | Flames ignited on that test day (ACME day tables) |
| `notes` | text | Anything the source said that does not fit a column |

**Rules every consumer can rely on** (enforced by `qa.py`): a value is present exactly when its source tag is set, `date` is ISO or blank, and `row_id` is unique.

**Rule for the map and the ranker:** plot `measured` values as solid dots and anything else as hollow markers. Never treat a `nominal` value as evidence that a condition was tested.

## Table by table

| Accession | Table | Rows out | O2 as | Pressure as | Other units | Quirks and how we handled them |
|---|---|---|---|---|---|---|
| PSI-69 | FLEX | 274 | mole fraction | mmHg | droplet mm, burn time s | File is Windows-1252, not UTF-8. Missing values are written as an en dash, read as blank. Header "CO initial" is CO2 (subscript lost). Test C11M201 logs 0 mmHg, blanked. 50 dates use two-digit years. |
| PSI-68 | FLEX-2 | 160 | list "0.17; 0.21;0.25; 0.3" | list in atm | droplet "1.5 - 5" mm, flow "0.1 - 5" cm/s | Only 8 rows, each a planned matrix per fuel. Expanded to O2 × pressure, tagged `condition_matrix`. |
| PSI-39 | CFI | 79 | mole fraction | text "1 atm", "2 atm" | | Fuel cells mix formulas and blends, e.g. `[.60]/[.40] C12H26/iso-dodecane`. Blends kept as written. 8 exact duplicate rows dropped. |
| PSI-159 | ACME CFI-G (normal, inverse) | 333 | XO2 | bar | burn time s | Inverse table has about 860 empty rows, dropped. In inverse flames O2 comes from the burner, up to 0.85. Outcome built from "Hot ignition" and "SE" (self-extinguished) or "FT" (flow terminated). The "Day" column is a campaign day number, not a date, so it goes to notes. **Open question:** in the normal-flame table the "Cool flame?" column is empty while "TFP" holds Yes/No, so the cool-flame flag may sit in the wrong column. Mufeed or Taha to check against the paper. |
| PSI-10 | ACME Flame Design (normal, inverse) | 327 | XO2 | atm (pmean) | | Some cells say "RAMPED", stored as a note. Tests 22024K2 and 22024K3 log XO2 = 2.0, blanked. Inverse table has no fuel column, its XC2H4 columns show ethylene. "Day" is a campaign day number, moved to notes. |
| PSI-20 | ACME BRE | 43 | list in percent, "21; 26.5; 40" | not listed | burner mm | One cell reads "3400%", an Excel artifact for 34. Each listed O2 becomes one `test_day_condition` row. Source says pressure was varied but not recorded here. |
| PSI-21 | ACME CLD Flame | 32 | none | none | | Test days only. Fuel cells were drag-filled in Excel ("40% CH5", "CH6"...), corrected to CH4. |
| PSI-22 | ACME E-FIELD Flames | 20 | none | none | | Test days only. Mesh polarity kept in notes. 8 exact duplicate rows dropped. |
| PSI-23 | ACME s-Flame | 18 | text "~21% O2 with N2" | about 1 atm per source note | spherical porous burner | Same drag-fill typos ("N3", "N4"), corrected. Values tagged `approximate`. |
| PSI-106 | SLICE | 12 | none | none | | Test days with free-text fuel descriptions. |
| PSI-107 | SPICE | 435 | cabin air | cabin | nozzle mm, air cm/s, fuel sccm | 34 exact duplicate rows dropped. Some rows say "Ku LOS" (lost signal) instead of a time. Date is a GMT day of year with no year, kept in notes. 8 rows log negative air flow (-0.28 and -5.92 cm/s), blanked. |
| PSI-26 | BASS | 121 | cabin air | cabin | sample size in cm | Material is free text ("2 cm sphere", "pmma slab oppsed"). Parsed into material, geometry and size. Spheres with no material named are inferred as PMMA and flagged "verify" in notes. One "SOOT Cleaning" row dropped. |
| PSI-25 | BASS-II | 129 | percent by volume | cabin | inches, mm, microns | Initial calibrated O2 used. Sizes like `1/4"`, `100 micron`, `3 mm thick` converted to mm. Fan and air display columns are unitless readings, not used. |
| PSI-98 | SAFFIRE-I | 2 | range "21.5 - 21.7" | cabin | cm in header | Range stored as its mean. Two flow-visualization rows dropped. |
| PSI-99 | SAFFIRE-II | 9 | "~ 22.1", "22.1 to 22.0" | cabin | units inside cells | Blank material cells are merged cells, forward-filled. Thickness "037 mm" is ambiguous and "See Fig. 5" is not a number, both left blank. Microgravity vs 1 g columns saved to `saffire2_gravity.csv`. |
| PSI-100 | SAFFIRE-III | 2 | none (cabin) | cabin | ".33 cm", "30 cm/s" | Column is "Direction", not "Flow Direction". |
| PSI-102 | SAME | 20 | cabin | cabin | flow cm/s, aging min | Samples 5 to 8 say "same conditions as 1-4", expanded into 4 rows each. |
| PSI-101 | SAME-R | 109 | cabin | cabin | inlet velocity cm/s | Dates have no year, kept in notes. |
| PSI-47 | DAFT / DAFT-2 | 2 | n/a | n/a | | Dates like "GMT 54 (2005)" converted to ISO. Dust, not fire. Tagged `fuel_phase = dust`, `record_type = session`. |
| PSI-142 | Data summary | 0 | | | | Lists figures in publications, no test conditions. Skipped. |

Investigations with no experimental table: PSI-60, PSI-62, PSI-115, PSI-117 (all ground studies). Their conditions must come from the LLM extraction of their metadata (task S2).

## investigations.json (task D3)

`pipeline/build_investigations.py` joins the raw PSI metadata with `tests.csv` into one record per investigation (24 in total).

| Count | Value |
|---|---|
| Investigations with an experimental table | 20 |
| Investigations with rows in `tests.csv` | 19 (PSI-142's table lists publications, not tests) |
| Investigations with a measured O2 range | 7: FLEX, CFI, CFI-G, Flame Design, BASS-II, SAFFIRE-I, SAFFIRE-II |
| Investigations whose O2 range is nominal cabin air | 5: SPICE, BASS, SAME, SAME-R, SAFFIRE-III |
| Investigations with test days or a planned matrix only (`n_tests` = 0) | FLEX-2, ACME BRE, CLD, E-FIELD, s-Flame, SLICE, DAFT |

Platform comes from PSI metadata. PSI lists SAFFIRE-I and SAFFIRE-III as ISS even though every Saffire burn ran inside a departing Cygnus vehicle. Taha should decide in T1 whether to override that.

## Check of the pitch claim (task D3)

Confirmed on the normalized data, 14 Nov 2026:

- **No solid-material test in PSI has a measured O2 above 22.2%** (140 solid tests with measured O2: 129 BASS-II, 9 SAFFIRE-II, 2 SAFFIRE-I).
- **66 individual tests** sit at lunar-base conditions (O2 of 30% or more at 70.3 kPa or less). All are gas flames: 48 from ACME CFI-G and 18 from ACME Flame Design.
- Above 30% O2 at any pressure there are 476 tests: 230 CFI-G, 222 Flame Design (both gas) and 24 FLEX (liquid droplets).

So the pitch line is safe: lunar habitats will run at 30% O2 or more, and every solid-material fire test in PSI stopped at about 22%.

## A gravity finding for the demo

`saffire2_gravity.csv` puts the same samples side by side. At about 22% O2 and 20 cm/s flow, thin silicone sheets burned completely in 1 g tests but barely burned at all in microgravity. The cotton-fiberglass (SIBAL) samples spread the full 29 cm in microgravity too. Gravity changes which materials are dangerous, so 1 g screening alone can mislead in both directions. Ahsan can build the Gravity Bounds panel (V4) around this.

## Known gaps for later

- Outcome is blank for most rows because many tables do not record one.
- Exact duplicate rows are dropped in every table (50 in total: 34 SPICE, 8 CFI, 8 E-FIELD).
- Dates are ISO where the source gives a full date. Anything else (SPICE day of year, SAME-R dates with no year, ACME campaign day numbers) is kept in `notes` and `date` is left blank.
- `size_mm` means whatever the source gave: droplet diameter, sample thickness, sphere diameter or strip width. Check `geometry` before comparing sizes across investigations.
