import { readFileSync } from "node:fs";
import path from "node:path";
import { parseCsv } from "./csv";
import { LAB_PHASES, type LabTest } from "./lab";
import type { Phase } from "./types";

const DATA_DIR = process.env.FLAME_DATA_DIR ?? path.join(process.cwd(), "..", "data");
const SMOKE_INVESTIGATIONS = ["PSI-101", "PSI-102"];

export interface LabData {
  tests: LabTest[];
  smoke: { tests: number; o2: number; accessions: string[] };
}

/** Flight tests with a measured oxygen value, plus the smoke tests, which ran in assumed cabin air. */
export function loadLabData(): LabData {
  const rows = parseCsv(readFileSync(path.join(DATA_DIR, "processed/tests.csv"), "utf-8")).filter((r) => r.record_type === "test");
  const number = (value: string | undefined) => (value === undefined || value.trim() === "" || !Number.isFinite(Number(value)) ? null : Number(value));

  const tests: LabTest[] = [];
  for (const r of rows) {
    const o2 = number(r.o2_mole_fraction);
    if (r.o2_source !== "measured" || o2 === null || !(LAB_PHASES as string[]).includes(r.fuel_phase)) continue;
    tests.push({ a: r.accession, ph: r.fuel_phase as Phase, o2, kpa: number(r.pressure_kpa), fuel: r.fuel, out: r.outcome ?? "" });
  }

  const smokeRows = rows.filter((r) => SMOKE_INVESTIGATIONS.includes(r.accession));
  return {
    tests,
    smoke: { tests: smokeRows.length, o2: number(smokeRows[0]?.o2_mole_fraction) ?? 0.21, accessions: SMOKE_INVESTIGATIONS },
  };
}
