import { readFileSync } from "node:fs";
import path from "node:path";
import { parseCsv } from "./csv";

const DATA_DIR = process.env.FLAME_DATA_DIR ?? path.join(process.cwd(), "..", "data");
const LABEL: Record<string, string> = { N2: "Nitrogen only", "N2+CO2": "Nitrogen and carbon dioxide", "N2+He": "Nitrogen and helium" };

export interface DiluentRow {
  diluent: string;
  label: string;
  tests: number;
  out: number;
  lo: number;
  hi: number;
}

/** How FLEX's droplet tests ended for each diluent: how many went out, and over which oxygen range. */
export function flexByDiluent(): DiluentRow[] {
  const rows = parseCsv(readFileSync(path.join(DATA_DIR, "processed/tests.csv"), "utf-8")).filter(
    (r) => r.accession === "PSI-69" && r.record_type === "test" && r.o2_source === "measured" && r.o2_mole_fraction.trim() !== "",
  );
  return Object.keys(LABEL)
    .map((diluent) => {
      const group = rows.filter((r) => r.diluent === diluent);
      const out = group.filter((r) => (r.outcome ?? "").includes("extinction")).map((r) => Number(r.o2_mole_fraction));
      return { diluent, label: LABEL[diluent], tests: group.length, out: out.length, lo: out.length ? Math.min(...out) : 0, hi: out.length ? Math.max(...out) : 0 };
    })
    .filter((row) => row.tests > 0);
}
