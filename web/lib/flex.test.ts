import { describe, expect, it } from "vitest";
import { flexByDiluent } from "./flex";

describe("FLEX by diluent", () => {
  it("matches the counts the suppression brief quotes", () => {
    const rows = Object.fromEntries(flexByDiluent().map((row) => [row.diluent, row]));
    expect([rows["N2+CO2"].out, rows["N2+CO2"].tests, rows["N2+CO2"].lo, rows["N2+CO2"].hi]).toEqual([88, 123, 0.14, 0.24]);
    expect([rows["N2+He"].out, rows["N2+He"].tests, rows["N2+He"].lo, rows["N2+He"].hi]).toEqual([40, 50, 0.13, 0.24]);
    expect([rows.N2.out, rows.N2.tests, rows.N2.lo, rows.N2.hi]).toEqual([58, 101, 0.12, 0.3]);
  });
});
